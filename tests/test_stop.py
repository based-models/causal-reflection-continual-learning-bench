"""Stop the run on a contract failure or the monthly spend cap."""

from cr_clbench.stop import (
    CommandParseStop,
    ResponseFormatStop,
    SpendCapStop,
    classify_stop,
)


def test_spend_cap_is_an_api_limit():
    exc = RuntimeError("LLM call failed: monthly spend cap reached (10.00 of 10.00 USD)")
    stopped = classify_stop(exc)
    assert isinstance(stopped, SpendCapStop)


def test_validation_failure_stops_for_command_parse():
    validation_error = type("ValidationError", (Exception,), {})("command field required")
    wrapped = RuntimeError("LLM call failed: 1 validation error")
    wrapped.__cause__ = validation_error
    assert isinstance(classify_stop(wrapped), CommandParseStop)


def test_response_format_rejection_stops():
    exc = type("BadRequestError", (Exception,), {})(
        "response_format is not supported for this model"
    )
    stopped = classify_stop(exc)
    assert isinstance(stopped, ResponseFormatStop)


def test_transport_errors_stay_with_the_bench():
    exc = RuntimeError("LLM call failed: connection reset")
    assert classify_stop(exc) is None
