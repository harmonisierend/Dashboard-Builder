"""Fetch and denormalize a registry snapshot from Home Assistant.

Joins entity/device/area/floor registries and current states into one
entity-centric structure so the rest of the app (filters, UI, later the
dashboard generator) never has to re-resolve device->area->floor chains.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from dashboard_studio.ha.models import (
    AreaRegistryEntry,
    DeviceRegistryEntry,
    EntityRegistryEntry,
    FloorRegistryEntry,
    LabelRegistryEntry,
    LovelaceResource,
    StateObject,
)
from dashboard_studio.ha.ws_client import HAWebSocketClient

UNAVAILABLE_STATES = {"unavailable", "unknown"}


class EntityRecord(BaseModel):
    entity_id: str
    domain: str
    name: str
    platform: str | None = None
    device_id: str | None = None
    device_name: str | None = None
    area_id: str | None = None
    area_name: str | None = None
    floor_id: str | None = None
    floor_name: str | None = None
    labels: list[str] = []
    entity_category: str | None = None
    hidden_by: str | None = None
    disabled_by: str | None = None
    state: str | None = None
    available: bool
    attributes: dict[str, Any] = {}


class RegistrySnapshot(BaseModel):
    fetched_at: datetime
    entities: list[EntityRecord]
    areas: list[AreaRegistryEntry]
    floors: list[FloorRegistryEntry]
    labels: list[LabelRegistryEntry]
    lovelace_resources: list[LovelaceResource]

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def area_count(self) -> int:
        return len(self.areas)


def _resolve_friendly_name(
    entry: EntityRegistryEntry, device: DeviceRegistryEntry | None, state: StateObject | None
) -> str:
    if entry.name:
        return entry.name
    if device is not None and (device.name_by_user or device.name):
        return device.name_by_user or device.name or entry.entity_id
    if state is not None:
        attr_name = state.attributes.get("friendly_name")
        if attr_name:
            return str(attr_name)
    return entry.entity_id


def _build_entity_record(
    raw_entry: dict[str, Any],
    devices_by_id: dict[str, DeviceRegistryEntry],
    areas_by_id: dict[str, AreaRegistryEntry],
    floors_by_id: dict[str, FloorRegistryEntry],
    states_by_entity: dict[str, StateObject],
) -> EntityRecord:
    entry = EntityRegistryEntry(**raw_entry)
    device = devices_by_id.get(entry.device_id) if entry.device_id else None
    # An entity's own area_id wins; otherwise it inherits its device's area.
    area_id = entry.area_id or (device.area_id if device else None)
    area = areas_by_id.get(area_id) if area_id else None
    floor = floors_by_id.get(area.floor_id) if area and area.floor_id else None
    state = states_by_entity.get(entry.entity_id)
    domain = entry.entity_id.split(".", 1)[0]
    device_name = None
    if device is not None:
        device_name = device.name_by_user or device.name

    return EntityRecord(
        entity_id=entry.entity_id,
        domain=domain,
        name=_resolve_friendly_name(entry, device, state),
        platform=entry.platform,
        device_id=entry.device_id,
        device_name=device_name,
        area_id=area.area_id if area else None,
        area_name=area.name if area else None,
        floor_id=floor.floor_id if floor else None,
        floor_name=floor.name if floor else None,
        labels=entry.labels,
        entity_category=entry.entity_category,
        hidden_by=entry.hidden_by,
        disabled_by=entry.disabled_by,
        state=state.state if state else None,
        available=state is not None and state.state not in UNAVAILABLE_STATES,
        attributes=state.attributes if state else {},
    )


async def fetch_snapshot(client: HAWebSocketClient) -> RegistrySnapshot:
    (
        entities_raw,
        devices_raw,
        areas_raw,
        floors_raw,
        labels_raw,
        states_raw,
        resources_raw,
    ) = await asyncio.gather(
        client.list_entity_registry(),
        client.list_device_registry(),
        client.list_area_registry(),
        client.list_floor_registry(),
        client.list_label_registry(),
        client.get_states(),
        client.list_lovelace_resources(),
    )

    devices_by_id = {d["id"]: DeviceRegistryEntry(**d) for d in devices_raw}
    areas = [AreaRegistryEntry(**a) for a in areas_raw]
    areas_by_id = {a.area_id: a for a in areas}
    floors = [FloorRegistryEntry(**f) for f in floors_raw]
    floors_by_id = {f.floor_id: f for f in floors}
    labels = [LabelRegistryEntry(**l) for l in labels_raw]
    states_by_entity = {s["entity_id"]: StateObject(**s) for s in states_raw}

    entities = [
        _build_entity_record(raw, devices_by_id, areas_by_id, floors_by_id, states_by_entity)
        for raw in entities_raw
    ]

    return RegistrySnapshot(
        fetched_at=datetime.now(UTC),
        entities=entities,
        areas=areas,
        floors=floors,
        labels=labels,
        lovelace_resources=[LovelaceResource(**r) for r in resources_raw],
    )
