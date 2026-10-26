"""The ICL wrapper sends one observation message and the coding headers."""

import os

import litellm
import pytest
from pydantic import BaseModel
from src.interface import Observation, Query

from cr_clbench.integrate import override_scope
from cr_clbench.sessions import RunScope
from cr_clbench.stop import CausalReflectionStop, CommandParseStop, ResponseFormatStop
from cr_clbench.system import CausalReflectionICL


class _Action(BaseModel):
    thought: str
    command: str


def _response() -> litellm.ModelResponse:
    return litellm.ModelResponse(
        id="cmpl-test",
        model="openai/glm-5.3-flash:causal-reflection",
        choices=[
            {
                "message": {
                    "role": "assistant",
                    "content": '{"thought": "run tests", "command": "pytest -q"}',
                }
            }
        ],
        usage={
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
        },
    )


def _query(instance_id: str, prompt: str = "Fix the issue.") -> Query:
    return Query(
        prompt=prompt,
        response_schema=_Action,
        instance_id=instance_id,
        instance_index=0,
    )


@pytest.fixture
def system(monkeypatch):
    monkeypatch.setenv("CRA_API_KEY", "test-key")
    monkeypatch.delenv("CLBENCH_RUN_TAG", raising=False)
    monkeypatch.setattr(
        "src.systems.utils.structured_output._model_supports_response_format",
        lambda model: True,
    )
    calls: list[dict] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return _response()

    monkeypatch.setattr(litellm, "completion", fake_completion)
    created = CausalReflectionICL()
    created._calls = calls  # type: ignore[attr-defined]
    return created


def test_stateful_turns_share_a_session_and_the_next_user_message_has_the_footer(system):
    scope = RunScope(
        phase="run",
        reset_between_instances=False,
        run_index=0,
        task_name="codebase_adaptation",
    )
    with override_scope(scope):
        system.respond(_query("jazzband__tablib-534"))
        system.observe(
            Observation(
                content="<returncode>0</returncode>\n<output>\n3 passed in 0.42s\n</output>",
                instance_complete=False,
            )
        )
        system.respond(_query("jazzband__tablib-540", "What's your next command?"))

    calls = system._calls
    assert len(calls) == 2
    assert calls[0]["extra_headers"]["X-Session-Id"] == calls[1]["extra_headers"]["X-Session-Id"]
    assert calls[0]["extra_headers"]["X-Session-Id"] == (
        "clbench-codebase-glm-stateful-r1-codebase_adaptation"
    )
    assert calls[1]["extra_headers"]["X-Run-Id"] == "clbench-codebase-glm-r1"
    assert calls[1]["extra_headers"]["X-Workload"] == "coding"
    assert calls[1]["api_base"] == "https://api.basedmodels.com/v1"
    assert calls[1]["api_key"] == "test-key"
    assert calls[1]["response_format"] is _Action
    assert "reasoning_effort" not in calls[1]
    assert "chat_template_kwargs" not in calls[1]
    messages = calls[1]["messages"]
    assert messages[-2]["role"] == "assistant"
    assert "pytest -q" in messages[-2]["content"]
    assert messages[-1]["role"] == "user"
    assert "3 passed in 0.42s" in messages[-1]["content"]
    assert messages[-1]["content"].endswith("What's your next command?")
    events = system.consume_usage_events()
    assert events[-1].cost_usd == pytest.approx(100 * 0.15 / 1_000_000 + 20 * 0.50 / 1_000_000)


def test_stateless_instances_get_distinct_sessions(system):
    scope = RunScope(
        phase="baseline",
        reset_between_instances=True,
        run_index=None,
        task_name="codebase_adaptation",
    )
    with override_scope(scope):
        system.respond(_query("jazzband__tablib-534"))
        system.reset()
        system.respond(_query("jd__tenacity-597"))
    sessions = [call["extra_headers"]["X-Session-Id"] for call in system._calls]
    assert sessions[0].endswith("jazzband__tablib-534")
    assert sessions[1].endswith("jd__tenacity-597")
    assert sessions[0] != sessions[1]
    assert system._calls[0]["extra_headers"]["X-Run-Id"] == "clbench-codebase-glm-r0"


def test_reset_drops_output_that_was_not_sent_yet(system):
    system.observe(Observation(content="3 passed in 0.42s\n"))
    system.reset()
    system.respond(_query("jazzband__tablib-534", "Start."))
    assert "3 passed in 0.42s" not in system._calls[-1]["messages"][-1]["content"]


