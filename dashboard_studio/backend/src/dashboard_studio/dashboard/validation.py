"""Hard entity-ID and custom-card-type validation.

This is the file the milestone's one named product acceptance criterion
lives and dies by: "no generated dashboard contains a non-existent entity
ID." `validate_and_strip` is called unconditionally by the orchestrator
regardless of how confident the generation calls looked -- it is the
actual enforcement point, not a best-effort extra step.

Stripping walks bottom-up (cards -> sections -> views):
- A `custom_type` not in the allowed set is nulled (card falls back to its
  native `card_type`, kept) -- counted separately from card removals,
  since the card itself survives.
- An invalid id inside `entities` is dropped from that list; the card
  survives if entities remain.
- An invalid single `entity` field drops the *whole card* -- a
  tile/thermostat/weather-forecast/light/media-control/heading card is
  meaningless without its one entity.
- A card whose `entities` list becomes empty after stripping is dropped.
- A section left with zero cards is dropped.
- A view left with zero sections is dropped -- never kept empty.
"""

from __future__ import annotations

from pydantic import BaseModel

from dashboard_studio.dashboard.config import (
    CardConfig,
    GeneratedDashboard,
    GridSection,
    SectionsView,
)


class ValidationReport(BaseModel):
    removed_entity_refs: int = 0
    removed_custom_types: int = 0
    removed_cards: int = 0
    removed_sections: int = 0
    removed_views: int = 0
    details: list[str] = []


def _validate_card(
    card: CardConfig,
    valid_entity_ids: set[str],
    allowed_custom_types: set[str],
    report: ValidationReport,
    context: str,
) -> CardConfig | None:
    if card.custom_type is not None and card.custom_type not in allowed_custom_types:
        report.removed_custom_types += 1
        report.details.append(
            f"Kartentyp '{card.custom_type}' in {context} nicht verfügbar, native Karte verwendet."
        )
        card = card.model_copy(update={"custom_type": None})

    if card.entity is not None and card.entity not in valid_entity_ids:
        report.removed_entity_refs += 1
        report.removed_cards += 1
        report.details.append(
            f"Karte in {context} entfernt: Entität '{card.entity}' nicht im Registry-Snapshot."
        )
        return None

    if card.entities is not None:
        valid_entities = [entity_id for entity_id in card.entities if entity_id in valid_entity_ids]
        removed = len(card.entities) - len(valid_entities)
        if removed:
            report.removed_entity_refs += removed
            for entity_id in card.entities:
                if entity_id not in valid_entity_ids:
                    report.details.append(
                        f"Entität '{entity_id}' aus Karte in {context} entfernt "
                        "(nicht im Registry-Snapshot)."
                    )
            if not valid_entities:
                report.removed_cards += 1
                report.details.append(f"Karte in {context} entfernt: keine gültigen Entitäten mehr.")
                return None
            card = card.model_copy(update={"entities": valid_entities})

    return card


def _validate_section(
    section: GridSection,
    valid_entity_ids: set[str],
    allowed_custom_types: set[str],
    report: ValidationReport,
    context: str,
) -> GridSection | None:
    cards = [
        validated
        for card in section.cards
        if (validated := _validate_card(card, valid_entity_ids, allowed_custom_types, report, context))
        is not None
    ]
    if not cards:
        report.removed_sections += 1
        report.details.append(f"Section in {context} entfernt: keine Karten mehr übrig.")
        return None
    return section.model_copy(update={"cards": cards})


def _validate_view(
    view: SectionsView,
    valid_entity_ids: set[str],
    allowed_custom_types: set[str],
    report: ValidationReport,
) -> SectionsView | None:
    context = f"Ansicht '{view.title}'"
    sections = [
        validated
        for section in view.sections
        if (validated := _validate_section(section, valid_entity_ids, allowed_custom_types, report, context))
        is not None
    ]
    if not sections:
        report.removed_views += 1
        report.details.append(f"{context} entfernt: keine Sections mehr übrig.")
        return None
    return view.model_copy(update={"sections": sections})


def validate_and_strip(
    dashboard: GeneratedDashboard,
    valid_entity_ids: set[str],
    allowed_custom_types: set[str],
) -> tuple[GeneratedDashboard, ValidationReport]:
    report = ValidationReport()
    views = [
        validated
        for view in dashboard.views
        if (validated := _validate_view(view, valid_entity_ids, allowed_custom_types, report)) is not None
    ]
    return GeneratedDashboard(views=views), report
