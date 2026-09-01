from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from dashboard_studio.api.deps import get_ha_client, get_registry_cache
from dashboard_studio.ha.ws_client import HAWebSocketClient
from dashboard_studio.registry.cache import RegistryCache

router = APIRouter(prefix="/api", tags=["status"])


class StatusResponse(BaseModel):
    ha_connected: bool
    ha_connection_source: str | None
    last_registry_refresh: datetime | None
    entity_count: int | None
    area_count: int | None


@router.get("/status", response_model=StatusResponse)
def get_status(
    request: Request,
    cache: Annotated[RegistryCache, Depends(get_registry_cache)],
    client: Annotated[HAWebSocketClient, Depends(get_ha_client)],
) -> StatusResponse:
    snapshot = cache.snapshot
    return StatusResponse(
        ha_connected=client.connected,
        ha_connection_source=getattr(request.app.state, "ha_connection_source", None),
        last_registry_refresh=snapshot.fetched_at if snapshot else None,
        entity_count=snapshot.entity_count if snapshot else None,
        area_count=snapshot.area_count if snapshot else None,
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
