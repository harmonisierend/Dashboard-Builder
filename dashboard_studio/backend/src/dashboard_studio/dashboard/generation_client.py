"""Anthropic text calls that turn a scoped entity inventory into a proposed
dashboard structure (phase 1) and, per view, a set of Lovelace cards
(phase 2).

Mirrors design/anthropic_client.py's shape exactly: same typed exception
hierarchy, same injectable-SDK-client pattern for testing (fake the
dependency, never mock library internals), same cost estimation via
design/pricing.py::estimate_cost_usd. Unlike the vision call, both calls
here are text-only -- no image content blocks.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import anthropic
from anthropic.types import MessageParam

from dashboard_studio.config import Settings
from dashboard_studio.dashboard.config import GenerationStrategy, StyleHint
from dashboard_studio.dashboard.scope import (
    CandidateEntitySummary,
    GeneratedViewSections,
    ScopeSummary,
    ViewStructureProposal,
)
from dashboard_studio.design.pricing import estimate_cost_usd

log = logging.getLogger(__name__)

STRUCTURE_MAX_TOKENS = 2000
VIEW_MAX_TOKENS = 6000

STRATEGY_INSTRUCTIONS: dict[GenerationStrategy, str] = {
    GenerationStrategy.by_area: (
        "Strukturiere die Ansichten nach Bereichen (Areas) -- eine Ansicht pro Bereich "
        "oder pro sinnvoll zusammengefasster Gruppe von Bereichen."
    ),
    GenerationStrategy.by_domain: (
        "Strukturiere die Ansichten nach Domains (z. B. Licht, Klima, Sicherheit) "
        "unabhaengig von Bereichen."
    ),
    GenerationStrategy.automatic: (
        "Waehle die sinnvollste Struktur selbst -- nach Bereichen, nach Domains, "
        "oder eine Mischung, je nachdem was fuer dieses Entity-Inventar am besten passt."
    ),
}

STRUCTURE_PROMPT_TEMPLATE = """\
Du planst die View-Struktur (Ansichten/Tabs) eines Home Assistant \
Lovelace-Dashboards anhand einer Zusammenfassung des verfuegbaren \
Entity-Inventars.

{strategy_instruction}

Schlage fuer jede Ansicht einen kurzen, klaren Namen vor und einen \
Selektor (Bereichs-IDs und/oder Domains), der beschreibt, welche \
Entitaeten in diese Ansicht gehoeren. Der Selektor muss ausschliesslich \
Bereichs-IDs und Domain-Namen verwenden, die in der Zusammenfassung unten \
tatsaechlich vorkommen. Schlage nicht mehr als 8 Ansichten vor.

Entity-Inventar-Zusammenfassung (JSON):
{scope_summary_json}
"""

VIEW_CARDS_PROMPT_TEMPLATE = """\
Du erstellst die Karten (Cards) fuer eine einzelne Ansicht eines Home \
Assistant Lovelace-Dashboards im "sections"-Layout.

Ansicht: {view_name}

Verwende ausschliesslich die folgenden nativen Kartentypen: tile, heading, \
entities, thermostat, history-graph, weather-forecast, light, \
media-control.

{custom_card_instruction}

Verwende als `entity`- oder `entities`-Werte ausschliesslich Entity-IDs aus \
der folgenden Kandidatenliste -- erfinde niemals eine Entity-ID, die dort \
nicht vorkommt.

Kandidaten (JSON):
{candidates_json}

{style_instruction}

