"""The generated-dashboard schema (Milestone 3).

`CardConfig` is deliberately one flat model -- a `card_type` discriminator
plus every possible optional field -- rather than a discriminated union of
one Pydantic model per HA card type. A flat shape is a strictly simpler
JSON schema for Anthropic's structured-output feature (`output_format`) to
enforce than a nested union, and it avoids per-card-type branch dispatch in
both validation (`validation.py`) and YAML rendering (`yaml_export.py`).

`column_span`/`row_span` live on `GridSection`, not on `CardConfig` --
verified against home-assistant/frontend's actual TypeScript source
(`LovelaceBaseSectionConfig`) during planning. Cards inside a section stack
vertically; it's the section itself that spans columns/rows in the view's
grid. Getting this backwards would silently produce a dashboard that
doesn't lay out as intended.

`SectionsView.title` is a *view*-level title, which is not deprecated --
only a *section*-level `title` is (HA's docs say to use a `heading` card
there instead), so `CardConfig.heading` exists as its own field distinct
from `name`/`title` for exactly that purpose.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from dashboard_studio.design.tokens import DensityMode, DesignTokenSet, StyleFamily


class NativeCardType(str, Enum):
    tile = "tile"
    heading = "heading"
    entities = "entities"
    thermostat = "thermostat"
    history_graph = "history-graph"
    weather_forecast = "weather-forecast"
    light = "light"
    media_control = "media-control"


class CardConfig(BaseModel):
    card_type: NativeCardType
    # Must be one of the exact strings in custom_cards.CUSTOM_CARD_CATALOG
    # for a family actually detected as installed -- validation.py strips
    # anything else back to None (native fallback), never trusting the
    # model to invent a HACS card type.
    custom_type: str | None = None

    # tile, thermostat, weather-forecast, light, media-control, heading
    entity: str | None = None
    # entities-card, history-graph
    entities: list[str] | None = None

    name: str | None = None
    # entities-card, history-graph
    title: str | None = None
    # heading-card's own text field
    heading: str | None = None

    icon: str | None = None
    color: str | None = None
    features: list[str] | None = None
    hours_to_show: int | None = None

    def entity_ids(self) -> list[str]:
        """Every entity_id this card references, for validation.py."""
        ids = list(self.entities or [])
        if self.entity:
            ids.append(self.entity)
        return ids


class GridSection(BaseModel):
    column_span: int | None = None
    row_span: int | None = None
    cards: list[CardConfig] = []


class SectionsView(BaseModel):
    title: str
    max_columns: int | None = None
    dense_section_placement: bool | None = None
    sections: list[GridSection] = []


class GeneratedDashboard(BaseModel):
    views: list[SectionsView] = []


class GenerationStrategy(str, Enum):
    """Closed set matching the UI's exact 3-way choice -- unlike
    CardStyleClassification.primary_style in design/tokens.py, there is no
    open-ended fourth option to leave room for here.
    """

    by_area = "by_area"
    by_domain = "by_domain"
    automatic = "automatic"


class StyleHint(BaseModel):
    """Reduced from an optional DesignTokenSet -- only the fields that
    plausibly influence card/density choices during generation, not the
    full 9-color palette (which has no bearing on layout structure).
    """

    density_mode: DensityMode
    card_style: str
    style_family: StyleFamily


def to_style_hint(tokens: DesignTokenSet) -> StyleHint:
    return StyleHint(
        density_mode=tokens.density.mode,
        card_style=tokens.card_style.primary_style,
        style_family=tokens.form.style_family,
    )
