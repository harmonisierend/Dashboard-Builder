from __future__ import annotations

from typing import Any

from dashboard_studio.dashboard.scope import (
    CandidateEntitySummary,
    GenerationScope,
    ViewProposalEntitySelector,
    entities_in_scope,
    resolve_view_entities,
    summarize_scope,
    to_candidate_summary,
)
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


def test_entities_in_scope_by_area_only() -> None:
    entities = [
        make_entity(entity_id="light.a", area_id="living_room"),
        make_entity(entity_id="light.b", area_id="kitchen"),
    ]
    result = entities_in_scope(entities, GenerationScope(area_ids=["living_room"]))
    assert [e.entity_id for e in result] == ["light.a"]


def test_entities_in_scope_by_floor_only() -> None:
    entities = [
        make_entity(entity_id="light.a", floor_id="ground"),
        make_entity(entity_id="light.b", floor_id="upper"),
    ]
    result = entities_in_scope(entities, GenerationScope(floor_ids=["ground"]))
    assert [e.entity_id for e in result] == ["light.a"]


def test_entities_in_scope_area_or_floor_union() -> None:
    entities = [
        make_entity(entity_id="light.a", area_id="living_room", floor_id="upper"),
        make_entity(entity_id="light.b", area_id="kitchen", floor_id="ground"),
        make_entity(entity_id="light.c", area_id="garage", floor_id="basement"),
    ]
    result = entities_in_scope(
        entities, GenerationScope(area_ids=["living_room"], floor_ids=["ground"])
    )
    assert {e.entity_id for e in result} == {"light.a", "light.b"}


def test_entities_in_scope_respects_default_filters() -> None:
    entities = [
        make_entity(entity_id="light.a", area_id="living_room"),
        make_entity(entity_id="light.b", area_id="living_room", hidden_by="user"),
        make_entity(entity_id="sensor.c", area_id="living_room", entity_category="diagnostic"),
    ]
    result = entities_in_scope(entities, GenerationScope(area_ids=["living_room"]))
    assert [e.entity_id for e in result] == ["light.a"]


def test_entities_in_scope_include_diagnostic() -> None:
    entities = [
        make_entity(entity_id="sensor.c", area_id="living_room", entity_category="diagnostic"),
    ]
    result = entities_in_scope(
        entities, GenerationScope(area_ids=["living_room"]), include_diagnostic=True
    )
    assert [e.entity_id for e in result] == ["sensor.c"]


def test_entities_in_scope_empty_scope_selects_nothing() -> None:
    entities = [make_entity(entity_id="light.a", area_id="living_room")]
    result = entities_in_scope(entities, GenerationScope())
    assert result == []


def test_summarize_scope_groups_by_area_and_counts_domains() -> None:
    entities = [
        make_entity(entity_id="light.a", domain="light", area_id="living_room", area_name="Living Room"),
        make_entity(entity_id="light.b", domain="light", area_id="living_room", area_name="Living Room"),
        make_entity(entity_id="switch.c", domain="switch", area_id="living_room", area_name="Living Room"),
        make_entity(entity_id="light.d", domain="light", area_id="kitchen", area_name="Kitchen"),
    ]
    summary = summarize_scope(entities)
    assert summary.total_entities == 4
    by_area = {area.area_id: area for area in summary.areas}
    assert set(by_area) == {"living_room", "kitchen"}
    living_room = by_area["living_room"]
    assert living_room.area_name == "Living Room"
    assert {(dc.domain, dc.count) for dc in living_room.domain_counts} == {("light", 2), ("switch", 1)}
    kitchen = by_area["kitchen"]
    assert {(dc.domain, dc.count) for dc in kitchen.domain_counts} == {("light", 1)}


def test_summarize_scope_groups_entities_without_area() -> None:
    entities = [make_entity(entity_id="light.a", area_id=None)]
    summary = summarize_scope(entities)
    assert summary.total_entities == 1
    assert summary.areas[0].area_id is None


def test_summarize_scope_empty_input() -> None:
    summary = summarize_scope([])
    assert summary.total_entities == 0
    assert summary.areas == []


def test_resolve_view_entities_and_between_dimensions() -> None:
    entities = [
        make_entity(entity_id="light.a", domain="light", area_id="living_room"),
        make_entity(entity_id="switch.b", domain="switch", area_id="living_room"),
        make_entity(entity_id="light.c", domain="light", area_id="kitchen"),
    ]
    selector = ViewProposalEntitySelector(area_ids=["living_room"], domains=["light"])
    result = resolve_view_entities(entities, selector)
    assert [e.entity_id for e in result] == ["light.a"]


def test_resolve_view_entities_or_within_dimension() -> None:
    entities = [
        make_entity(entity_id="light.a", domain="light"),
        make_entity(entity_id="switch.b", domain="switch"),
        make_entity(entity_id="sensor.c", domain="sensor"),
    ]
    selector = ViewProposalEntitySelector(domains=["light", "switch"])
    result = resolve_view_entities(entities, selector)
    assert {e.entity_id for e in result} == {"light.a", "switch.b"}


def test_resolve_view_entities_empty_selector_means_no_filter() -> None:
    entities = [make_entity(entity_id="light.a"), make_entity(entity_id="switch.b", domain="switch")]
    result = resolve_view_entities(entities, ViewProposalEntitySelector())
    assert {e.entity_id for e in result} == {"light.a", "switch.b"}


def test_resolve_view_entities_selector_outside_scope_yields_zero_candidates() -> None:
    entities = [make_entity(entity_id="light.a", area_id="living_room")]
    selector = ViewProposalEntitySelector(area_ids=["nonexistent_area"])
    result = resolve_view_entities(entities, selector)
    assert result == []


def test_to_candidate_summary_extracts_device_class() -> None:
    entity = make_entity(
        entity_id="sensor.temp",
        domain="sensor",
        name="Temperature",
        area_name="Living Room",
        attributes={"device_class": "temperature"},
    )
    summary = to_candidate_summary(entity)
    assert summary == CandidateEntitySummary(
        entity_id="sensor.temp",
        domain="sensor",
        name="Temperature",
        area_name="Living Room",
        device_class="temperature",
    )


def test_to_candidate_summary_device_class_absent() -> None:
    entity = make_entity(entity_id="light.a")
    summary = to_candidate_summary(entity)
    assert summary.device_class is None
