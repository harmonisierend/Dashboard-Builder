from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import anthropic
import httpx2
import pytest

from dashboard_studio.config import Settings
from dashboard_studio.design.anthropic_client import (
    AnthropicDesignClient,
    DesignAnalysisAuthError,
    DesignAnalysisNotConfiguredError,
    DesignAnalysisRateLimitError,
    DesignAnalysisUpstreamError,
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


def make_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "anthropic_api_key": "test-key",
        "anthropic_model": "claude-sonnet-5",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


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


@dataclass
class FakeUsage:
    input_tokens: int = 100
    output_tokens: int = 50


@dataclass
class FakeResponse:
    parsed_output: DesignTokenSet | None
    usage: FakeUsage
    stop_reason: str = "end_turn"


class FakeMessagesAPI:
    """Stands in for `AsyncAnthropic().messages` -- fakes the dependency
    (matching test_ws_client.py's FakeTransport pattern) rather than
    mocking anthropic's internals.
    """

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


async def test_analyze_design_success() -> None:
    token_set = make_token_set()

    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        return FakeResponse(parsed_output=token_set, usage=FakeUsage(input_tokens=1200, output_tokens=400))

    fake_sdk = FakeSDKClient(responder)
    client = AnthropicDesignClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    result = await client.analyze_design(b"fake-bytes", "image/png")

    assert result.tokens == token_set
    assert result.input_tokens == 1200
    assert result.output_tokens == 400
    assert result.estimated_cost_usd == pytest.approx((1200 * 2.00 + 400 * 10.00) / 1_000_000)
    assert result.model == "claude-sonnet-5"
    assert fake_sdk.messages.calls[0]["model"] == "claude-sonnet-5"
    assert fake_sdk.messages.calls[0]["output_format"] is DesignTokenSet


async def test_analyze_design_unrecognized_model_has_no_cost_estimate() -> None:
    token_set = make_token_set()

    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        return FakeResponse(parsed_output=token_set, usage=FakeUsage())

    fake_sdk = FakeSDKClient(responder)
    client = AnthropicDesignClient(
        make_settings(anthropic_model="some-future-model"), sdk_client=fake_sdk  # type: ignore[arg-type]
    )

    result = await client.analyze_design(b"fake-bytes", "image/png")

    assert result.estimated_cost_usd is None


async def test_analyze_design_not_configured_without_calling_sdk() -> None:
    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        raise AssertionError("should never be called when no API key is configured")

    fake_sdk = FakeSDKClient(responder)
    client = AnthropicDesignClient(
        make_settings(anthropic_api_key=""), sdk_client=fake_sdk  # type: ignore[arg-type]
    )

    with pytest.raises(DesignAnalysisNotConfiguredError):
        await client.analyze_design(b"fake-bytes", "image/png")

    assert fake_sdk.messages.calls == []


async def test_analyze_design_none_parsed_output_raises_upstream_error() -> None:
    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        return FakeResponse(parsed_output=None, usage=FakeUsage(), stop_reason="max_tokens")

    fake_sdk = FakeSDKClient(responder)
    client = AnthropicDesignClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    with pytest.raises(DesignAnalysisUpstreamError):
        await client.analyze_design(b"fake-bytes", "image/png")


async def test_analyze_design_maps_authentication_error() -> None:
    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        raise anthropic.AuthenticationError("bad key", response=error_response(401), body=None)

    fake_sdk = FakeSDKClient(responder)
    client = AnthropicDesignClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    with pytest.raises(DesignAnalysisAuthError):
        await client.analyze_design(b"fake-bytes", "image/png")


async def test_analyze_design_maps_permission_denied_error() -> None:
    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        raise anthropic.PermissionDeniedError("forbidden", response=error_response(403), body=None)

    fake_sdk = FakeSDKClient(responder)
    client = AnthropicDesignClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    with pytest.raises(DesignAnalysisAuthError):
        await client.analyze_design(b"fake-bytes", "image/png")


async def test_analyze_design_maps_rate_limit_error_with_retry_after() -> None:
    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        raise anthropic.RateLimitError(
            "rate limited", response=error_response(429, {"retry-after": "30"}), body=None
        )

    fake_sdk = FakeSDKClient(responder)
    client = AnthropicDesignClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    with pytest.raises(DesignAnalysisRateLimitError) as exc_info:
        await client.analyze_design(b"fake-bytes", "image/png")
    assert exc_info.value.retry_after == 30


async def test_analyze_design_maps_generic_status_error() -> None:
    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        raise anthropic.APIStatusError("server error", response=error_response(500), body=None)

    fake_sdk = FakeSDKClient(responder)
    client = AnthropicDesignClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    with pytest.raises(DesignAnalysisUpstreamError):
        await client.analyze_design(b"fake-bytes", "image/png")


async def test_analyze_design_maps_connection_error() -> None:
    def responder(_kwargs: dict[str, Any]) -> FakeResponse:
        raise anthropic.APIConnectionError(request=make_request())

    fake_sdk = FakeSDKClient(responder)
    client = AnthropicDesignClient(make_settings(), sdk_client=fake_sdk)  # type: ignore[arg-type]

    with pytest.raises(DesignAnalysisUpstreamError):
        await client.analyze_design(b"fake-bytes", "image/png")
