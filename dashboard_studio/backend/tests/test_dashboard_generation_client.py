from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import anthropic
import httpx2
import pytest

from dashboard_studio.config import Settings
from dashboard_studio.dashboard.config import (
    DensityMode,
    GenerationStrategy,
    StyleFamily,
    StyleHint,
)
from dashboard_studio.dashboard.generation_client import (
    DashboardGenerationAuthError,
    DashboardGenerationClient,
    DashboardGenerationNotConfiguredError,
    DashboardGenerationRateLimitError,
    DashboardGenerationUpstreamError,
)
from dashboard_studio.dashboard.scope import (
    AreaSummary,
    CandidateEntitySummary,
    DomainCount,
    GeneratedViewSections,
    ScopeSummary,
    ViewProposal,
    ViewProposalEntitySelector,
    ViewStructureProposal,
)


def make_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "anthropic_api_key": "test-key",
        "anthropic_model": "claude-sonnet-5",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def make_scope_summary() -> ScopeSummary:
    return ScopeSummary(
        total_entities=2,
        areas=[
            AreaSummary(
                area_id="living_room",
                area_name="Living Room",
                floor_name=None,
                domain_counts=[DomainCount(domain="light", count=2)],
            )
        ],
    )


def make_structure_proposal() -> ViewStructureProposal:
    return ViewStructureProposal(
        views=[ViewProposal(name="Living Room", selector=ViewProposalEntitySelector(area_ids=["living_room"]))]
    )


def make_view_sections() -> GeneratedViewSections:
    return GeneratedViewSections(sections=[])


@dataclass
class FakeUsage:
    input_tokens: int = 100
    output_tokens: int = 50


@dataclass
class FakeResponse:
    parsed_output: Any
    usage: FakeUsage
    stop_reason: str = "end_turn"


