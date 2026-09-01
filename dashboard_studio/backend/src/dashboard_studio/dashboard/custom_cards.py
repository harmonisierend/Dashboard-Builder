"""Detects which HACS custom-card families are actually installed, from
the registry snapshot's `lovelace_resources` list, and gates which
`custom_type` strings the generation prompt is allowed to use.

Custom card types are never invented freely by the model: `CUSTOM_CARD_CATALOG`
is the only source of `custom_type` values it may emit, and only for a
family that's genuinely detected as installed. This closes the
hallucination risk for card *types* the same way registry cross-checking
closes it for entity *IDs* in validation.py.

`LovelaceResource` has no `name` field to match a family against, only a
`url` -- detection is a case-insensitive substring match against known
HACS resource URL patterns.
"""

from __future__ import annotations

from dashboard_studio.ha.models import LovelaceResource

CUSTOM_CARD_URL_PATTERNS: dict[str, str] = {
    "mushroom": "mushroom",
    "bubble-card": "bubble-card",
    "card-mod": "card-mod",
    "layout-card": "layout-card",
}

# Only families that genuinely swap in for a native card get catalog
# entries. card-mod (a styling layer, not a card type) and layout-card (the
# native `sections` view already covers grid placement) are detected above
# for a user-facing note but never produce a custom_type here.
CUSTOM_CARD_CATALOG: dict[str, dict[str, str]] = {
    "mushroom": {
        "light": "custom:mushroom-light-card",
        "climate": "custom:mushroom-climate-card",
        "cover": "custom:mushroom-cover-card",
        "fan": "custom:mushroom-fan-card",
        "generic": "custom:mushroom-entity-card",
        "title": "custom:mushroom-title-card",
    },
    "bubble-card": {
        "generic": "custom:bubble-card",
    },
}


def detect_installed_custom_card_families(resources: list[LovelaceResource]) -> set[str]:
    families: set[str] = set()
    for resource in resources:
        url_lower = resource.url.lower()
        for family, pattern in CUSTOM_CARD_URL_PATTERNS.items():
            if pattern in url_lower:
                families.add(family)
    return families


def available_custom_cards(families: set[str]) -> dict[str, dict[str, str]]:
    """CUSTOM_CARD_CATALOG filtered down to detected families only."""
    return {family: CUSTOM_CARD_CATALOG[family] for family in families if family in CUSTOM_CARD_CATALOG}


def allowed_custom_type_strings(available: dict[str, dict[str, str]]) -> set[str]:
    """Flattened set of every exact `custom:xxx` string in `available` --
    consumed directly by validation.py's hard-validation gate.
    """
    return {custom_type for domain_map in available.values() for custom_type in domain_map.values()}