Gruppiere verwandte Entitaeten sinnvoll in Sections und Cards. Wenn keine \
sinnvollen Karten aus den Kandidaten gebildet werden koennen, gib eine \
leere Section-Liste zurueck.
"""


class DashboardGenerationError(RuntimeError):
    """Base class for dashboard-generation errors."""


class DashboardGenerationNotConfiguredError(DashboardGenerationError):
    """Raised when no Anthropic API key is configured."""


class DashboardGenerationAuthError(DashboardGenerationError):
    """Raised when Anthropic rejects the configured API key."""


class DashboardGenerationRateLimitError(DashboardGenerationError):
    def __init__(self, message: str, retry_after: int | None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class DashboardGenerationUpstreamError(DashboardGenerationError):
    """Raised for upstream Anthropic API/connection failures."""


@dataclass
class GenerationCallResult[T]:
    output: T
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None
    model: str


def _style_instruction(style_hint: StyleHint | None) -> str:
    if style_hint is None:
        return "Es liegt kein Style-Hinweis vor -- verwende sinnvolle Standardwerte."
    return (
        "Beruecksichtige folgenden Style-Hinweis bei Dichte- und Kartenwahl (JSON): "
        f"{style_hint.model_dump_json()}"
    )


def _custom_card_instruction(available_custom_cards: dict[str, dict[str, str]]) -> str:
    if not available_custom_cards:
        return "Es sind keine zusaetzlichen Custom-Card-Typen verfuegbar -- verwende nur native Karten."
    return (
        "Zusaetzlich sind folgende Custom-Card-Typen installiert und duerfen als "
        "`custom_type` verwendet werden (Familie -> Domain -> exakter Typ-String, JSON): "
        f"{json.dumps(available_custom_cards)}"
    )


class DashboardGenerationClient:
    def __init__(
        self,
        settings: Settings,
        sdk_client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        self._settings = settings
        self._client = sdk_client or anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key or "unset"
        )

    async def propose_view_structure(
        self, scope_summary: ScopeSummary, strategy: GenerationStrategy
    ) -> GenerationCallResult[ViewStructureProposal]:
        prompt = STRUCTURE_PROMPT_TEMPLATE.format(
            strategy_instruction=STRATEGY_INSTRUCTIONS[strategy],
            scope_summary_json=scope_summary.model_dump_json(),
        )
        return await self._call(
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            output_format=ViewStructureProposal,
            max_tokens=STRUCTURE_MAX_TOKENS,
        )

    async def generate_view_cards(
        self,
        view_name: str,
        candidates: list[CandidateEntitySummary],
        available_custom_cards: dict[str, dict[str, str]],
        style_hint: StyleHint | None,
    ) -> GenerationCallResult[GeneratedViewSections]:
        prompt = VIEW_CARDS_PROMPT_TEMPLATE.format(
            view_name=view_name,
            custom_card_instruction=_custom_card_instruction(available_custom_cards),
            candidates_json=json.dumps([c.model_dump() for c in candidates]),
            style_instruction=_style_instruction(style_hint),
        )
        return await self._call(
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            output_format=GeneratedViewSections,
            max_tokens=VIEW_MAX_TOKENS,
        )

    async def _call[T](
        self,
        *,
        messages: list[MessageParam],
        output_format: type[T],
        max_tokens: int,
    ) -> GenerationCallResult[T]:
        if not self._settings.anthropic_api_key:
            raise DashboardGenerationNotConfiguredError(
                "Kein Anthropic-API-Key konfiguriert. Bitte in den App-Optionen hinterlegen."
            )

        try:
            response = await self._client.messages.parse(
                model=self._settings.anthropic_model,
                max_tokens=max_tokens,
                messages=messages,
                output_format=output_format,
            )
        except anthropic.AuthenticationError as exc:
            raise DashboardGenerationAuthError(
                "Anthropic-API-Key wurde abgelehnt. Bitte in den App-Optionen pruefen."
            ) from exc
        except anthropic.PermissionDeniedError as exc:
            raise DashboardGenerationAuthError(
                "Anthropic-API-Key hat nicht die noetigen Berechtigungen."
            ) from exc
        except anthropic.RateLimitError as exc:
            retry_after_raw = exc.response.headers.get("retry-after")
            retry_after = int(retry_after_raw) if retry_after_raw else None
            raise DashboardGenerationRateLimitError(
                "Anthropic-API-Rate-Limit erreicht. Bitte spaeter erneut versuchen.", retry_after
            ) from exc
        except anthropic.APIStatusError as exc:
            raise DashboardGenerationUpstreamError(
                f"Anthropic-API-Fehler ({exc.status_code}): {exc.message}"
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise DashboardGenerationUpstreamError(
                "Anthropic-API war nicht erreichbar. Bitte spaeter erneut versuchen."
            ) from exc

        usage = response.usage
        cost = estimate_cost_usd(self._settings.anthropic_model, usage.input_tokens, usage.output_tokens)
        log.info(
            "Dashboard generation call: model=%s output_format=%s input_tokens=%d "
            "output_tokens=%d estimated_cost_usd=%s stop_reason=%s",
            self._settings.anthropic_model,
            output_format.__name__,
            usage.input_tokens,
            usage.output_tokens,
            cost,
            response.stop_reason,
        )

        if response.parsed_output is None:
            raise DashboardGenerationUpstreamError(
                "Anthropic hat kein gueltiges Ergebnis geliefert "
                f"(stop_reason={response.stop_reason}). Bitte erneut versuchen."
            )

        return GenerationCallResult(
            output=response.parsed_output,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            estimated_cost_usd=cost,
            model=self._settings.anthropic_model,
        )
