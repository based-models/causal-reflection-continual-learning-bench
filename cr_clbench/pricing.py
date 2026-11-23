"""Register the public model id in LiteLLM's price table.

The bench prices whatever model string it recorded. That string is
``openai/glm-5.3-flash:causal-reflection`` unless a caller strips the prefix.
Missing entries leave ``cost_usd`` null. Absent ``cached_tokens`` counts as zero
because the bench's usage helper already coerces a missing cache count to 0.
"""

from __future__ import annotations

import litellm

from .constants import (
    CACHED_INPUT_USD_PER_MILLION,
    CONTEXT_WINDOW_TOKENS,
    INKLING_CACHED_INPUT_USD_PER_MILLION,
    INKLING_CONTEXT_WINDOW_TOKENS,
    INKLING_INPUT_USD_PER_MILLION,
    INKLING_LITELLM_MODEL,
    INKLING_MAX_OUTPUT_TOKENS,
    INKLING_OUTPUT_USD_PER_MILLION,
    INKLING_PUBLIC_MODEL_ID,
    INPUT_USD_PER_MILLION,
    LITELLM_MODEL,
    MAX_OUTPUT_TOKENS,
    OUTPUT_USD_PER_MILLION,
    PUBLIC_MODEL_ID,
)

_PER_TOKEN = 1_000_000


def price_entry(
    *,
    input_usd_per_million: float = INPUT_USD_PER_MILLION,
    cached_input_usd_per_million: float = CACHED_INPUT_USD_PER_MILLION,
    output_usd_per_million: float = OUTPUT_USD_PER_MILLION,
    context_window_tokens: int = CONTEXT_WINDOW_TOKENS,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
) -> dict[str, float | int | str]:
    return {
        "input_cost_per_token": input_usd_per_million / _PER_TOKEN,
        "output_cost_per_token": output_usd_per_million / _PER_TOKEN,
        "cache_read_input_token_cost": cached_input_usd_per_million / _PER_TOKEN,
        "max_input_tokens": context_window_tokens,
        "max_output_tokens": max_output_tokens,
        "max_tokens": max_output_tokens,
        "litellm_provider": "openai",
        "mode": "chat",
    }


def register_prices() -> None:
    """Install price entries under both ids the bench may look up."""
    table = litellm.model_cost
    entries = (
        (
            (LITELLM_MODEL, PUBLIC_MODEL_ID),
            price_entry(),
        ),
        (
            (INKLING_LITELLM_MODEL, INKLING_PUBLIC_MODEL_ID),
            price_entry(
                input_usd_per_million=INKLING_INPUT_USD_PER_MILLION,
                cached_input_usd_per_million=INKLING_CACHED_INPUT_USD_PER_MILLION,
                output_usd_per_million=INKLING_OUTPUT_USD_PER_MILLION,
                context_window_tokens=INKLING_CONTEXT_WINDOW_TOKENS,
                max_output_tokens=INKLING_MAX_OUTPUT_TOKENS,
            ),
        ),
    )
    for keys, entry in entries:
        for key in keys:
            table[key] = dict(entry)
