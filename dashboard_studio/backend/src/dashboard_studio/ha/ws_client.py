"""Async client for the Home Assistant WebSocket API.

The wire transport is behind a small `Transport` protocol so unit tests can
substitute an in-process fake implementing the HA auth handshake and canned
command/response pairs -- no real HA instance needed to test this module.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Protocol

from dashboard_studio.ha.auth import HAConnectionParams

log = logging.getLogger(__name__)

DEFAULT_COMMAND_TIMEOUT = 30.0
# get_states on a ~2300-entity instance easily exceeds the websockets
# library's 1MB default frame-size cap; give plenty of headroom.
MAX_MESSAGE_SIZE = 32 * 1024 * 1024


class HAWebSocketError(RuntimeError):
    """Base class for HA WebSocket client errors."""


class HAAuthError(HAWebSocketError):
    """Raised when the HA server rejects our access token."""


class HACommandError(HAWebSocketError):
    """Raised when a command's `result` message has success=false."""


class Transport(Protocol):
    async def connect(self, url: str) -> None: ...
    async def send(self, message: dict[str, Any]) -> None: ...
    async def receive(self) -> dict[str, Any]: ...
    async def close(self) -> None: ...


class WebsocketsTransport:
    """Real transport, backed by the `websockets` library."""

    def __init__(self) -> None:
        self._ws: Any = None

    async def connect(self, url: str) -> None:
        import websockets

        self._ws = await websockets.connect(url, max_size=MAX_MESSAGE_SIZE)

    async def send(self, message: dict[str, Any]) -> None:
        if self._ws is None:
            raise HAWebSocketError("Transport not connected")
        await self._ws.send(json.dumps(message))

    async def receive(self) -> dict[str, Any]:
        if self._ws is None:
            raise HAWebSocketError("Transport not connected")
        raw = await self._ws.recv()
        return json.loads(raw)

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None


