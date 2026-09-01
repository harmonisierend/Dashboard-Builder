from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from dashboard_studio.api.deps import (
    get_dashboard_generation_client,
    get_db_session,
    get_registry_cache,
)
from dashboard_studio.dashboard.config import GeneratedDashboard, GenerationStrategy, StyleHint
from dashboard_studio.dashboard.generation_client import (
    DashboardGenerationAuthError,
    DashboardGenerationClient,
    DashboardGenerationNotConfiguredError,
    DashboardGenerationRateLimitError,
    DashboardGenerationUpstreamError,
)
from dashboard_studio.dashboard.orchestrator import (
    GenerationUsageTotals,
    ProposedView,
    combine_usage_totals,
    generate_from_curated_views,
    propose_structure,
)
from dashboard_studio.dashboard.scope import (
    CandidateEntitySummary,
    GenerationScope,
    entities_in_scope,
)
from dashboard_studio.dashboard.yaml_export import render_dashboard_yaml
from dashboard_studio.db.models import TokenPreset
from dashboard_studio.design.tokens import DesignTokenSet
from dashboard_studio.ha.ws_client import HAWebSocketError
from dashboard_studio.registry.cache import RegistryCache

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class DashboardScopeRequest(BaseModel):
    area_ids: list[str] = []
    floor_ids: list[str] = []
    strategy: GenerationStrategy
    token_preset_id: str | None = None
    tokens: DesignTokenSet | None = None
    include_diagnostic: bool = False


class DashboardUsageInfo(BaseModel):
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None
    model: str
    call_count: int


class ValidationReportResponse(BaseModel):
    removed_entity_refs: int
    removed_custom_types: int
    removed_cards: int
    removed_sections: int
    removed_views: int
    details: list[str]


class ProposedViewResponse(BaseModel):
    name: str
    candidates: list[CandidateEntitySummary]


class ProposeStructureResponse(BaseModel):
    proposed_views: list[ProposedViewResponse]
    available_custom_cards: dict[str, dict[str, str]]
    style_hint: StyleHint | None
    usage: DashboardUsageInfo
    notes: list[str]


class GenerateDashboardResponse(BaseModel):
    dashboard: GeneratedDashboard
    yaml: str
    validation: ValidationReportResponse
    usage: DashboardUsageInfo
    notes: list[str]


def _to_usage_info(usage: GenerationUsageTotals) -> DashboardUsageInfo:
    return DashboardUsageInfo(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        estimated_cost_usd=usage.estimated_cost_usd,
        model=usage.model,
        call_count=usage.call_count,
    )


def _to_usage_totals(usage: DashboardUsageInfo) -> GenerationUsageTotals:
    return GenerationUsageTotals(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        estimated_cost_usd=usage.estimated_cost_usd,
        model=usage.model,
        call_count=usage.call_count,
    )


