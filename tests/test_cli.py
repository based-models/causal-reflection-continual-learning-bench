"""CLI guards for this codebase-only run."""

import json
from pathlib import Path

import pytest

from cr_clbench.cli import (
    _absolutize_config,
    _ensure_system,
    _reject_other_domains,
)


def test_run_defaults_to_the_icl_wrapper():
    assert _ensure_system(["run", "--config", "configs/codebase_glm_smoke.json"])[:3] == [
        "run",
        "--system",
        "icl",
    ]


def test_other_systems_are_rejected():
    with pytest.raises(SystemExit, match="icl"):
        _ensure_system(["run", "--system", "ace"])


def test_other_domains_are_rejected():
    with pytest.raises(SystemExit, match="codebase_adaptation"):
        _reject_other_domains(["run", "blind_spectrum_monitoring", "--system", "icl"])


def test_database_exploration_config_is_accepted(tmp_path: Path):
    path = tmp_path / "database.json"
    path.write_text(
        json.dumps({"task": {"name": "database_exploration", "params": {"schedule": "default"}}})
    )
    _reject_other_domains(["run", "--config", str(path)])


def test_sales_cohort_and_poker_configs_are_accepted(tmp_path: Path):
    for name in ("sales_prediction", "cohort_studies", "exploitable_poker"):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps({"task": {"name": name, "params": {"schedule": "default"}}}))
        _reject_other_domains(["run", "--config", str(path)])


def test_config_for_another_task_is_rejected(tmp_path: Path):
    path = tmp_path / "other.json"
    path.write_text(json.dumps({"task": {"name": "blind_spectrum_monitoring"}}))
    with pytest.raises(SystemExit, match="Supported tasks"):
        _reject_other_domains(["run", "--config", str(path)])


def test_config_path_is_absolute_before_chdir(tmp_path: Path):
    args = _absolutize_config(["run", "--config", "configs/codebase_glm_smoke.json"], tmp_path)
    assert Path(args[2]).is_absolute()
    assert args[2] == str(tmp_path / "configs/codebase_glm_smoke.json")
