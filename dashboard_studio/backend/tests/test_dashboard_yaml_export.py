from __future__ import annotations

import yaml

from dashboard_studio.dashboard.config import (
    CardConfig,
    GeneratedDashboard,
    GridSection,
    NativeCardType,
    SectionsView,
)
from dashboard_studio.dashboard.yaml_export import render_dashboard_yaml


def test_top_level_key_is_views() -> None:
    dashboard = GeneratedDashboard(
        views=[SectionsView(title="V", sections=[GridSection(cards=[])])]
    )
    document = yaml.safe_load(render_dashboard_yaml(dashboard))
    assert set(document.keys()) == {"views"}
    assert document["views"][0]["type"] == "sections"


def test_column_span_and_row_span_render_under_section_not_card() -> None:
    dashboard = GeneratedDashboard(
        views=[
            SectionsView(
                title="V",
                sections=[
                    GridSection(
                        column_span=3,
                        row_span=2,
                        cards=[CardConfig(card_type=NativeCardType.tile, entity="light.a")],
                    )
                ],
            )
        ]
    )
    document = yaml.safe_load(render_dashboard_yaml(dashboard))
    section = document["views"][0]["sections"][0]
    assert section["type"] == "grid"
    assert section["column_span"] == 3
    assert section["row_span"] == 2
    card = section["cards"][0]
    assert "column_span" not in card
    assert "row_span" not in card


def test_custom_type_emits_exact_string_as_type() -> None:
    dashboard = GeneratedDashboard(
        views=[
            SectionsView(
                title="V",
                sections=[
                    GridSection(
                        cards=[
                            CardConfig(
                                card_type=NativeCardType.tile,
                                entity="light.a",
                                custom_type="custom:mushroom-light-card",
                            )
                        ]
                    )
                ],
            )
        ]
    )
    document = yaml.safe_load(render_dashboard_yaml(dashboard))
    card = document["views"][0]["sections"][0]["cards"][0]
    assert card["type"] == "custom:mushroom-light-card"


def test_native_card_type_used_when_no_custom_type() -> None:
    dashboard = GeneratedDashboard(
        views=[
            SectionsView(
                title="V",
                sections=[
                    GridSection(cards=[CardConfig(card_type=NativeCardType.heading, heading="Lights")])
                ],
            )
        ]
    )
    document = yaml.safe_load(render_dashboard_yaml(dashboard))
    card = document["views"][0]["sections"][0]["cards"][0]
    assert card["type"] == "heading"
    assert card["heading"] == "Lights"


def test_unset_optional_fields_are_omitted() -> None:
    dashboard = GeneratedDashboard(
        views=[
            SectionsView(
                title="V",
                sections=[GridSection(cards=[CardConfig(card_type=NativeCardType.tile, entity="light.a")])],
            )
        ]
    )
    document = yaml.safe_load(render_dashboard_yaml(dashboard))
    view = document["views"][0]
    assert "max_columns" not in view
    assert "dense_section_placement" not in view
    section = view["sections"][0]
    assert "column_span" not in section
    assert "row_span" not in section
    card = section["cards"][0]
    for field in ("entities", "name", "title", "heading", "icon", "color", "features", "hours_to_show"):
        assert field not in card


def test_view_title_and_set_optional_fields_render() -> None:
    dashboard = GeneratedDashboard(
        views=[
            SectionsView(
                title="Wohnzimmer",
                max_columns=4,
                dense_section_placement=True,
                sections=[GridSection(cards=[])],
            )
        ]
    )
    document = yaml.safe_load(render_dashboard_yaml(dashboard))
    view = document["views"][0]
    assert view["title"] == "Wohnzimmer"
    assert view["max_columns"] == 4
    assert view["dense_section_placement"] is True


def test_entities_card_renders_entities_list() -> None:
    dashboard = GeneratedDashboard(
        views=[
            SectionsView(
                title="V",
                sections=[
                    GridSection(
                        cards=[
                            CardConfig(
                                card_type=NativeCardType.entities,
                                entities=["light.a", "switch.b"],
                                title="Devices",
                            )
                        ]
                    )
                ],
            )
        ]
    )
    document = yaml.safe_load(render_dashboard_yaml(dashboard))
    card = document["views"][0]["sections"][0]["cards"][0]
    assert card["type"] == "entities"
    assert card["entities"] == ["light.a", "switch.b"]
    assert card["title"] == "Devices"
