"""Resolve how to authenticate to Home Assistant's WebSocket API.

Inside the real App container, Supervisor injects SUPERVISOR_TOKEN and the
Core WebSocket is reachable at ws://supervisor/core/websocket via the
Supervisor proxy. Outside the sandbox (local development against a real or
test HA instance), that variable is absent and a long-lived access token
configured via App options is used instead against `settings.ha_url`.

The long-lived-token path must only ever activate when SUPERVISOR_TOKEN is
missing entirely -- never preferred when the Supervisor token is present --
so a misconfigured fallback token can't quietly widen the auth surface.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Literal

from dashboard_studio.config import Settings

log = logging.getLogger(__name__)

SUPERVISOR_WS_URL = "ws://supervisor/core/websocket"


class HAConfigError(RuntimeError):
    """Raised when no usable HA credentials/connection info are available."""


@dataclass(frozen=True)
class HAConnectionParams:
    ws_url: str
    token: str
    source: Literal["supervisor", "long_lived_token"]


def resolve_ha_connection(settings: Settings) -> HAConnectionParams:
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
    if supervisor_token:
        return HAConnectionParams(
            ws_url=SUPERVISOR_WS_URL, token=supervisor_token, source="supervisor"
        )

    if not settings.long_lived_token:
        raise HAConfigError(
            "No SUPERVISOR_TOKEN in the environment and no long_lived_token configured. "
            "Inside the App container SUPERVISOR_TOKEN is set automatically; for local "
            "development outside the sandbox, configure a long-lived access token."
        )

    log.warning(
        "SUPERVISOR_TOKEN not present -- falling back to the configured long-lived "
        "access token. This is expected only in local development, never inside the "
        "real App container."
    )
    ws_url = settings.ha_url.rstrip("/").replace("http", "ws", 1) + "/api/websocket"
    return HAConnectionParams(ws_url=ws_url, token=settings.long_lived_token, source="long_lived_token")
