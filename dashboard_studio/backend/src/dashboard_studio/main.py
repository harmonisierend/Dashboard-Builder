from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from dashboard_studio.api import routes_dashboard, routes_design, routes_registry, routes_status
from dashboard_studio.config import get_settings
from dashboard_studio.dashboard.generation_client import DashboardGenerationClient
from dashboard_studio.db.migrate import run_migrations
from dashboard_studio.db.session import make_engine, make_session_factory
from dashboard_studio.design.anthropic_client import AnthropicDesignClient
from dashboard_studio.design.uploads import DesignUploadStore
from dashboard_studio.ha.auth import HAConfigError, resolve_ha_connection
from dashboard_studio.ha.ws_client import HAWebSocketClient
from dashboard_studio.logging import configure_logging
from dashboard_studio.registry.cache import RegistryCache

log = logging.getLogger(__name__)

# The frontend's `npm run build` output is copied here by the Dockerfile's
# frontend-builder stage (Phase D); absent in a bare backend-only checkout.
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)

    # DB/Anthropic/upload init happens before the HA-connection block below
    # and unconditionally: design-token analysis has nothing to do with HA
    # reachability, so a broken/unconfigured HA connection must not make
    # /api/design/* permanently 503.
    run_migrations()
    engine = make_engine(settings.data_dir)
    app.state.db_engine = engine
    app.state.db_session_factory = make_session_factory(engine)
    app.state.anthropic_client = AnthropicDesignClient(settings)
    app.state.dashboard_generation_client = DashboardGenerationClient(settings)
    app.state.upload_store = DesignUploadStore(settings.data_dir)

    try:
        connection = resolve_ha_connection(settings)
    except HAConfigError as exc:
        # No SUPERVISOR_TOKEN and no long-lived-token configured -- nothing
        # meaningful to connect with. app.state.ha_client stays unset, and
        # /api/status correctly 503s with a clear "not initialized" message
        # until the App options are fixed.
        log.error("Cannot resolve Home Assistant connection: %s", exc)
        yield
        await engine.dispose()
        return

    client = HAWebSocketClient(connection)
    try:
        await client.connect()
    except Exception as exc:  # noqa: BLE001 - startup must not crash the App
        # Params were valid but the connect attempt itself failed (HA
        # restarting, network hiccup, etc.) -- keep the disconnected client
        # around so status/UI can show "not connected" and a later request
        # can still retry via registry/refresh once HA is back.
        log.warning("Could not connect to Home Assistant on startup: %s", exc)

    app.state.ha_client = client
    app.state.ha_connection_source = connection.source
    app.state.registry_cache = RegistryCache(client, settings.data_dir)
    app.state.registry_cache.load_persisted()

    yield

    if client.connected:
        await client.close()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="HA Dashboard Studio", lifespan=lifespan)
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    app.include_router(routes_status.router)
    app.include_router(routes_registry.router)
    app.include_router(routes_design.router)
    app.include_router(routes_dashboard.router)

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app


app = create_app()
