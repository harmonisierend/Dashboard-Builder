from __future__ import annotations

from pathlib import Path
from typing import Any

from dashboard_studio.registry.cache import RegistryCache


class FakeClient:
    """Minimal stand-in for HAWebSocketClient's registry-fetch surface."""

    def __init__(self) -> None:
        self.connected = False
        self.ensure_connected_calls = 0
        self.entity_registry_calls = 0

    async def ensure_connected(self) -> None:
        self.ensure_connected_calls += 1
        self.connected = True

    async def list_entity_registry(self) -> list[dict[str, Any]]:
        self.entity_registry_calls += 1
        return [{"entity_id": "light.a"}]

    async def list_device_registry(self) -> list[dict[str, Any]]:
        return []

    async def list_area_registry(self) -> list[dict[str, Any]]:
        return []

    async def list_floor_registry(self) -> list[dict[str, Any]]:
        return []

    async def list_label_registry(self) -> list[dict[str, Any]]:
        return []

    async def get_states(self) -> list[dict[str, Any]]:
        return [{"entity_id": "light.a", "state": "on", "attributes": {}}]

    async def list_lovelace_resources(self) -> list[dict[str, Any]]:
        return []


async def test_refresh_fetches_connects_and_persists(tmp_path: Path) -> None:
    client = FakeClient()
    cache = RegistryCache(client, tmp_path)  # type: ignore[arg-type]

    snapshot = await cache.refresh()

    assert snapshot.entity_count == 1
    assert client.connected is True
    assert client.ensure_connected_calls == 1
    assert (tmp_path / "registry_snapshot.json").is_file()


async def test_get_reuses_cached_snapshot(tmp_path: Path) -> None:
    client = FakeClient()
    cache = RegistryCache(client, tmp_path)  # type: ignore[arg-type]
    await cache.refresh()

    await cache.get()

    assert client.entity_registry_calls == 1  # only the initial refresh actually fetched


async def test_get_force_refresh_refetches(tmp_path: Path) -> None:
    client = FakeClient()
    cache = RegistryCache(client, tmp_path)  # type: ignore[arg-type]
    await cache.refresh()

    await cache.get(force_refresh=True)

    assert client.entity_registry_calls == 2


async def test_get_without_prior_refresh_fetches_once(tmp_path: Path) -> None:
    client = FakeClient()
    cache = RegistryCache(client, tmp_path)  # type: ignore[arg-type]

    snapshot = await cache.get()

    assert snapshot.entity_count == 1
    assert client.entity_registry_calls == 1


async def test_load_persisted_round_trips_across_cache_instances(tmp_path: Path) -> None:
    client_a = RegistryCache(FakeClient(), tmp_path)  # type: ignore[arg-type]
    await client_a.refresh()

    cache_b = RegistryCache(FakeClient(), tmp_path)  # type: ignore[arg-type]
    loaded = cache_b.load_persisted()

    assert loaded is not None
    assert loaded.entity_count == 1
    assert cache_b.snapshot is loaded


def test_load_persisted_returns_none_when_no_file_exists(tmp_path: Path) -> None:
    cache = RegistryCache(FakeClient(), tmp_path)  # type: ignore[arg-type]

    assert cache.load_persisted() is None
