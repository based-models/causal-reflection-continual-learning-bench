"""Session id scheme."""

import os

import pytest

from cr_clbench.sessions import (
    RunScope,
    build_ids,
    causal_headers,
    run_label,
    session_kind,
    workload_for,
)


def test_stateful_rollout_is_one_session_per_run():
    first_run, first_session = build_ids(
        kind="stateful",
        run_index=0,
        task_id="codebase_adaptation",
        instance_id="jazzband__tablib-534",
    )
    _, second_session = build_ids(
        kind="stateful",
        run_index=0,
        task_id="codebase_adaptation",
        instance_id="jazzband__tablib-540",
    )
    next_run, next_session = build_ids(
        kind="stateful",
        run_index=1,
        task_id="codebase_adaptation",
        instance_id="jazzband__tablib-534",
    )
    assert first_run == "clbench-codebase-glm-r1"
    assert first_session == "clbench-codebase-glm-stateful-r1-codebase_adaptation"
    assert second_session == first_session
    assert next_run == "clbench-codebase-glm-r2"
    assert next_session == "clbench-codebase-glm-stateful-r2-codebase_adaptation"


def test_stateless_session_includes_the_instance_and_stays_on_r0():
    run_id, session_id = build_ids(
        kind="stateless",
        run_index=4,
        task_id="codebase_adaptation",
        instance_id="jazzband__tablib-534",
    )
    _, other = build_ids(
        kind="stateless",
        run_index=4,
        task_id="codebase_adaptation",
        instance_id="jd__tenacity-597",
    )
    assert run_id == "clbench-codebase-glm-r0"
    assert session_id == (
        "clbench-codebase-glm-stateless-r0-codebase_adaptation-jazzband__tablib-534"
    )
    assert other != session_id
    assert other.endswith("jd__tenacity-597")


def test_database_sessions_use_the_query_workload_and_do_not_reuse_codebase_ids():
    run_id, session_id = build_ids(
        kind="stateful",
        run_index=0,
        task_id="database_exploration",
        instance_id=None,
    )
    _, stateless = build_ids(
        kind="stateless",
        run_index=None,
        task_id="database_exploration",
        instance_id="1",
    )
    assert run_id == "clbench-database-glm-r1"
    assert session_id == "clbench-database-glm-stateful-r1-database_exploration"
    assert stateless == "clbench-database-glm-stateless-r0-database_exploration-1"
    assert "codebase" not in session_id
    assert workload_for("database_exploration") == "query"
    headers = causal_headers(
        kind="stateful",
        run_index=0,
        task_id="database_exploration",
        instance_id=None,
    )
    assert headers["X-Workload"] == "query"


def test_headers_always_carry_session_run_and_workload():
    headers = causal_headers(
        kind="stateful",
        run_index=0,
        task_id="codebase_adaptation",
        instance_id=None,
    )
    assert headers == {
        "X-Session-Id": "clbench-codebase-glm-stateful-r1-codebase_adaptation",
        "X-Run-Id": "clbench-codebase-glm-r1",
        "X-Workload": "coding",
    }


def test_baseline_phase_is_stateless_even_without_a_reset_flag():
    scope = RunScope(phase="baseline", reset_between_instances=False, run_index=None)
    assert session_kind(scope) == "stateless"
    assert run_label("stateless", None) == "0"


def test_rollout_phase_is_stateful():
    scope = RunScope(phase="run", reset_between_instances=False, run_index=0)
    assert session_kind(scope) == "stateful"


def test_run_tag_appends_without_changing_the_default(monkeypatch):
    monkeypatch.delenv("CLBENCH_RUN_TAG", raising=False)
    _, plain = build_ids(
        kind="stateful",
        run_index=0,
        task_id="codebase_adaptation",
        instance_id=None,
    )
    monkeypatch.setenv("CLBENCH_RUN_TAG", "smoke2")
    _, tagged = build_ids(
        kind="stateful",
        run_index=0,
        task_id="codebase_adaptation",
        instance_id=None,
    )
    assert plain == "clbench-codebase-glm-stateful-r1-codebase_adaptation"
    assert tagged == "clbench-codebase-glm-stateful-r1-smoke2-codebase_adaptation"


def test_stateless_requires_an_instance_id():
    with pytest.raises(ValueError):
        build_ids(
            kind="stateless",
            run_index=None,
            task_id="codebase_adaptation",
            instance_id=None,
        )


def test_commas_cannot_land_in_a_session_id():
    _, session_id = build_ids(
        kind="stateless",
        run_index=None,
        task_id="codebase_adaptation",
        instance_id="a, b",
    )
    assert "," not in session_id
    assert " " not in session_id
    os.environ.pop("CLBENCH_RUN_TAG", None)
