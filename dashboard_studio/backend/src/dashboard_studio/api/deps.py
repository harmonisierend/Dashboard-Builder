from __future__ import annotations

from fastapi import HTTPException, Request

from dashboard_studio.ha.ws_client import HAWebSocketClient
from dashboard_studio.registry.cache import RegistryCache


def get_registry_cache(request: Request) -> RegistryCache:
    cache: RegistryCache | None = getattr(request.app.state, "registry_cache", None)
    if cache is None:
        raise HTTPException(status_code=503, detail="Registry cache not initialized yet")
    return cache


def get_ha_client(request: Request) -> HAWebSocketClient:
    client: HAWebSocketClient | None = getattr(request.app.state, "ha_client", None)
    if client is None:
        raise HTTPException(status_code=503, detail="Home Assistant connection not initialized yet")
    return client