def test_missing_api_key_stops_before_a_call(monkeypatch):
    monkeypatch.delenv("CRA_API_KEY", raising=False)
    monkeypatch.setattr(
        "src.systems.utils.structured_output._model_supports_response_format",
        lambda model: True,
    )
    system = CausalReflectionICL()
    with pytest.raises(CausalReflectionStop, match="CRA_API_KEY"):
        system.respond(_query("jazzband__tablib-534"))


def test_missing_response_format_stops(monkeypatch):
    monkeypatch.setenv("CRA_API_KEY", "test-key")
    monkeypatch.setattr(
        "src.systems.utils.structured_output._model_supports_response_format",
        lambda model: False,
    )

    def fake_completion(**kwargs):
        return _response()

    monkeypatch.setattr(litellm, "completion", fake_completion)
    system = CausalReflectionICL()
    with pytest.raises(ResponseFormatStop):
        system.respond(_query("jazzband__tablib-534"))


class _QueryAction(BaseModel):
    action: str
    content: str


def _query_completion(body: str) -> litellm.ModelResponse:
    return litellm.ModelResponse(
        id="cmpl-query",
        model="openai/glm-5.3-flash:causal-reflection",
        choices=[{"message": {"role": "assistant", "content": body}}],
        usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    )


def test_query_turns_keep_the_sql_result_and_do_not_promote_a_runner_footer(monkeypatch):
    monkeypatch.setenv("CRA_API_KEY", "test-key")
    monkeypatch.delenv("CLBENCH_RUN_TAG", raising=False)
    monkeypatch.setattr(
        "src.systems.utils.structured_output._model_supports_response_format",
        lambda model: True,
    )
    calls: list[dict] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return _query_completion('{"action": "QUERY", "content": ".tables"}')

    monkeypatch.setattr(litellm, "completion", fake_completion)
    system = CausalReflectionICL()
    scope = RunScope(
        phase="run",
        reset_between_instances=False,
        run_index=0,
        task_name="database_exploration",
    )
    observation = ("x" * 2100) + "\n1 failed in 0.15s"
    with override_scope(scope):
        system.respond(
            Query(
                prompt="Question 1/1\n\nHow many?",
                response_schema=_QueryAction,
                instance_id="1",
                instance_index=0,
            )
        )
        system.observe(Observation(content=observation, instance_complete=False))
        system.respond(
            Query(
                prompt="Question 1/1\n\nHow many?",
                response_schema=_QueryAction,
                instance_id="1",
                instance_index=0,
            )
        )
    assert calls[1]["extra_headers"]["X-Workload"] == "query"
    assert calls[1]["extra_headers"]["X-Session-Id"] == (
        "clbench-database-glm-stateful-r1-database_exploration"
    )
    message = calls[1]["messages"][-1]["content"]
    assert message.startswith("x")
    assert "1 failed in 0.15s" in message
    assert message.endswith("How many?")
    assert calls[1]["response_format"] is _QueryAction


def test_empty_query_sql_stops(monkeypatch):
    monkeypatch.setenv("CRA_API_KEY", "test-key")
    monkeypatch.setattr(
        "src.systems.utils.structured_output._model_supports_response_format",
        lambda model: True,
    )
    monkeypatch.setattr(
        litellm,
        "completion",
        lambda **kwargs: _query_completion('{"action": "QUERY", "content": "  "}'),
    )
    system = CausalReflectionICL()
    scope = RunScope(
        phase="run",
        reset_between_instances=False,
        run_index=0,
        task_name="database_exploration",
    )
    with override_scope(scope):
        with pytest.raises(CommandParseStop, match="SQL"):
            system.respond(
                Query(
                    prompt="Question 1/1",
                    response_schema=_QueryAction,
                    instance_id="1",
                    instance_index=0,
                )
            )


class _ForecastCommand(BaseModel):
    thought: str
    command: str


class _ForecastSubmission(BaseModel):
    predictions: list[dict]


class _CohortTool(BaseModel):
    thought: str
    tool_call: dict


class _CohortSubmission(BaseModel):
    cohort_01__s12: float
    cohort_01__s24: float
    cohort_01__s36: float


def _json_completion(body: str) -> litellm.ModelResponse:
    return litellm.ModelResponse(
        id="cmpl-pack",
        model="openai/glm-5.3-flash:causal-reflection",
        choices=[{"message": {"role": "assistant", "content": body}}],
        usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    )


