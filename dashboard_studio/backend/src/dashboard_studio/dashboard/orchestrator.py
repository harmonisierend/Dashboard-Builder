"""Orchestrates the two-phase dashboard generation call and the mandatory
entity-ID / custom-card-type validation gate.

Phase 1 (structure) errors propagate to the caller unchanged -- there is no
dashboard to build at all if that call fails. Phase 2 (per-view card
generation) failures are isolated per view: a transient failure generating
one view's cards must not void the whole response, so each is caught,
logged, and turned into a user-facing note instead.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from dashboard_studio.dashboard.config import (
    GeneratedDashboard,
    GenerationStrategy,
    SectionsView,
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
    ViewProposal,
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


@dataclass
class DashboardGenerationOutcome:
    dashboard: GeneratedDashboard
    validation: ValidationReport
    usage: GenerationUsageTotals
    notes: list[str]


async def generate_dashboard(
    *,
    client: DashboardGenerationClient,
    scoped_entities: list[EntityRecord],
    lovelace_resources: list[LovelaceResource],
    strategy: GenerationStrategy,
    tokens: DesignTokenSet | None,
    max_concurrent_view_calls: int = 3,
) -> DashboardGenerationOutcome:
    notes: list[str] = []

    families = detect_installed_custom_card_families(lovelace_resources)
    available = available_custom_cards(families)
    allowed_types = allowed_custom_type_strings(available)
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
        notes.append(
            f"{len(proposals)} Ansichten vorgeschlagen, auf {MAX_PROPOSED_VIEWS} begrenzt."
        )
        proposals = proposals[:MAX_PROPOSED_VIEWS]

    semaphore = asyncio.Semaphore(max_concurrent_view_calls)
    active_proposals: list[ViewProposal] = []
    tasks = []
    for proposal in proposals:
        candidates = resolve_view_entities(scoped_entities, proposal.selector)
        if not candidates:
            notes.append(
                f"Ansicht '{proposal.name}' übersprungen: keine passenden Entitäten im Scope."
            )
            continue
        candidate_summaries = [to_candidate_summary(entity) for entity in candidates]
        active_proposals.append(proposal)

        async def call(candidate_summaries=candidate_summaries, name=proposal.name):
            async with semaphore:
                return await client.generate_view_cards(name, candidate_summaries, available, style_hint)

        tasks.append(call())

    results = await asyncio.gather(*tasks, return_exceptions=True)

    views: list[SectionsView] = []
    total_input = structure_result.input_tokens
    total_output = structure_result.output_tokens
    cost_known = structure_result.estimated_cost_usd is not None
    total_cost = structure_result.estimated_cost_usd or 0.0
    call_count = 1

    for proposal, result in zip(active_proposals, results, strict=True):
        if isinstance(result, DashboardGenerationError):
            log.warning("View '%s' generation failed: %s", proposal.name, result)
            notes.append(f"Ansicht '{proposal.name}' konnte nicht generiert werden: {result}")
            continue
        if isinstance(result, BaseException):
            raise result

        call_count += 1
        total_input += result.input_tokens
        total_output += result.output_tokens
        if result.estimated_cost_usd is None:
            cost_known = False
        elif cost_known:
            total_cost += result.estimated_cost_usd

        views.append(SectionsView(title=proposal.name, sections=result.output.sections))

    dashboard = GeneratedDashboard(views=views)
    valid_ids = {entity.entity_id for entity in scoped_entities}
    validated_dashboard, report = validate_and_strip(dashboard, valid_ids, allowed_types)

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
        model=structure_result.model,
        call_count=call_count,
    )

    return DashboardGenerationOutcome(
        dashboard=validated_dashboard, validation=report, usage=usage, notes=notes
    )
