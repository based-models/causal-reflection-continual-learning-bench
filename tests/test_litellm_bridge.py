"""Gateway kwargs added around ICL's chat completion."""

from pydantic import BaseModel

from cr_clbench.litellm_bridge import prepare_completion_kwargs


class _Action(BaseModel):
    thought: str
    command: str


def test_prepare_keeps_response_format_and_drops_thinking_switches():
    prepared = prepare_completion_kwargs(
        {
            "model": "openai/glm-5.3-flash:causal-reflection",
            "messages": [{"role": "user", "content": "hi"}],
            "response_format": _Action,
            "reasoning_effort": "low",
            "chat_template_kwargs": {"enable_thinking": False},
            "extra_body": {"reasoning_effort": "low", "chat_template_kwargs": {}},
        },
        extra_headers={
            "X-Session-Id": "session",
            "X-Run-Id": "run",
            "X-Workload": "coding",
        },
        api_base="https://api.basedmodels.com/v1",
        api_key="secret",
    )
    assert prepared["response_format"] is _Action
    assert prepared["extra_headers"]["X-Session-Id"] == "session"
    assert prepared["extra_headers"]["X-Workload"] == "coding"
    assert prepared["api_base"] == "https://api.basedmodels.com/v1"
    assert prepared["api_key"] == "secret"
    assert "reasoning_effort" not in prepared
    assert "chat_template_kwargs" not in prepared
    assert "extra_body" not in prepared


def test_prepare_refuses_a_missing_session_header():
    try:
        prepare_completion_kwargs(
            {},
            extra_headers={"X-Run-Id": "run", "X-Workload": "coding"},
            api_base="https://api.basedmodels.com/v1",
            api_key="secret",
        )
    except ValueError as exc:
        assert "X-Session-Id" in str(exc)
    else:
        raise AssertionError("missing session id was accepted")
