"""LiteLLM price entry used by the bench's usage helper."""

import pytest
from src.usage import build_usage_event, build_usage_event_from_response

from cr_clbench.constants import LITELLM_MODEL, PUBLIC_MODEL_ID
from cr_clbench.pricing import register_prices


def setup_module() -> None:
    register_prices()


def test_cost_uses_input_cached_input_and_output_rates():
    event = build_usage_event(
        model=LITELLM_MODEL,
        input_tokens=1_000_000,
        output_tokens=500_000,
        cached_input_tokens=200_000,
    )
    # 800k fresh input at $0.15, 200k cached at $0.03, 500k output at $0.50.
    assert event.cost_usd == 0.376
    assert event.pricing_error is None


def test_missing_cached_tokens_count_as_zero():
    event = build_usage_event(
        model=LITELLM_MODEL,
        input_tokens=1_000,
        output_tokens=1_000,
        cached_input_tokens=None,
    )
    assert event.cost_usd is not None
    assert event.cached_input_tokens is None
    assert abs(event.cost_usd - (1000 * 0.15 + 1000 * 0.50) / 1_000_000) < 1e-12


def test_public_id_is_in_the_rate_table_the_bench_looks_up():
    """The bench tries the full string, then the id with the provider prefix removed.

    ``cost_per_token`` still receives the original string. ICL stores the
    ``openai/`` id, which is the call that fills ``cost_usd``. The bare id has
    to be in the table so a tier lookup after the prefix is stripped still
    finds these rates.
    """
    from src.usage import _lookup_model_rates

    rates = _lookup_model_rates(PUBLIC_MODEL_ID, None)
    assert rates is not None
    assert rates["input_cost_per_token"] == 0.15 / 1_000_000
    assert rates["cache_read_input_token_cost"] == 0.03 / 1_000_000
    assert rates["output_cost_per_token"] == 0.50 / 1_000_000


def test_response_usage_still_fills_cost_usd():
    # The bench prices a real completion response before token counts alone.
    # A dict is the shape ``completion_cost`` accepts; a bare namespace is not.
    response = {
        "id": "cmpl",
        "model": LITELLM_MODEL,
        "usage": {
            "prompt_tokens": 2_000,
            "completion_tokens": 1_000,
            "total_tokens": 3_000,
            "prompt_tokens_details": {"cached_tokens": 500},
        },
    }
    event = build_usage_event_from_response(model=LITELLM_MODEL, response=response)
    assert event.input_tokens == 2_000
    assert event.output_tokens == 1_000
    assert event.cached_input_tokens == 500
    # 1,500 fresh input at $0.15, 500 cached at $0.03, 1,000 output at $0.50.
    assert event.cost_usd == pytest.approx(0.00074)
