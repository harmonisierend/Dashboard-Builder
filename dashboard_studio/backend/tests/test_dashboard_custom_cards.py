from __future__ import annotations

from dashboard_studio.dashboard.custom_cards import (
    CUSTOM_CARD_CATALOG,
    allowed_custom_type_strings,
    available_custom_cards,
    detect_installed_custom_card_families,
)
from dashboard_studio.ha.models import LovelaceResource


def make_resource(url: str) -> LovelaceResource:
    return LovelaceResource(id="1", type="module", url=url)


def test_detects_mushroom_by_substring() -> None:
    resources = [make_resource("/hacsfiles/mushroom/mushroom.js")]
    assert detect_installed_custom_card_families(resources) == {"mushroom"}


def test_detects_case_insensitively() -> None:
    resources = [make_resource("/hacsfiles/Mushroom/Mushroom.js")]
    assert detect_installed_custom_card_families(resources) == {"mushroom"}


def test_detects_multiple_families() -> None:
    resources = [
        make_resource("/hacsfiles/mushroom/mushroom.js"),
        make_resource("/hacsfiles/bubble-card/bubble-card.js"),
        make_resource("/hacsfiles/card-mod/card-mod.js"),
    ]
    assert detect_installed_custom_card_families(resources) == {"mushroom", "bubble-card", "card-mod"}


def test_partial_url_match_still_detects() -> None:
    resources = [make_resource("https://cdn.example.com/community/layout-card/layout-card.js?v=2")]
    assert detect_installed_custom_card_families(resources) == {"layout-card"}


def test_unrelated_resource_detects_nothing() -> None:
    resources = [make_resource("/local/my-custom-theme.css")]
    assert detect_installed_custom_card_families(resources) == set()


def test_no_resources_detects_nothing() -> None:
    assert detect_installed_custom_card_families([]) == set()


def test_available_custom_cards_filters_to_catalog_families() -> None:
    # card-mod is detected but has no catalog entry -- it must not appear.
    available = available_custom_cards({"mushroom", "card-mod"})
    assert available == {"mushroom": CUSTOM_CARD_CATALOG["mushroom"]}


def test_available_custom_cards_empty_when_nothing_detected() -> None:
    assert available_custom_cards(set()) == {}


def test_allowed_custom_type_strings_flattens_all_domains() -> None:
    available = available_custom_cards({"mushroom", "bubble-card"})
    allowed = allowed_custom_type_strings(available)
    assert allowed == {
        "custom:mushroom-light-card",
        "custom:mushroom-climate-card",
        "custom:mushroom-cover-card",
        "custom:mushroom-fan-card",
        "custom:mushroom-entity-card",
        "custom:mushroom-title-card",
        "custom:bubble-card",
    }


def test_allowed_custom_type_strings_empty_for_empty_available() -> None:
    assert allowed_custom_type_strings({}) == set()
