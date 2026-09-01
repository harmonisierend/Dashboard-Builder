from __future__ import annotations

from dashboard_studio.dashboard.config import (
    CardConfig,
    GeneratedDashboard,
    GridSection,
    NativeCardType,
    SectionsView,
)
from dashboard_studio.dashboard.validation import validate_and_strip


def test_fully_valid_dashboard_produces_zero_removals() -> None:
    dashboard = GeneratedDashboard(
        views=[
            SectionsView(
                title="Wohnzimmer",
                sections=[
                    GridSection(
                        cards=[
                            CardConfig(card_type=NativeCardType.tile, entity="light.a"),
                            CardConfig(
                                card_type=NativeCardType.entities,
                                entities=["switch.b", "switch.c"],
                            ),
                        ]
                    )
                ],
            )
        ]
    )
    valid_ids = {"light.a", "switch.b", "switch.c"}

    result, report = validate_and_strip(dashboard, valid_ids, set())

    assert result == dashboard
    assert report.removed_entity_refs == 0
    assert report.removed_custom_types == 0
    assert report.removed_cards == 0
    assert report.removed_sections == 0
    assert report.removed_views == 0
    assert report.details == []


def test_entities_card_strips_invalid_ids_and_keeps_card() -> None:
    dashboard = GeneratedDashboard(
        views=[
            SectionsView(
                title="V",
                sections=[
                    GridSection(
                        cards=[
                            CardConfig(
                                card_type=NativeCardType.entities,
                                entities=["light.a", "light.b", "light.c", "light.d", "light.e", "light.ghost"],
                            )
                        ]
                    )
                ],
            )
        ]
    )
    valid_ids = {"light.a", "light.b", "light.c", "light.d", "light.e"}

    result, report = validate_and_strip(dashboard, valid_ids, set())

    card = result.views[0].sections[0].cards[0]
    assert card.entities == ["light.a", "light.b", "light.c", "light.d", "light.e"]
    assert report.removed_entity_refs == 1
    assert report.removed_cards == 0


def test_tile_card_with_invalid_single_entity_is_dropped() -> None:
    dashboard = GeneratedDashboard(
        views=[
            SectionsView(
                title="V",
                sections=[
                    GridSection(
                        cards=[
                            CardConfig(card_type=NativeCardType.tile, entity="light.ghost"),
                            CardConfig(card_type=NativeCardType.tile, entity="light.real"),
                        ]
                    )
                ],
            )
        ]
    )
    valid_ids = {"light.real"}

    result, report = validate_and_strip(dashboard, valid_ids, set())

    cards = result.views[0].sections[0].cards
    assert [c.entity for c in cards] == ["light.real"]
    assert report.removed_entity_refs == 1
    assert report.removed_cards == 1


def test_section_with_zero_cards_after_stripping_is_dropped() -> None:
    dashboard = GeneratedDashboard(
        views=[
            SectionsView(
                title="V",
                sections=[
                    GridSection(cards=[CardConfig(card_type=NativeCardType.tile, entity="light.ghost")]),
                    GridSection(cards=[CardConfig(card_type=NativeCardType.tile, entity="light.real")]),
                ],
            )
        ]
    )
    valid_ids = {"light.real"}

    result, report = validate_and_strip(dashboard, valid_ids, set())

    assert len(result.views[0].sections) == 1
    assert result.views[0].sections[0].cards[0].entity == "light.real"
    assert report.removed_sections == 1


def test_view_with_zero_sections_after_stripping_is_dropped() -> None:
    dashboard = GeneratedDashboard(
        views=[
            SectionsView(
                title="Empty After Strip",
                sections=[
                    GridSection(cards=[CardConfig(card_type=NativeCardType.tile, entity="light.ghost")])
                ],
            ),
            SectionsView(
                title="Survives",
                sections=[
                    GridSection(cards=[CardConfig(card_type=NativeCardType.tile, entity="light.real")])
                ],
            ),
        ]
    )
    valid_ids = {"light.real"}

    result, report = validate_and_strip(dashboard, valid_ids, set())

    assert [v.title for v in result.views] == ["Survives"]
    assert report.removed_views == 1


def test_entities_list_becomes_empty_drops_card() -> None:
    dashboard = GeneratedDashboard(
        views=[
            SectionsView(
                title="V",
                sections=[
                    GridSection(
                        cards=[CardConfig(card_type=NativeCardType.entities, entities=["light.ghost"])]
                    )
                ],
            )
        ]
    )
    result, report = validate_and_strip(dashboard, set(), set())

    assert result.views == []
    assert report.removed_cards == 1
    assert report.removed_entity_refs == 1
    assert report.removed_sections == 1
    assert report.removed_views == 1


def test_custom_type_not_allowed_is_nulled_but_card_kept() -> None:
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
    valid_ids = {"light.a"}

    result, report = validate_and_strip(dashboard, valid_ids, set())

    card = result.views[0].sections[0].cards[0]
    assert card.custom_type is None
    assert card.card_type == NativeCardType.tile
    assert card.entity == "light.a"
    assert report.removed_custom_types == 1
    assert report.removed_cards == 0


def test_custom_type_in_allowed_set_is_preserved() -> None:
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
    valid_ids = {"light.a"}
    allowed = {"custom:mushroom-light-card"}

    result, report = validate_and_strip(dashboard, valid_ids, allowed)

    assert result.views[0].sections[0].cards[0].custom_type == "custom:mushroom-light-card"
    assert report.removed_custom_types == 0


def test_multi_violation_dashboard_produces_correct_combined_counts() -> None:
    dashboard = GeneratedDashboard(
        views=[
            SectionsView(
                title="Mixed",
                sections=[
                    GridSection(
                        cards=[
                            CardConfig(card_type=NativeCardType.tile, entity="light.real"),
                            CardConfig(card_type=NativeCardType.tile, entity="light.ghost"),
                            CardConfig(
                                card_type=NativeCardType.entities,
                                entities=["switch.real", "switch.ghost"],
                            ),
                            CardConfig(
                                card_type=NativeCardType.tile,
                                entity="light.real",
                                custom_type="custom:unknown-card",
                            ),
                        ]
                    ),
                    GridSection(
                        cards=[CardConfig(card_type=NativeCardType.tile, entity="light.only_ghost")]
                    ),
                ],
            ),
            SectionsView(
                title="All Ghosts",
                sections=[
                    GridSection(
                        cards=[CardConfig(card_type=NativeCardType.tile, entity="light.also_ghost")]
                    )
                ],
            ),
        ]
    )
    valid_ids = {"light.real", "switch.real"}

    result, report = validate_and_strip(dashboard, valid_ids, set())

    assert [v.title for v in result.views] == ["Mixed"]
    remaining_section = result.views[0].sections
    assert len(remaining_section) == 1
    cards = remaining_section[0].cards
    assert [c.entity for c in cards if c.entity] == ["light.real", "light.real"]
    entities_card = next(c for c in cards if c.entities is not None)
    assert entities_card.entities == ["switch.real"]

    assert report.removed_entity_refs == 4  # light.ghost, switch.ghost, light.only_ghost, light.also_ghost
    assert report.removed_cards == 3  # light.ghost card, light.only_ghost card, light.also_ghost card
    assert report.removed_custom_types == 1  # custom:unknown-card
    assert report.removed_sections == 2  # the only_ghost section + All Ghosts' own section
    assert report.removed_views == 1  # "All Ghosts"
    assert len(report.details) > 0