async def _resolve_tokens(
    body: DashboardScopeRequest, session: AsyncSession
) -> DesignTokenSet | None:
    if body.token_preset_id is not None and body.tokens is not None:
        raise HTTPException(
            status_code=400, detail="token_preset_id und tokens können nicht gleichzeitig angegeben werden."
        )
    if body.token_preset_id is None:
        return body.tokens
    preset = await session.get(TokenPreset, body.token_preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset nicht gefunden.")
    return DesignTokenSet.model_validate_json(preset.token_json)


@router.post("/propose-structure", response_model=ProposeStructureResponse)
async def propose_structure_route(
    body: DashboardScopeRequest,
    cache: Annotated[RegistryCache, Depends(get_registry_cache)],
    client: Annotated[DashboardGenerationClient, Depends(get_dashboard_generation_client)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProposeStructureResponse:
    if not body.area_ids and not body.floor_ids:
        raise HTTPException(status_code=400, detail="Bitte mindestens einen Bereich oder eine Etage auswählen.")

    tokens = await _resolve_tokens(body, session)

    try:
        snapshot = await cache.get()
    except HAWebSocketError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    scope = GenerationScope(area_ids=body.area_ids, floor_ids=body.floor_ids)
    scoped_entities = entities_in_scope(snapshot.entities, scope, body.include_diagnostic)
    if not scoped_entities:
        raise HTTPException(
            status_code=400, detail="Die ausgewählten Bereiche/Etagen enthalten keine Entitäten."
        )

    try:
        outcome = await propose_structure(
            client=client,
            scoped_entities=scoped_entities,
            lovelace_resources=snapshot.lovelace_resources,
            strategy=body.strategy,
            tokens=tokens,
        )
    except DashboardGenerationNotConfiguredError as exc:
        raise HTTPException(status_code=424, detail=str(exc)) from exc
    except DashboardGenerationAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except DashboardGenerationRateLimitError as exc:
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        raise HTTPException(status_code=429, detail=str(exc), headers=headers) from exc
    except DashboardGenerationUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ProposeStructureResponse(
        proposed_views=[
            ProposedViewResponse(name=view.name, candidates=view.candidates)
            for view in outcome.proposed_views
        ],
        available_custom_cards=outcome.available_custom_cards,
        style_hint=outcome.style_hint,
        usage=_to_usage_info(outcome.usage),
        notes=outcome.notes,
    )


class CuratedViewRequest(BaseModel):
    name: str
    candidates: list[CandidateEntitySummary]


class GenerateDashboardRequest(BaseModel):
    area_ids: list[str] = []
    floor_ids: list[str] = []
    include_diagnostic: bool = False
    curated_views: list[CuratedViewRequest]
    available_custom_cards: dict[str, dict[str, str]]
    style_hint: StyleHint | None = None
    phase1_usage: DashboardUsageInfo


@router.post("/generate", response_model=GenerateDashboardResponse)
async def generate_dashboard_route(
    body: GenerateDashboardRequest,
    cache: Annotated[RegistryCache, Depends(get_registry_cache)],
    client: Annotated[DashboardGenerationClient, Depends(get_dashboard_generation_client)],
) -> GenerateDashboardResponse:
    if not body.curated_views:
        raise HTTPException(status_code=400, detail="Bitte mindestens eine Ansicht behalten.")

    try:
        snapshot = await cache.get()
    except HAWebSocketError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Re-fetch and re-derive valid_entity_ids from the live registry rather
    # than trusting the client-echoed candidate lists as ground truth -- this
    # is the independent re-validation that keeps the M3 hard entity-ID
    # guarantee intact regardless of what a client sends back in
    # curated_views. Anything not actually in scope is silently stripped by
    # validate_and_strip() inside generate_from_curated_views(), exactly like
    # a hallucinated entity is.
    scope = GenerationScope(area_ids=body.area_ids, floor_ids=body.floor_ids)
    scoped_entities = entities_in_scope(snapshot.entities, scope, body.include_diagnostic)
    valid_entity_ids = {entity.entity_id for entity in scoped_entities}

    try:
        outcome = await generate_from_curated_views(
            client=client,
            curated_views=[
                ProposedView(name=view.name, candidates=view.candidates) for view in body.curated_views
            ],
            available_custom_cards=body.available_custom_cards,
            style_hint=body.style_hint,
            valid_entity_ids=valid_entity_ids,
        )
    except DashboardGenerationNotConfiguredError as exc:
        raise HTTPException(status_code=424, detail=str(exc)) from exc
    except DashboardGenerationAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except DashboardGenerationRateLimitError as exc:
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        raise HTTPException(status_code=429, detail=str(exc), headers=headers) from exc
    except DashboardGenerationUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    usage = combine_usage_totals(_to_usage_totals(body.phase1_usage), outcome.usage)

    return GenerateDashboardResponse(
        dashboard=outcome.dashboard,
        yaml=render_dashboard_yaml(outcome.dashboard),
        validation=ValidationReportResponse(
            removed_entity_refs=outcome.validation.removed_entity_refs,
            removed_custom_types=outcome.validation.removed_custom_types,
            removed_cards=outcome.validation.removed_cards,
            removed_sections=outcome.validation.removed_sections,
            removed_views=outcome.validation.removed_views,
            details=outcome.validation.details,
        ),
        usage=_to_usage_info(usage),
        notes=outcome.notes,
    )
