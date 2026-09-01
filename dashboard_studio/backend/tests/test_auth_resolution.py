from __future__ import annotations

import pytest

from dashboard_studio.config import Settings
from dashboard_studio.ha.auth import HAConfigError, resolve_ha_connection


def make_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "long_lived_token": "",
        "ha_url": "http://homeassistant.local:8123",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def test_uses_supervisor_token_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERVISOR_TOKEN", "super-secret")
    settings = make_settings(long_lived_token="should-be-ignored")

    connection = resolve_ha_connection(settings)

    assert connection.source == "supervisor"
    assert connection.token == "super-secret"
    assert connection.ws_url == "ws://supervisor/core/websocket"


def test_falls_back_to_long_lived_token_when_supervisor_token_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    settings = make_settings(long_lived_token="llt-token", ha_url="http://192.168.1.10:8123")

    connection = resolve_ha_connection(settings)

    assert connection.source == "long_lived_token"
    assert connection.token == "llt-token"
    assert connection.ws_url == "ws://192.168.1.10:8123/api/websocket"


def test_https_ha_url_maps_to_wss(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    settings = make_settings(long_lived_token="llt-token", ha_url="https://my-ha.example.com")

    connection = resolve_ha_connection(settings)

    assert connection.ws_url == "wss://my-ha.example.com/api/websocket"


def test_raises_when_neither_is_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    settings = make_settings(long_lived_token="")

    with pytest.raises(HAConfigError):
        resolve_ha_connection(settings)


def test_never_prefers_fallback_when_supervisor_token_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERVISOR_TOKEN", "real-token")
    settings = make_settings(long_lived_token="do-not-use-me")

    connection = resolve_ha_connection(settings)

    assert connection.source == "supervisor"
    assert connection.token == "real-token"
