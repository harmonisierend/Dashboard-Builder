from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dashboard_studio.api.deps import get_registry_cache
from dashboard_studio.ha.ws_client import HAWebSocketError
from dashboard_studio.registry.cache import RegistryCache
from dashboard_studio.registry.filters import filter_entities
from dashboard_studio.registry.snapshot import EntityRecord, RegistrySnapshot

router = APIRouter(prefix="/api/registry", tags=["registry"])


class RegistryResponse(BaseModel):
    fetched_at: str
    entities: list[EntityRecord]
    filtered_entities: list[EntityRecord]
    areas: list[dict[str, Any]]
    floors: list[dict[str, Any]]
    labels: list[dict[str, Any]]
    lovelace_resources: list[dict[str, Any]]


def _to_response(snapshot: RegistrySnapshot, include_diagnostic: bool) -> RegistryResponse:
    return RegistryResponse(
        fetched_at=snapshot.fetched_at.isoformat(),
        entities=snapshot.entities,
        filtered_entities=filter_entities(snapshot.entities, include_diagnostic),
        areas=[a.model_dump() for a in snapshot.areas],
        floors=[f.model_dump() for f in snapshot.floors],
        labels=[l.model_dump() for l in snapshot.labels],
        lovelace_resources=[r.model_dump() for r in snapshot.lovelace_resources],
    )


@router.get("", response_model=RegistryResponse)
async def get_registry(
    cache: Annotated[RegistryCache, Depends(get_registry_cache)],
    include_diagnostic: bool = False,
) -> RegistryResponse:
    try:
        snapshot = await cache.get()
    except HAWebSocketError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _to_response(snapshot, include_diagnostic)


@router.post("/refresh", response_model=RegistryResponse)
async def refresh_registry(
    cache: Annotated[RegistryCache, Depends(get_registry_cache)],
    include_diagnostic: bool = False,
) -> RegistryResponse:
    try:
        snapshot = await cache.refresh()
    except HAWebSocketError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _to_response(snapshot, include_diagnostic)
