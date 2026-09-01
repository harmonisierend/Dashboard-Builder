"""In-memory + on-disk cache for the registry snapshot.

With ~2300 entities, re-fetching the full registry+states set on every UI
load would be wasteful; the snapshot is cached in memory for the process
lifetime and persisted to `/data/registry_snapshot.json` so a restart has
stale-but-immediately-available data while a background refresh runs.

M1 invalidation is manual only (an explicit refresh call) -- push
invalidation via `entity_registry_updated` event subscriptions is deferred
to M2+ to keep this milestone's scope tight.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from dashboard_studio.ha.ws_client import HAWebSocketClient
from dashboard_studio.registry.snapshot import RegistrySnapshot, fetch_snapshot

log = logging.getLogger(__name__)

SNAPSHOT_FILENAME = "registry_snapshot.json"


class RegistryCache:
    def __init__(self, client: HAWebSocketClient, data_dir: Path) -> None:
        self._client = client
        self._path = data_dir / SNAPSHOT_FILENAME
        self._snapshot: RegistrySnapshot | None = None
        self._lock = asyncio.Lock()

    @property
    def snapshot(self) -> RegistrySnapshot | None:
        return self._snapshot

    def load_persisted(self) -> RegistrySnapshot | None:
        """Best-effort load of a previously persisted snapshot, e.g. on startup."""
        if not self._path.is_file():
            return None
        try:
            self._snapshot = RegistrySnapshot.model_validate_json(self._path.read_text())
        except (ValueError, OSError) as exc:
            log.warning("Could not load persisted registry snapshot: %s", exc)
            return None
        return self._snapshot

    async def refresh(self) -> RegistrySnapshot:
        async with self._lock:
            await self._client.ensure_connected()
            snapshot = await fetch_snapshot(self._client)
            self._snapshot = snapshot
            self._persist(snapshot)
            return snapshot

    async def get(self, force_refresh: bool = False) -> RegistrySnapshot:
        if force_refresh or self._snapshot is None:
            return await self.refresh()
        return self._snapshot

    def _persist(self, snapshot: RegistrySnapshot) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(snapshot.model_dump_json())
        except OSError as exc:
            log.warning("Could not persist registry snapshot: %s", exc)
