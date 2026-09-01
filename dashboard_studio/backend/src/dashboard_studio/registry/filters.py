"""Default entity include/exclude rules.

Per spec: entities with `hidden_by`/`disabled_by` set are excluded;
`entity_category` in (config, diagnostic) is excluded by default but can be
toggled back on; unavailable/unknown state is flagged for the UI, never used
to drop an entity from consideration.

`hidden_by`/`disabled_by` are `None` or a free-form reason string (e.g.
"user", "integration") -- never a fixed enum -- so the correct check is
"is this non-null", not a match against specific known values.
"""

from __future__ import annotations

from dashboard_studio.registry.snapshot import EntityRecord

DEFAULT_EXCLUDED_CATEGORIES = frozenset({"config", "diagnostic"})


def is_excluded_by_default(entity: EntityRecord, include_diagnostic: bool = False) -> bool:
    if entity.hidden_by is not None:
        return True
    if entity.disabled_by is not None:
        return True
    return not include_diagnostic and entity.entity_category in DEFAULT_EXCLUDED_CATEGORIES


def filter_entities(
    entities: list[EntityRecord], include_diagnostic: bool = False
) -> list[EntityRecord]:
    return [e for e in entities if not is_excluded_by_default(e, include_diagnostic)]
