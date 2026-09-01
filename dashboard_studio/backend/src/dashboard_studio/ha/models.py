"""Pydantic models mirroring Home Assistant's WebSocket API payloads.

Field sets are intentionally minimal (only what the registry snapshot and
filtering logic need) rather than exhaustive mirrors of HA's internal
registry schemas — extra fields HA sends are simply ignored.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class HAModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class AreaRegistryEntry(HAModel):
    area_id: str
    name: str
    floor_id: str | None = None
    labels: list[str] = []


class FloorRegistryEntry(HAModel):
    floor_id: str
    name: str
    level: int | None = None


class LabelRegistryEntry(HAModel):
    label_id: str
    name: str
    color: str | None = None


class DeviceRegistryEntry(HAModel):
    id: str
    name: str | None = None
    name_by_user: str | None = None
    area_id: str | None = None
    labels: list[str] = []


class EntityRegistryEntry(HAModel):
    entity_id: str
    name: str | None = None
    device_id: str | None = None
    area_id: str | None = None
    platform: str | None = None
    entity_category: str | None = None
    hidden_by: str | None = None
    disabled_by: str | None = None
    labels: list[str] = []


class StateObject(HAModel):
    entity_id: str
    state: str
    attributes: dict[str, Any] = {}
    last_changed: str | None = None
    last_updated: str | None = None


class LovelaceResource(HAModel):
    id: str
    type: str
    url: str


class LovelaceDashboard(HAModel):
    id: str | None = None
    url_path: str | None = None
    title: str | None = None
    mode: str | None = None
    show_in_sidebar: bool = True
