"""Orchestrates the two-phase dashboard generation flow and the mandatory
entity-ID / custom-card-type validation gate.

Split at the curation seam (Milestone 4): `propose_structure()` runs phase 1
(structure proposal) and resolves each proposed view's candidate entities,
stopping short of spending any phase-2 LLM calls -- the caller curates
which views/entities survive before `generate_from_curated_views()` spends
anything on phase 2. Phase 1 errors propagate to the caller unchanged --
there is no dashboard to build at all if that call fails. Phase 2
(per-view card generation) failures are isolated per view: a transient
failure generating one view's cards must not void the whole response, so
each is caught, logged, and turned into a user-facing note instead.

This app stays stateless end to end (no M1-M3 milestone introduced
server-side session state, and M4 doesn't either): the caller is expected
to hold a `StructureProposalOutcome` in memory (or echo it back over the
wire, as `api/routes_dashboard.py` does), apply curation to its
`proposed_views`, and pass the curated subset straight into
`generate_from_curated_views()`.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from dashboard_studio.dashboard.config import (
    GeneratedDashboard,
    GenerationStrategy,
    SectionsView,
    StyleHint,
    to_style_hint,
)
from dashboard_studio.dashboard.custom_cards import (
    allowed_custom_type_strings,
    available_custom_cards,
    detect_installed_custom_card_families,
)
from dashboard_studio.dashboard.generation_client import (
    DashboardGenerationClient,
    DashboardGenerationError,
    DashboardGenerationUpstreamError,
)
from dashboard_studio.dashboard.scope import (
    MAX_PROPOSED_VIEWS,
    CandidateEntitySummary,
    resolve_view_entities,
    summarize_scope,
    to_candidate_summary,
)
from dashboard_studio.dashboard.validation import ValidationReport, validate_and_strip
from dashboard_studio.design.tokens import DesignTokenSet
from dashboard_studio.ha.models import LovelaceResource
from dashboard_studio.registry.snapshot import EntityRecord

log = logging.getLogger(__name__)


@dataclass
class GenerationUsageTotals:
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None
    model: str
    call_count: int


def combine_usage_totals(
    phase1: GenerationUsageTotals, phase2: GenerationUsageTotals
) -> GenerationUsageTotals:
    """`model` is always taken from `phase1` -- that call always happens
    exactly once and always has a real model name, whereas phase 2 can
    legitimately make zero calls (every curated view skipped/emptied out).
    """
    cost_known = phase1.estimated_cost_usd is not None and phase2.estimated_cost_usd is not None
    return GenerationUsageTotals(
        input_tokens=phase1.input_tokens + phase2.input_tokens,
        output_tokens=phase1.output_tokens + phase2.output_tokens,
        estimated_cost_usd=(
            (phase1.estimated_cost_usd or 0.0) + (phase2.estimated_cost_usd or 0.0) if cost_known else None
        ),
        model=phase1.model,
        call_count=phase1.call_count + phase2.call_count,
    )


@dataclass
class ProposedView:
    name: str
    candidates: list[CandidateEntitySummary]


@dataclass
class StructureProposalOutcome:
    proposed_views: list[ProposedView]
    available_custom_cards: dict[str, dict[str, str]]
    style_hint: StyleHint | None
    usage: GenerationUsageTotals
    notes: list[str]


@dataclass
class DashboardGenerationOutcome:
    dashboard: GeneratedDashboard
    validation: ValidationReport
    usage: GenerationUsageTotals
    notes: list[str]


async def propose_structure(
    *,
    client: DashboardGenerationClient,
    scoped_entities: list[EntityRecord],
    lovelace_resources: list[LovelaceResource],
    strategy: GenerationStrategy,
    tokens: DesignTokenSet | None,
) -> StructureProposalOutcome:
    notes: list[str] = []

    families = detect_installed_custom_card_families(lovelace_resources)
    available = available_custom_cards(families)
    for family in sorted(families - set(available)):
        notes.append(
            f"Erkannte Ressource '{family}' stellt keinen eigenen Kartentyp bereit "
            "und wird nicht als Kartentyp verwendet."
        )

    style_hint = to_style_hint(tokens) if tokens is not None else None

    scope_summary = summarize_scope(scoped_entities)
    structure_result = await client.propose_view_structure(scope_summary, strategy)
    proposals = structure_result.output.views

    if not proposals:
        raise DashboardGenerationUpstreamError("Es konnten keine Ansichten vorgeschlagen werden.")

    if len(proposals) > MAX_PROPOSED_VIEWS:
        notes.append(f"{len(proposals)} Ansichten vorgeschlagen, auf {MAX_PROPOSED_VIEWS} begrenzt.")
        proposals = proposals[:MAX_PROPOSED_VIEWS]

    proposed_views: list[ProposedView] = []
    for proposal in proposals:
        candidates = resolve_view_entities(scoped_entities, proposal.selector)
        if not candidates:
            notes.append(f"Ansicht '{proposal.name}' übersprungen: keine passenden Entitäten im Scope.")
            continue
        proposed_views.append(
            ProposedView(
                name=proposal.name,
                candidates=[to_candidate_summary(entity) for entity in candidates],
            )
        )

    usage = GenerationUsageTotals(
        input_tokens=structure_result.input_tokens,
        output_tokens=structure_result.output_tokens,
        estimated_cost_usd=structure_result.estimated_cost_usd,
        model=structure_result.model,
        call_count=1,
    )

    return StructureProposalOutcome(
        proposed_views=proposed_views,
        available_custom_cards=available,
        style_hint=style_hint,
        usage=usage,
        notes=notes,
    )


async def generate_from_curated_views(
    *,
    client: DashboardGenerationClient,
    curated_views: list[ProposedView],
    available_custom_cards: dict[str, dict[str, str]],
    style_hint: StyleHint | None,
    valid_entity_ids: set[str],
    max_concurrent_view_calls: int = 3,
) -> DashboardGenerationOutcome:
    notes: list[str] = []
    allowed_types = allowed_custom_type_strings(available_custom_cards)

    semaphore = asyncio.Semaphore(max_concurrent_view_calls)
    active_views: list[ProposedView] = []
    tasks = []
    for view in curated_views:
        if not view.candidates:
            notes.append(f"Ansicht '{view.name}' übersprungen: keine ausgewählten Entitäten.")
            continue
        active_views.append(view)

        async def call(candidates=view.candidates, name=view.name):
            async with semaphore:
                return await client.generate_view_cards(
                    name, candidates, available_custom_cards, style_hint
                )

        tasks.append(call())

    results = await asyncio.gather(*tasks, return_exceptions=True)

    views: list[SectionsView] = []
    total_input = 0
    total_output = 0
    cost_known = True
    total_cost = 0.0
    call_count = 0
    model = ""

    for view, result in zip(active_views, results, strict=True):
        if isinstance(result, DashboardGenerationError):
            log.warning("View '%s' generation failed: %s", view.name, result)
            notes.append(f"Ansicht '{view.name}' konnte nicht generiert werden: {result}")
            continue
        if isinstance(result, BaseException):
            raise result

        call_count += 1
        total_input += result.input_tokens
        total_output += result.output_tokens
        model = result.model
        if result.estimated_cost_usd is None:
            cost_known = False
        elif cost_known:
            total_cost += result.estimated_cost_usd

        views.append(SectionsView(title=view.name, sections=result.output.sections))

    dashboard = GeneratedDashboard(views=views)
    validated_dashboard, report = validate_and_strip(dashboard, valid_entity_ids, allowed_types)

    if report.removed_cards:
        notes.append(f"{report.removed_cards} Karten mit unbekannten Entitäten entfernt.")
    if report.removed_custom_types:
        notes.append(
            f"{report.removed_custom_types} Kartentypen waren nicht verfügbar "
            "und wurden durch native Karten ersetzt."
        )

    usage = GenerationUsageTotals(
        input_tokens=total_input,
        output_tokens=total_output,
        estimated_cost_usd=total_cost if cost_known else None,
        model=model,
        call_count=call_count,
    )

    return DashboardGenerationOutcome(
        dashboard=validated_dashboard, validation=report, usage=usage, notes=notes
    )
