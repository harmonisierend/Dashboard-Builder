from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dashboard_studio.db.session import session_scope
from dashboard_studio.design.anthropic_client import AnthropicDesignClient
from dashboard_studio.design.uploads import DesignUploadStore
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


def get_db_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] | None = getattr(
        request.app.state, "db_session_factory", None
    )
    if factory is None:
        raise HTTPException(status_code=503, detail="Datenbank noch nicht initialisiert")
    return factory


async def get_db_session(
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_db_session_factory)],
) -> AsyncIterator[AsyncSession]:
    async for session in session_scope(factory):
        yield session


def get_anthropic_client(request: Request) -> AnthropicDesignClient:
    client: AnthropicDesignClient | None = getattr(request.app.state, "anthropic_client", None)
    if client is None:
        raise HTTPException(status_code=503, detail="Anthropic-Client noch nicht initialisiert")
    return client


def get_upload_store(request: Request) -> DesignUploadStore:
    store: DesignUploadStore | None = getattr(request.app.state, "upload_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Upload-Speicher noch nicht initialisiert")
    return store