class HAWebSocketClient:
    """Typed wrapper over the HA WebSocket command/result protocol.

    Handles the auth handshake, per-command id correlation via a background
    reader task (so concurrent `asyncio.gather`ed commands work correctly),
    and per-command timeouts.
    """

    def __init__(
        self,
        connection: HAConnectionParams,
        transport: Transport | None = None,
        command_timeout: float = DEFAULT_COMMAND_TIMEOUT,
    ) -> None:
        self._connection = connection
        self._transport = transport or WebsocketsTransport()
        self._command_timeout = command_timeout
        self._next_id = 1
        self._connected = False
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._reader_task: asyncio.Task[None] | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        # Transport-level failures (refused connection, DNS, TLS, dropped
        # socket mid-handshake) surface as raw exceptions from the transport
        # implementation -- normalize them to HAWebSocketError so callers
        # (e.g. the /api/registry route) can catch one error type instead of
        # having to know about `websockets`' exception hierarchy.
        try:
            await self._transport.connect(self._connection.ws_url)
            first = await self._transport.receive()
        except HAWebSocketError:
            raise
        except Exception as exc:
            raise HAWebSocketError(f"Could not connect to Home Assistant: {exc}") from exc

        if first.get("type") != "auth_required":
            raise HAWebSocketError(f"Unexpected first message from HA: {first!r}")

        try:
            await self._transport.send({"type": "auth", "access_token": self._connection.token})
            auth_response = await self._transport.receive()
        except HAWebSocketError:
            raise
        except Exception as exc:
            raise HAWebSocketError(f"Could not complete Home Assistant auth handshake: {exc}") from exc

        if auth_response.get("type") == "auth_invalid":
            raise HAAuthError(auth_response.get("message", "Authentication rejected by Home Assistant"))
        if auth_response.get("type") != "auth_ok":
            raise HAWebSocketError(f"Unexpected auth response from HA: {auth_response!r}")

        self._connected = True
        self._reader_task = asyncio.ensure_future(self._reader_loop())
        log.info("Connected to Home Assistant WebSocket API (source=%s)", self._connection.source)

    async def ensure_connected(self) -> None:
        """(Re)connect if not currently connected -- used before a manual refresh."""
        if not self._connected:
            await self.connect()

    async def close(self) -> None:
        self._connected = False
        if self._reader_task is not None:
            self._reader_task.cancel()
            self._reader_task = None
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()
        await self._transport.close()

    async def _reader_loop(self) -> None:
        try:
            while True:
                message = await self._transport.receive()
                msg_id = message.get("id")
                if msg_id is not None and msg_id in self._pending:
                    future = self._pending.pop(msg_id)
                    if not future.done():
                        future.set_result(message)
                # `event` messages (subscriptions) are ignored in M1 -- no
                # subscriptions are made yet.
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - any transport failure must fail pending commands
            log.warning("HA WebSocket reader loop stopped: %s", exc)
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(HAWebSocketError(f"Connection lost: {exc}"))
            self._pending.clear()

    async def send_command(self, command_type: str, **kwargs: Any) -> Any:
        if not self._connected:
            raise HAWebSocketError("Not connected -- call connect() first")

        command_id = self._next_id
        self._next_id += 1

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[command_id] = future

        message = {"id": command_id, "type": command_type, **kwargs}
        await self._transport.send(message)

        try:
            response = await asyncio.wait_for(future, timeout=self._command_timeout)
        except TimeoutError as exc:
            self._pending.pop(command_id, None)
            raise HAWebSocketError(
                f"Timed out waiting for response to {command_type!r} (id={command_id})"
            ) from exc

        if not response.get("success", False):
            error = response.get("error") or {}
            raise HACommandError(
                f"{command_type} failed: {error.get('code', 'unknown')}: {error.get('message', '')}"
            )
        return response.get("result")

    # -- Typed convenience wrappers -----------------------------------

    async def list_entity_registry(self) -> list[dict[str, Any]]:
        return await self.send_command("config/entity_registry/list")

    async def list_device_registry(self) -> list[dict[str, Any]]:
        return await self.send_command("config/device_registry/list")

    async def list_area_registry(self) -> list[dict[str, Any]]:
        return await self.send_command("config/area_registry/list")

    async def list_floor_registry(self) -> list[dict[str, Any]]:
        return await self.send_command("config/floor_registry/list")

    async def list_label_registry(self) -> list[dict[str, Any]]:
        return await self.send_command("config/label_registry/list")

    async def get_states(self) -> list[dict[str, Any]]:
        return await self.send_command("get_states")

    async def list_lovelace_resources(self) -> list[dict[str, Any]]:
        return await self.send_command("lovelace/resources/list")

    # -- Stubs for M6 (implemented against real command shapes now so the
    # M6 "write to HA" milestone doesn't have to reverse-engineer them) --

    async def list_lovelace_dashboards(self) -> list[dict[str, Any]]:
        return await self.send_command("lovelace/dashboards/list")

    async def get_lovelace_config(self, url_path: str | None = None) -> Any:
        kwargs = {"url_path": url_path} if url_path else {}
        return await self.send_command("lovelace/config", **kwargs)

    async def save_lovelace_config(self, config: dict[str, Any], url_path: str | None = None) -> None:
        kwargs: dict[str, Any] = {"config": config}
        if url_path:
            kwargs["url_path"] = url_path
        await self.send_command("lovelace/config/save", **kwargs)

    async def create_lovelace_dashboard(
        self,
        url_path: str,
        title: str,
        *,
        icon: str | None = None,
        show_in_sidebar: bool = True,
        require_admin: bool = False,
    ) -> dict[str, Any]:
        return await self.send_command(
            "lovelace/dashboards/create",
            url_path=url_path,
            title=title,
            icon=icon,
            show_in_sidebar=show_in_sidebar,
            require_admin=require_admin,
        )
