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
    INPUT_USD_PER_MILLION,
    LITELLM_MODEL,
    MAX_OUTPUT_TOKENS,
    OUTPUT_USD_PER_MILLION,
    PUBLIC_MODEL_ID,
)

_PER_TOKEN = 1_000_000


def price_entry() -> dict[str, float | int | str]:
    return {
        "input_cost_per_token": INPUT_USD_PER_MILLION / _PER_TOKEN,
        "output_cost_per_token": OUTPUT_USD_PER_MILLION / _PER_TOKEN,
        "cache_read_input_token_cost": CACHED_INPUT_USD_PER_MILLION / _PER_TOKEN,
        "max_input_tokens": CONTEXT_WINDOW_TOKENS,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "litellm_provider": "openai",
        "mode": "chat",
    }


def register_prices() -> None:
    """Install the price entry under both ids the bench may look up."""
    entry = price_entry()
    table = litellm.model_cost
    for key in (LITELLM_MODEL, PUBLIC_MODEL_ID):
        table[key] = dict(entry)
