from __future__ import annotations

from typing import Any

from dashboard_studio.registry.filters import filter_entities, is_excluded_by_default
from dashboard_studio.registry.snapshot import EntityRecord


def make_entity(**overrides: Any) -> EntityRecord:
    defaults: dict[str, Any] = {
        "entity_id": "light.test",
        "domain": "light",
        "name": "Test Light",
        "available": True,
    }
    defaults.update(overrides)
    return EntityRecord(**defaults)


def test_included_by_default() -> None:
    assert is_excluded_by_default(make_entity()) is False


def test_hidden_by_any_reason_excludes() -> None:
    # hidden_by/disabled_by are free-form reason strings ("user", "integration", ...),
    # not a fixed enum -- any non-null value must exclude, not just known ones.
    assert is_excluded_by_default(make_entity(hidden_by="user")) is True
    assert is_excluded_by_default(make_entity(hidden_by="some_future_reason")) is True


def test_disabled_by_any_reason_excludes() -> None:
    assert is_excluded_by_default(make_entity(disabled_by="integration")) is True


def test_diagnostic_category_excluded_by_default_but_togglable() -> None:
    entity = make_entity(entity_category="diagnostic")
    assert is_excluded_by_default(entity) is True
    assert is_excluded_by_default(entity, include_diagnostic=True) is False


def test_config_category_excluded_by_default_but_togglable() -> None:
    entity = make_entity(entity_category="config")
    assert is_excluded_by_default(entity) is True
    assert is_excluded_by_default(entity, include_diagnostic=True) is False


def test_unavailable_state_never_excludes() -> None:
    entity = make_entity(state="unavailable", available=False)
    assert is_excluded_by_default(entity) is False


def test_unknown_state_never_excludes() -> None:
    entity = make_entity(state="unknown", available=False)
    assert is_excluded_by_default(entity) is False


def test_filter_entities_keeps_only_included() -> None:
    entities = [
        make_entity(entity_id="light.a"),
        make_entity(entity_id="light.b", hidden_by="user"),
        make_entity(entity_id="switch.c", disabled_by="integration"),
        make_entity(entity_id="sensor.d", entity_category="diagnostic"),
        make_entity(entity_id="sensor.e", state="unavailable", available=False),
    ]

    result = filter_entities(entities)

    assert [e.entity_id for e in result] == ["light.a", "sensor.e"]


def test_filter_entities_with_diagnostic_included() -> None:
    entities = [
        make_entity(entity_id="light.a"),
        make_entity(entity_id="sensor.d", entity_category="diagnostic"),
    ]

    result = filter_entities(entities, include_diagnostic=True)

    assert [e.entity_id for e in result] == ["light.a", "sensor.d"]
