from __future__ import annotations

from dashboard_studio.dashboard.config import (
    CardConfig,
    GeneratedDashboard,
    GridSection,
    NativeCardType,
    SectionsView,
    StyleHint,
    to_style_hint,
)
from dashboard_studio.design.tokens import (
    CardStyleClassification,
    ColorPair,
    ColorPalette,
    Density,
    DensityMode,
    DesignTokenSet,
    FontSizeScale,
    FontWeights,
    Form,
    StyleFamily,
    Typography,
)


def make_token_set() -> DesignTokenSet:
    pair = ColorPair(light="#111111", dark="#eeeeee")
    return DesignTokenSet(
        colors=ColorPalette(
            primary=pair,
            accent=pair,
            background=pair,
            surface=pair,
            on_surface=pair,
            state_on=pair,
            state_off=pair,
            warn=pair,
            critical=pair,
        ),
        typography=Typography(
            font_family="Inter",
            sizes=FontSizeScale(xs="12px", sm="14px", md="16px", lg="20px", xl="24px"),
            weights=FontWeights(regular=400, medium=500, bold=700),
        ),
        form=Form(border_radius_px=8, shadow="none", border_width_px=1, style_family=StyleFamily.flat),
        density=Density(mode=DensityMode.comfortable, grid_gap_px=8, section_spacing_px=16),
        card_style=CardStyleClassification(primary_style="Tile-based", reasoning="test"),
    )


def test_entity_ids_combines_entity_and_entities() -> None:
    card = CardConfig(card_type=NativeCardType.entities, entity="light.a", entities=["switch.b", "switch.c"])
    assert card.entity_ids() == ["switch.b", "switch.c", "light.a"]


def test_entity_ids_empty_when_neither_set() -> None:
    card = CardConfig(card_type=NativeCardType.heading)
    assert card.entity_ids() == []


def test_entity_ids_entity_only() -> None:
    card = CardConfig(card_type=NativeCardType.tile, entity="light.a")
    assert card.entity_ids() == ["light.a"]


def test_entity_ids_entities_only() -> None:
    card = CardConfig(card_type=NativeCardType.entities, entities=["switch.b", "switch.c"])
    assert card.entity_ids() == ["switch.b", "switch.c"]


def test_full_dashboard_round_trip() -> None:
    dashboard = GeneratedDashboard(
        views=[
            SectionsView(
                title="Wohnzimmer",
                sections=[
                    GridSection(
                        column_span=2,
                        cards=[CardConfig(card_type=NativeCardType.tile, entity="light.living_room")],
                    )
                ],
            )
        ]
    )
    dumped = dashboard.model_dump()
    restored = GeneratedDashboard(**dumped)
    assert restored == dashboard
    assert restored.views[0].sections[0].column_span == 2
    assert restored.views[0].sections[0].cards[0].entity == "light.living_room"


def test_generated_dashboard_defaults_to_empty_views() -> None:
    assert GeneratedDashboard().views == []


def test_grid_section_defaults() -> None:
    section = GridSection()
    assert section.column_span is None
    assert section.row_span is None
    assert section.cards == []


def test_to_style_hint_projects_relevant_fields_only() -> None:
    tokens = make_token_set()
    hint = to_style_hint(tokens)
    assert hint == StyleHint(
        density_mode=DensityMode.comfortable,
        card_style="Tile-based",
        style_family=StyleFamily.flat,
    )
