from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from dashboard_studio.ha.auth import HAConnectionParams
from dashboard_studio.ha.ws_client import (
    HAAuthError,
    HACommandError,
    HAWebSocketClient,
    HAWebSocketError,
)

Responder = Callable[[dict[str, Any]], dict[str, Any] | None]


class FakeTransport:
    """In-process fake implementing the HA WS auth handshake + command/result protocol.

    `responder(message) -> response | None` is called synchronously from
    `send()` and its return value is queued for the reader loop's next
    `receive()` -- this naturally supports concurrent (gather'd) commands
    since each command's response is queued independently, keyed by the id
    the responder echoes back.
    """

    def __init__(self, responder: Responder) -> None:
        self._responder = responder
        self.sent: list[dict[str, Any]] = []
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def connect(self, url: str) -> None:
        self.url = url
        await self._queue.put({"type": "auth_required"})

    async def send(self, message: dict[str, Any]) -> None:
        self.sent.append(message)
        response = self._responder(message)
        if response is not None:
            await self._queue.put(response)

    async def receive(self) -> dict[str, Any]:
        return await self._queue.get()

    async def close(self) -> None:
        pass


def ok_auth_responder(result_for_command: dict[str, Any] | None = None) -> Responder:
    def responder(message: dict[str, Any]) -> dict[str, Any] | None:
        if message["type"] == "auth":
            if message["access_token"] == "good-token":
                return {"type": "auth_ok"}
            return {"type": "auth_invalid", "message": "invalid token"}
        result = (result_for_command or {}).get(message["type"], {"ok": True})
        return {"id": message["id"], "type": "result", "success": True, "result": result}

    return responder


@pytest.fixture
def connection_params() -> HAConnectionParams:
    return HAConnectionParams(ws_url="ws://fake", token="good-token", source="supervisor")


async def test_connect_success(connection_params: HAConnectionParams) -> None:
    transport = FakeTransport(ok_auth_responder())
    client = HAWebSocketClient(connection_params, transport=transport)

    await client.connect()

    assert client.connected is True
    await client.close()


async def test_connect_auth_invalid() -> None:
    connection = HAConnectionParams(ws_url="ws://fake", token="bad-token", source="supervisor")
    transport = FakeTransport(ok_auth_responder())
    client = HAWebSocketClient(connection, transport=transport)

    with pytest.raises(HAAuthError):
        await client.connect()

    assert client.connected is False


async def test_send_command_returns_result(connection_params: HAConnectionParams) -> None:
    transport = FakeTransport(ok_auth_responder({"get_states": [{"entity_id": "light.x"}]}))
    client = HAWebSocketClient(connection_params, transport=transport)
    await client.connect()

    result = await client.get_states()

    assert result == [{"entity_id": "light.x"}]
    await client.close()


async def test_command_ids_increment(connection_params: HAConnectionParams) -> None:
    transport = FakeTransport(ok_auth_responder())
    client = HAWebSocketClient(connection_params, transport=transport)
    await client.connect()

    await client.send_command("get_states")
    await client.send_command("get_states")

    ids = [m["id"] for m in transport.sent if m["type"] == "get_states"]
    assert ids == [1, 2]
    await client.close()


async def test_command_error_raises(connection_params: HAConnectionParams) -> None:
    def responder(message: dict[str, Any]) -> dict[str, Any]:
        if message["type"] == "auth":
            return {"type": "auth_ok"}
        return {
            "id": message["id"],
            "type": "result",
            "success": False,
            "error": {"code": "not_found", "message": "nope"},
        }

    transport = FakeTransport(responder)
    client = HAWebSocketClient(connection_params, transport=transport)
    await client.connect()

    with pytest.raises(HACommandError):
        await client.send_command("config/entity_registry/list")
    await client.close()


async def test_command_timeout(connection_params: HAConnectionParams) -> None:
    def responder(message: dict[str, Any]) -> dict[str, Any] | None:
        if message["type"] == "auth":
            return {"type": "auth_ok"}
        return None  # never respond -> should time out

    transport = FakeTransport(responder)
    client = HAWebSocketClient(connection_params, transport=transport, command_timeout=0.05)
    await client.connect()

    with pytest.raises(HAWebSocketError):
        await client.send_command("get_states")
    await client.close()


async def test_concurrent_commands_correlate_correctly(
    connection_params: HAConnectionParams,
) -> None:
    result_map = {
        "config/entity_registry/list": [{"entity_id": "light.a"}],
        "get_states": [{"entity_id": "light.a", "state": "on"}],
        "lovelace/resources/list": [{"id": "1", "type": "module", "url": "/x.js"}],
    }
    transport = FakeTransport(ok_auth_responder(result_map))
    client = HAWebSocketClient(connection_params, transport=transport)
    await client.connect()

    entities, states, resources = await asyncio.gather(
        client.list_entity_registry(),
        client.get_states(),
        client.list_lovelace_resources(),
    )

    assert entities == result_map["config/entity_registry/list"]
    assert states == result_map["get_states"]
    assert resources == result_map["lovelace/resources/list"]
    await client.close()


async def test_not_connected_raises_before_connect(connection_params: HAConnectionParams) -> None:
    transport = FakeTransport(ok_auth_responder())
    client = HAWebSocketClient(connection_params, transport=transport)

    with pytest.raises(HAWebSocketError):
        await client.send_command("get_states")


class RefusingTransport:
    """Simulates a raw transport-level failure (e.g. connection refused)."""

    async def connect(self, url: str) -> None:
        raise ConnectionRefusedError("refused")

    async def send(self, message: dict[str, Any]) -> None:  # pragma: no cover - unreachable
        raise AssertionError("should never send on a transport that failed to connect")

    async def receive(self) -> dict[str, Any]:  # pragma: no cover - unreachable
        raise AssertionError("should never receive on a transport that failed to connect")

    async def close(self) -> None:
        pass


async def test_raw_transport_connect_failure_wraps_to_ha_websocket_error(
    connection_params: HAConnectionParams,
) -> None:
    client = HAWebSocketClient(connection_params, transport=RefusingTransport())

    with pytest.raises(HAWebSocketError):
        await client.connect()

    assert client.connected is False
