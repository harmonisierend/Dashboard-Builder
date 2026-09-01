"""Rough cost estimation for Anthropic API calls.

Per the M1 decision, there is no hard budget cap -- calls are never blocked
on cost. This is purely for logging and surfacing an estimate in the UI.
Prices are USD per 1M tokens, (input, output); an unrecognized configured
model returns None rather than guessing.
"""

from __future__ import annotations

PRICING_USD_PER_MILLION: dict[str, tuple[float, float]] = {
    "claude-sonnet-5": (2.00, 10.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    prices = PRICING_USD_PER_MILLION.get(model)
    if prices is None:
        return None
    input_price, output_price = prices
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
