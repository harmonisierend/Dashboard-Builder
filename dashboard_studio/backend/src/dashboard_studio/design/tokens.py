"""The design-token-set schema produced by the vision analysis (M2) and
edited/saved by the user.

Fields mirror the spec's bullet list exactly (color palette with light/dark
variants, typography, form, density, card-style classification).

`CardStyleClassification.primary_style` is deliberately a free-form `str`,
not an `Enum`. The spec lists "Mushroom-like/Bubble-like/Minimal-Native/
Tile-based" as *examples* of a classification, not an exhaustive set --
an `Enum` field would become a hard JSON-schema `enum` that the vision call's
structured output is forced to pick from, producing a wrong classification
for any reference image that doesn't fit one of the four. The examples are
given to the model as prompt guidance instead (see `anthropic_client.py`).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ColorPair(BaseModel):
    """A single color's light- and dark-mode variant, as CSS hex strings."""

    light: str
    dark: str


class ColorPalette(BaseModel):
    primary: ColorPair
    accent: ColorPair
    background: ColorPair
    surface: ColorPair
    on_surface: ColorPair
    state_on: ColorPair
    state_off: ColorPair
    warn: ColorPair
    critical: ColorPair


class FontSizeScale(BaseModel):
    xs: str
    sm: str
    md: str
    lg: str
    xl: str


class FontWeights(BaseModel):
    regular: int
    medium: int
    bold: int


class Typography(BaseModel):
    font_family: str
    sizes: FontSizeScale
    weights: FontWeights


class StyleFamily(str, Enum):
    glass = "glass"
    flat = "flat"
    neumorphic = "neumorphic"


class Form(BaseModel):
    border_radius_px: int
    shadow: str
    border_width_px: int
    style_family: StyleFamily


class DensityMode(str, Enum):
    compact = "compact"
    comfortable = "comfortable"


class Density(BaseModel):
    mode: DensityMode
    grid_gap_px: int
    section_spacing_px: int


class CardStyleClassification(BaseModel):
    primary_style: str
    reasoning: str


class DesignTokenSet(BaseModel):
    schema_version: int = 1
    colors: ColorPalette
    typography: Typography
    form: Form
    density: Density
    card_style: CardStyleClassification
