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
from dashboard_studio.dashboard.config import GeneratedDashboard, GenerationStrategy
from dashboard_studio.dashboard.generation_client import (
    DashboardGenerationAuthError,
    DashboardGenerationClient,
    DashboardGenerationNotConfiguredError,
    DashboardGenerationRateLimitError,
    DashboardGenerationUpstreamError,
)
from dashboard_studio.dashboard.orchestrator import generate_dashboard
from dashboard_studio.dashboard.scope import GenerationScope, entities_in_scope
from dashboard_studio.dashboard.yaml_export import render_dashboard_yaml
from dashboard_studio.db.models import TokenPreset
from dashboard_studio.design.tokens import DesignTokenSet
from dashboard_studio.ha.ws_client import HAWebSocketError
from dashboard_studio.registry.cache import RegistryCache

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class GenerateDashboardRequest(BaseModel):
    area_ids: list[str] = []
    floor_ids: list[str] = []
    strategy: GenerationStrategy
    token_preset_id: str | None = None
    tokens: DesignTokenSet | None = None
    include_diagnostic: bool = False


class ValidationReportResponse(BaseModel):
    removed_entity_refs: int
    removed_custom_types: int
    removed_cards: int
    removed_sections: int
    removed_views: int
    details: list[str]


class DashboardUsageInfo(BaseModel):
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None
    model: str
    call_count: int


class GenerateDashboardResponse(BaseModel):
    dashboard: GeneratedDashboard
    yaml: str
    validation: ValidationReportResponse
    usage: DashboardUsageInfo
    notes: list[str]


@router.post("/generate", response_model=GenerateDashboardResponse)
async def generate_dashboard_route(
    body: GenerateDashboardRequest,
    cache: Annotated[RegistryCache, Depends(get_registry_cache)],
    client: Annotated[DashboardGenerationClient, Depends(get_dashboard_generation_client)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GenerateDashboardResponse:
    if not body.area_ids and not body.floor_ids:
        raise HTTPException(status_code=400, detail="Bitte mindestens einen Bereich oder eine Etage auswählen.")
    if body.token_preset_id is not None and body.tokens is not None:
        raise HTTPException(
            status_code=400, detail="token_preset_id und tokens können nicht gleichzeitig angegeben werden."
        )

    tokens: DesignTokenSet | None = body.tokens
    if body.token_preset_id is not None:
        preset = await session.get(TokenPreset, body.token_preset_id)
        if preset is None:
            raise HTTPException(status_code=404, detail="Preset nicht gefunden.")
        tokens = DesignTokenSet.model_validate_json(preset.token_json)

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
        outcome = await generate_dashboard(
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
        usage=DashboardUsageInfo(
            input_tokens=outcome.usage.input_tokens,
            output_tokens=outcome.usage.output_tokens,
            estimated_cost_usd=outcome.usage.estimated_cost_usd,
            model=outcome.usage.model,
            call_count=outcome.usage.call_count,
        ),
        notes=outcome.notes,
    )
