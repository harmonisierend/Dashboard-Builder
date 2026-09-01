from __future__ import annotations

import pytest
from pydantic import ValidationError

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


def make_pair() -> ColorPair:
    return ColorPair(light="#111111", dark="#eeeeee")


def make_palette() -> ColorPalette:
    pair = make_pair()
    return ColorPalette(
        primary=pair,
        accent=pair,
        background=pair,
        surface=pair,
        on_surface=pair,
        state_on=pair,
        state_off=pair,
        warn=pair,
        critical=pair,
    )


def make_token_set(**overrides: object) -> DesignTokenSet:
    defaults: dict[str, object] = {
        "colors": make_palette(),
        "typography": Typography(
            font_family="Inter, sans-serif",
            sizes=FontSizeScale(xs="12px", sm="14px", md="16px", lg="20px", xl="24px"),
            weights=FontWeights(regular=400, medium=500, bold=700),
        ),
        "form": Form(
            border_radius_px=12,
            shadow="0 2px 8px rgba(0,0,0,0.15)",
            border_width_px=1,
            style_family=StyleFamily.flat,
        ),
        "density": Density(mode=DensityMode.comfortable, grid_gap_px=8, section_spacing_px=16),
        "card_style": CardStyleClassification(primary_style="Tile-based", reasoning="test"),
    }
    defaults.update(overrides)
    return DesignTokenSet(**defaults)  # type: ignore[arg-type]


def test_round_trips_through_json() -> None:
    token_set = make_token_set()
    restored = DesignTokenSet.model_validate_json(token_set.model_dump_json())
    assert restored == token_set


def test_default_schema_version_is_one() -> None:
    assert make_token_set().schema_version == 1


def test_card_style_accepts_a_label_outside_the_four_examples() -> None:
    token_set = make_token_set(
        card_style=CardStyleClassification(
            primary_style="Something Entirely New", reasoning="doesn't fit the examples"
        )
    )
    assert token_set.card_style.primary_style == "Something Entirely New"


def test_invalid_style_family_rejected() -> None:
    with pytest.raises(ValidationError):
        Form(
            border_radius_px=12,
            shadow="none",
            border_width_px=1,
            style_family="not-a-real-style",  # type: ignore[arg-type]
        )


def test_invalid_density_mode_rejected() -> None:
    with pytest.raises(ValidationError):
        Density(
            mode="not-a-real-mode",  # type: ignore[arg-type]
            grid_gap_px=8,
            section_spacing_px=16,
        )


def test_missing_required_field_rejected() -> None:
    with pytest.raises(ValidationError):
        ColorPair(light="#111111")  # type: ignore[call-arg]
