"""Anthropic vision call that turns a design-reference image into a
DesignTokenSet.

Uses `messages.parse(output_format=DesignTokenSet)` -- Anthropic's
structured-output API -- rather than prompting for JSON and hand-parsing
it, so the response is guaranteed to validate against the schema. Vision
input (an `image` content block) combined with `output_format` in the same
call is a documented, intended use case ("Extract data from images or
text"), not a workaround.

Mirrors ha/ws_client.py's shape: a typed exception hierarchy, and the SDK
client is injectable so tests can fake it instead of mocking library
internals (matching the FakeTransport pattern in test_ws_client.py).
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass

import anthropic
from anthropic.types import Base64ImageSourceParam, ImageBlockParam, MessageParam, TextBlockParam

from dashboard_studio.config import Settings
from dashboard_studio.design.pricing import estimate_cost_usd
from dashboard_studio.design.tokens import DesignTokenSet
from dashboard_studio.design.uploads import AllowedMediaType

log = logging.getLogger(__name__)

ANALYSIS_PROMPT = """\
You are analyzing a design reference image (a screenshot, mockup, or photo \
of a UI) to derive an abstract design-token set for a Home Assistant \
dashboard.

Extract only abstract design characteristics -- colors, typography, \
spacing, and visual style -- never attempt to reproduce the specific \
layout, content, or copyrighted elements of the reference image. The goal \
is a reusable style direction, not a clone.

For each token:
- Colors: pick a primary, accent, background, surface, on-surface \
(text-on-surface), state-on, state-off, warn, and critical color from the \
image's palette. For each, also produce a sensible dark-mode variant even \
if the reference image is light-mode only (and vice versa) -- infer a \
plausible variant using standard dark-mode conventions (darkened \
backgrounds, lightened text, etc).
- Typography: identify the general font family/stack in use (or the \
closest standard web-safe/system font family if the exact font can't be \
identified), a 5-step size scale (xs/sm/md/lg/xl) as CSS length strings, \
and font weights (regular/medium/bold) as numeric values.
- Form: estimate border-radius and border-width in pixels, describe the \
shadow style as a CSS box-shadow value, and classify the overall style as \
"glass" (translucent/blurred), "flat" (no depth effects), or "neumorphic" \
(soft embossed shadows).
- Density: classify as "compact" or "comfortable", and estimate grid-gap \
and section-spacing in pixels.
- Card style: classify the dominant card/component style. Common examples \
include "Mushroom-like" (rounded, icon-forward, minimal chrome), \
"Bubble-like" (large rounded pill-shaped cards), "Minimal-Native" (close \
to Home Assistant's default look), and "Tile-based" (grid of uniform \
square/rectangular tiles) -- but use your own judgment and a different \
label if none of these fit well. Briefly explain your reasoning.
"""


class DesignAnalysisError(RuntimeError):
    """Base class for design-analysis errors."""


class DesignAnalysisNotConfiguredError(DesignAnalysisError):
    """Raised when no Anthropic API key is configured."""


class DesignAnalysisAuthError(DesignAnalysisError):
    """Raised when Anthropic rejects the configured API key."""


class DesignAnalysisRateLimitError(DesignAnalysisError):
    def __init__(self, message: str, retry_after: int | None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class DesignAnalysisUpstreamError(DesignAnalysisError):
    """Raised for upstream Anthropic API/connection failures."""


@dataclass
class DesignAnalysisResult:
    tokens: DesignTokenSet
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None
    model: str


class AnthropicDesignClient:
    def __init__(
        self,
        settings: Settings,
        sdk_client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        self._settings = settings
        # Constructing the SDK client does no network I/O, so this is safe
        # even when no key is configured yet -- analyze_design() checks
        # settings.anthropic_api_key explicitly first, for a clear "not
        # configured" message instead of a generic auth failure.
        self._client = sdk_client or anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key or "unset"
        )

    async def analyze_design(
        self, image_bytes: bytes, media_type: AllowedMediaType
    ) -> DesignAnalysisResult:
        if not self._settings.anthropic_api_key:
            raise DesignAnalysisNotConfiguredError(
                "Kein Anthropic-API-Key konfiguriert. Bitte in den App-Optionen hinterlegen."
            )

        image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        image_block: ImageBlockParam = {
            "type": "image",
            "source": Base64ImageSourceParam(
                type="base64", media_type=media_type, data=image_b64
            ),
        }
        text_block: TextBlockParam = {"type": "text", "text": ANALYSIS_PROMPT}
        message: MessageParam = {"role": "user", "content": [image_block, text_block]}

        try:
            response = await self._client.messages.parse(
                model=self._settings.anthropic_model,
                max_tokens=8000,
                messages=[message],
                output_format=DesignTokenSet,
            )
        except anthropic.AuthenticationError as exc:
            raise DesignAnalysisAuthError(
                "Anthropic-API-Key wurde abgelehnt. Bitte in den App-Optionen prüfen."
            ) from exc
        except anthropic.PermissionDeniedError as exc:
            raise DesignAnalysisAuthError(
                "Anthropic-API-Key hat nicht die nötigen Berechtigungen."
            ) from exc
        except anthropic.RateLimitError as exc:
            # .response is always set on APIStatusError subclasses (an HTTP
            # response was received, just with a 429 status).
            retry_after_raw = exc.response.headers.get("retry-after")
            retry_after = int(retry_after_raw) if retry_after_raw else None
            raise DesignAnalysisRateLimitError(
                "Anthropic-API-Rate-Limit erreicht. Bitte später erneut versuchen.", retry_after
            ) from exc
        except anthropic.APIStatusError as exc:
            raise DesignAnalysisUpstreamError(
                f"Anthropic-API-Fehler ({exc.status_code}): {exc.message}"
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise DesignAnalysisUpstreamError(
                "Anthropic-API war nicht erreichbar. Bitte später erneut versuchen."
            ) from exc

        usage = response.usage
        cost = estimate_cost_usd(
            self._settings.anthropic_model, usage.input_tokens, usage.output_tokens
        )
        log.info(
            "Design analysis call: model=%s input_tokens=%d output_tokens=%d "
            "estimated_cost_usd=%s stop_reason=%s",
            self._settings.anthropic_model,
            usage.input_tokens,
            usage.output_tokens,
            cost,
            response.stop_reason,
        )

        # ParsedMessage.parsed_output is Optional -- it's None if the model
        # stopped (e.g. hit max_tokens, or refused) before producing output
        # that validated against DesignTokenSet. Never pass None where a
        # DesignTokenSet is expected downstream.
        if response.parsed_output is None:
            raise DesignAnalysisUpstreamError(
                "Anthropic hat kein gültiges Design-Token-Set geliefert "
                f"(stop_reason={response.stop_reason}). Bitte erneut versuchen."
            )

        return DesignAnalysisResult(
            tokens=response.parsed_output,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            estimated_cost_usd=cost,
            model=self._settings.anthropic_model,
        )