class FakeMessagesAPI:
    def __init__(self, responder: Callable[[dict[str, Any]], FakeResponse]) -> None:
        self._responder = responder
        self.calls: list[dict[str, Any]] = []

    async def parse(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        return self._responder(kwargs)


class FakeSDKClient:
    def __init__(self, responder: Callable[[dict[str, Any]], FakeResponse]) -> None:
        self.messages = FakeMessagesAPI(responder)


def make_request() -> httpx2.Request:
    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def error_response(status_code: int, headers: dict[str, str] | None = None) -> httpx2.Response:
    return httpx2.Response(status_code, request=make_request(), headers=headers)


async def test_propose_view_structure_success() -> None:
    proposal = make_structure_proposal()

    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        return FakeResponse(parsed_output=proposal, usage=FakeUsage(input_tokens=300, output_tokens=100))

    fake_sdk = FakeSDKClient(responder)
    client = DashboardGenerationClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    result = await client.propose_view_structure(make_scope_summary(), GenerationStrategy.by_area)

    assert result.output == proposal
    assert result.input_tokens == 300
    assert result.output_tokens == 100
    assert result.estimated_cost_usd == pytest.approx((300 * 2.00 + 100 * 10.00) / 1_000_000)
    assert result.model == "claude-sonnet-5"
    assert fake_sdk.messages.calls[0]["output_format"] is ViewStructureProposal


async def test_generate_view_cards_success() -> None:
    sections = make_view_sections()

    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        return FakeResponse(parsed_output=sections, usage=FakeUsage())

    fake_sdk = FakeSDKClient(responder)
    client = DashboardGenerationClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    candidates = [
        CandidateEntitySummary(
            entity_id="light.a", domain="light", name="Light A", area_name="Living Room", device_class=None
        )
    ]
    style_hint = StyleHint(
        density_mode=DensityMode.comfortable, card_style="Tile-based", style_family=StyleFamily.flat
    )

    result = await client.generate_view_cards("Living Room", candidates, {}, style_hint)

    assert result.output == sections
    assert fake_sdk.messages.calls[0]["output_format"] is GeneratedViewSections


async def test_generate_view_cards_without_style_hint() -> None:
    sections = make_view_sections()

    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        return FakeResponse(parsed_output=sections, usage=FakeUsage())

    fake_sdk = FakeSDKClient(responder)
    client = DashboardGenerationClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    result = await client.generate_view_cards("Living Room", [], {}, None)

    assert result.output == sections


async def test_generate_view_cards_includes_custom_card_catalog_in_prompt() -> None:
    sections = make_view_sections()

    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        return FakeResponse(parsed_output=sections, usage=FakeUsage())

    fake_sdk = FakeSDKClient(responder)
    client = DashboardGenerationClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    available = {"mushroom": {"light": "custom:mushroom-light-card"}}
    await client.generate_view_cards("Living Room", [], available, None)

    prompt_text = fake_sdk.messages.calls[0]["messages"][0]["content"][0]["text"]
    assert "custom:mushroom-light-card" in prompt_text


async def test_unrecognized_model_has_no_cost_estimate() -> None:
    proposal = make_structure_proposal()

    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        return FakeResponse(parsed_output=proposal, usage=FakeUsage())

    fake_sdk = FakeSDKClient(responder)
    client = DashboardGenerationClient(
        make_settings(anthropic_model="some-future-model"), sdk_client=fake_sdk  # type: ignore[arg-type]
    )

    result = await client.propose_view_structure(make_scope_summary(), GenerationStrategy.automatic)

    assert result.estimated_cost_usd is None


async def test_propose_view_structure_not_configured_without_calling_sdk() -> None:
    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        raise AssertionError("should never be called when no API key is configured")

    fake_sdk = FakeSDKClient(responder)
    client = DashboardGenerationClient(
        make_settings(anthropic_api_key=""), sdk_client=fake_sdk  # type: ignore[arg-type]
    )

    with pytest.raises(DashboardGenerationNotConfiguredError):
        await client.propose_view_structure(make_scope_summary(), GenerationStrategy.by_area)

    assert fake_sdk.messages.calls == []


async def test_none_parsed_output_raises_upstream_error() -> None:
    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        return FakeResponse(parsed_output=None, usage=FakeUsage(), stop_reason="max_tokens")

    fake_sdk = FakeSDKClient(responder)
    client = DashboardGenerationClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    with pytest.raises(DashboardGenerationUpstreamError):
        await client.propose_view_structure(make_scope_summary(), GenerationStrategy.by_area)


async def test_maps_authentication_error() -> None:
    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        raise anthropic.AuthenticationError("bad key", response=error_response(401), body=None)

    fake_sdk = FakeSDKClient(responder)
    client = DashboardGenerationClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    with pytest.raises(DashboardGenerationAuthError):
        await client.propose_view_structure(make_scope_summary(), GenerationStrategy.by_area)


async def test_maps_permission_denied_error() -> None:
    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        raise anthropic.PermissionDeniedError("forbidden", response=error_response(403), body=None)

    fake_sdk = FakeSDKClient(responder)
    client = DashboardGenerationClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    with pytest.raises(DashboardGenerationAuthError):
        await client.propose_view_structure(make_scope_summary(), GenerationStrategy.by_area)


async def test_maps_rate_limit_error_with_retry_after() -> None:
    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        raise anthropic.RateLimitError(
            "rate limited", response=error_response(429, {"retry-after": "30"}), body=None
        )

    fake_sdk = FakeSDKClient(responder)
    client = DashboardGenerationClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    with pytest.raises(DashboardGenerationRateLimitError) as exc_info:
        await client.propose_view_structure(make_scope_summary(), GenerationStrategy.by_area)
    assert exc_info.value.retry_after == 30


async def test_maps_generic_status_error() -> None:
    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        raise anthropic.APIStatusError("server error", response=error_response(500), body=None)

    fake_sdk = FakeSDKClient(responder)
    client = DashboardGenerationClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    with pytest.raises(DashboardGenerationUpstreamError):
        await client.propose_view_structure(make_scope_summary(), GenerationStrategy.by_area)


async def test_maps_connection_error() -> None:
    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        raise anthropic.APIConnectionError(request=make_request())

    fake_sdk = FakeSDKClient(responder)
    client = DashboardGenerationClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    with pytest.raises(DashboardGenerationUpstreamError):
        await client.propose_view_structure(make_scope_summary(), GenerationStrategy.by_area)


async def test_generate_view_cards_maps_errors_too() -> None:
    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        raise anthropic.AuthenticationError("bad key", response=error_response(401), body=None)

    fake_sdk = FakeSDKClient(responder)
    client = DashboardGenerationClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    with pytest.raises(DashboardGenerationAuthError):
        await client.generate_view_cards("Living Room", [], {}, None)
