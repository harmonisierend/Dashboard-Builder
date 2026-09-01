"""Renders a validated GeneratedDashboard as real Lovelace YAML-mode text.

Hand-builds the nested dict rather than a generic `model_dump(by_alias=True)`
call, mirroring design/theme_export.py's approach exactly -- internal field
names (`card_type`, not `type`) don't match HA's YAML keys 1:1, so an
explicit mapping is clearer and safer than fighting Pydantic aliasing.

Output shape (verified against home-assistant/frontend's TypeScript
source): a top-level `views:` list; each view is `type: sections`; each
section is `type: grid` with `column_span`/`row_span` at the *section*
level (not per-card); cards carry their real HA `type:` (native card type,
or a `custom:...` string when set).
"""

from __future__ import annotations

import yaml

from dashboard_studio.dashboard.config import (
    CardConfig,
    GeneratedDashboard,
    GridSection,
    SectionsView,
)


def _render_card(card: CardConfig) -> dict[str, object]:
    result: dict[str, object] = {"type": card.custom_type or card.card_type.value}
    if card.entity is not None:
        result["entity"] = card.entity
    if card.entities is not None:
        result["entities"] = card.entities
    if card.name is not None:
        result["name"] = card.name
    if card.title is not None:
        result["title"] = card.title
    if card.heading is not None:
        result["heading"] = card.heading
    if card.icon is not None:
        result["icon"] = card.icon
    if card.color is not None:
        result["color"] = card.color
    if card.features is not None:
        result["features"] = card.features
    if card.hours_to_show is not None:
        result["hours_to_show"] = card.hours_to_show
    return result


def _render_section(section: GridSection) -> dict[str, object]:
    result: dict[str, object] = {"type": "grid", "cards": [_render_card(card) for card in section.cards]}
    if section.column_span is not None:
        result["column_span"] = section.column_span
    if section.row_span is not None:
        result["row_span"] = section.row_span
    return result


def _render_view(view: SectionsView) -> dict[str, object]:
    result: dict[str, object] = {
        "title": view.title,
        "type": "sections",
        "sections": [_render_section(section) for section in view.sections],
    }
    if view.max_columns is not None:
        result["max_columns"] = view.max_columns
    if view.dense_section_placement is not None:
        result["dense_section_placement"] = view.dense_section_placement
    return result


def render_dashboard_yaml(dashboard: GeneratedDashboard) -> str:
    document = {"views": [_render_view(view) for view in dashboard.views]}
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)