def test_forecast_keeps_shell_output_and_accepts_the_prediction_list(monkeypatch):
    monkeypatch.setenv("CRA_API_KEY", "test-key")
    monkeypatch.delenv("CLBENCH_RUN_TAG", raising=False)
    monkeypatch.setattr(
        "src.systems.utils.structured_output._model_supports_response_format",
        lambda model: True,
    )
    calls: list[dict] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        schema = kwargs.get("response_format")
        if schema is _ForecastSubmission:
            return _json_completion('{"predictions": []}')
        return _json_completion('{"thought": "fit", "command": "python3 fit_panel.py"}')

    monkeypatch.setattr(litellm, "completion", fake_completion)
    system = CausalReflectionICL()
    scope = RunScope(
        phase="run",
        reset_between_instances=False,
        run_index=0,
        task_name="sales_prediction",
    )
    observation = ("y" * 2100) + "\n1 failed in 0.15s"
    with override_scope(scope):
        system.respond(
            Query(
                prompt="Forecast 2027.",
                response_schema=_ForecastCommand,
                instance_id="sales_prediction:default:years:2027-2031",
                instance_index=0,
            )
        )
        system.observe(Observation(content=observation, instance_complete=False))
        system.respond(
            Query(
                prompt="Provide your best predictions.",
                response_schema=_ForecastSubmission,
                instance_id="sales_prediction:default:years:2027-2031",
                instance_index=0,
            )
        )
    assert calls[0]["extra_headers"]["X-Workload"] == "forecast"
    assert calls[0]["extra_headers"]["X-Session-Id"] == (
        "clbench-sales-glm-stateful-r1-sales_prediction"
    )
    message = calls[1]["messages"][-1]["content"]
    assert message.startswith("y")
    assert message.index("1 failed in 0.15s") > 2000
    assert message.endswith("Provide your best predictions.")


def test_forecast_without_a_command_or_predictions_stops(monkeypatch):
    monkeypatch.setenv("CRA_API_KEY", "test-key")
    monkeypatch.setattr(
        "src.systems.utils.structured_output._model_supports_response_format",
        lambda model: True,
    )
    monkeypatch.setattr(
        litellm,
        "completion",
        lambda **kwargs: _json_completion('{"thought": "stuck"}'),
    )
    system = CausalReflectionICL()
    scope = RunScope(
        phase="run",
        reset_between_instances=False,
        run_index=0,
        task_name="sales_prediction",
    )
    with override_scope(scope):
        with pytest.raises(CommandParseStop, match="predictions"):
            system.respond(
                Query(
                    prompt="Forecast.",
                    response_schema=_ForecastCommand,
                    instance_id="year",
                    instance_index=0,
                )
            )


def test_cohort_tool_call_uses_the_cohort_header(monkeypatch):
    monkeypatch.setenv("CRA_API_KEY", "test-key")
    monkeypatch.delenv("CLBENCH_RUN_TAG", raising=False)
    monkeypatch.setattr(
        "src.systems.utils.structured_output._model_supports_response_format",
        lambda model: True,
    )
    calls: list[dict] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        if kwargs.get("response_format") is _CohortSubmission:
            return _json_completion(
                '{"cohort_01__s12": 0.8, "cohort_01__s24": 0.5, "cohort_01__s36": 0.3}'
            )
        return _json_completion(
            '{"thought": "list columns", "tool_call": {"tool": "get_database_metadata"}}'
        )

    monkeypatch.setattr(litellm, "completion", fake_completion)
    system = CausalReflectionICL()
    scope = RunScope(
        phase="run",
        reset_between_instances=False,
        run_index=0,
        task_name="cohort_studies",
    )
    with override_scope(scope):
        system.respond(
            Query(
                prompt="Study 1/20: HERALD Panel",
                response_schema=_CohortTool,
                instance_id="cohort_studies:herald_suburban",
                instance_index=0,
            )
        )
        system.observe(
            Observation(content="=== Columns ===\n  age: Patient age  units=years", instance_complete=False)
        )
        system.respond(
            Query(
                prompt="Provide your survival estimates for all 36 cohorts.",
                response_schema=_CohortSubmission,
                instance_id="cohort_studies:herald_suburban",
                instance_index=0,
            )
        )
    assert calls[1]["extra_headers"]["X-Workload"] == "cohort"
    assert calls[1]["extra_headers"]["X-Session-Id"] == (
        "clbench-cohort-glm-stateful-r1-cohort_studies"
    )
    message = calls[1]["messages"][-1]["content"]
    assert message.startswith("=== Columns ===")
    assert message.endswith("all 36 cohorts.")


def test_auto_provider_mode_is_rejected():
    with pytest.raises(ValueError, match="litellm_chat"):
        CausalReflectionICL(provider_mode="auto")


def test_context_budget_is_explicit():
    os.environ["CRA_API_KEY"] = "test-key"
    system = CausalReflectionICL()
    assert system.max_tokens == 913_408
    assert system.model == "openai/glm-5.3-flash:causal-reflection"
    assert system.name == "ICL + GLM 5.3 Flash"
