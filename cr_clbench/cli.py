"""Entry point. Registers the ICL wrapper, then dispatches to ``clbench``."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .constants import (
    API_BASE,
    COHORT_TASK,
    CONTEXT_BUDGET_TOKENS,
    DATABASE_TASK,
    LEADERBOARD_NAME,
    LITELLM_MODEL,
    PUBLIC_MODEL_ID,
    SALES_TASK,
    SUPPORTED_TASKS,
    TASK_NAME,
)
from .schedule import DATABASE_SMOKE_QUESTION_ID, SMOKE_INSTANCE_ID
from .sessions import build_ids, workload_for

_OTHER_TASKS = {
    "exploitable_poker",
    "poker",
    "blind_spectrum_monitoring",
}
_CODEBASE_DATASET = Path("data/codebase_adaptation/final-dataset.jsonl")
_DATABASE_READY = (
    Path("data/database_exploration/products.db"),
    Path("data/database_exploration/products_drifted.db"),
    Path("data/database_exploration/questions.json"),
    Path("data/database_exploration/questions_post_drift.json"),
)
_DATABASE_SMOKE_READY = (
    Path("data/database_exploration/products.db"),
    Path("data/database_exploration/questions.json"),
)
_SALES_CORPUS = (
    Path("data/sales_prediction/sales_lifecycle_panel.jsonl"),
    Path("data/sales_prediction/sales_lifecycle_metadata.json"),
    Path("data/sales_prediction/furniture.json"),
    Path("data/sales_prediction/locations.json"),
)
_COHORT_READY = (
    Path("data/cohort_studies/default/metadata.json"),
    Path("data/cohort_studies/default/ground_truth.json"),
    Path("data/cohort_studies/default/dbs/herald_suburban.db"),
)
_NEEDS_DATASET = {"run", "smoke"}


def main(argv: list[str] | None = None) -> None:
    from dotenv import load_dotenv

    original = Path.cwd()
    load_dotenv(original / ".env")
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        _print_help()
        return
    if args[0] == "ids":
        _print_ids()
        return
    if args[0] == "run-all":
        raise SystemExit(
            "run-all scores every domain in one invocation. "
            "Run each domain separately, "
            "then keep each viewer artifact for the submission."
        )
    _reject_other_domains(args)
    if args[0] in {"run", "smoke"}:
        args = _ensure_system(args)
    args = _absolutize_config(args, original)
    root = (os.environ.get("CLBENCH_ROOT") or "").strip()
    if root:
        os.chdir(root)
    if args[0] in _NEEDS_DATASET:
        _require_task_data(args)
    from src.registry import SYSTEMS_REGISTRY

    from .integrate import install_runtime
    from .system import CausalReflectionICL

    install_runtime()
    SYSTEMS_REGISTRY["icl"] = CausalReflectionICL
    from src.cli import main as clbench_main

    sys.argv = [sys.argv[0], *args]
    clbench_main()


def _print_help() -> None:
    print(
        f"""cr-clbench — Continual Learning Bench through the causal-reflection API

Leaderboard name: {LEADERBOARD_NAME}
Model: {PUBLIC_MODEL_ID}
LiteLLM model: {LITELLM_MODEL}
API: {API_BASE}
Context budget: {CONTEXT_BUDGET_TOKENS} tokens

Commands:
  cr-clbench run --config configs/codebase_glm_smoke.json
  cr-clbench run --config configs/codebase_glm.json --runs 5
  cr-clbench run --config configs/database_glm_smoke.json
  cr-clbench run --config configs/database_glm.json --runs 1
  cr-clbench run --config configs/database_glm.json --runs 5
  cr-clbench run --config configs/sales_glm_smoke.json
  cr-clbench run --config configs/sales_glm.json --runs 1
  cr-clbench run --config configs/sales_glm.json --runs 5
  cr-clbench run --config configs/cohort_glm_smoke.json
  cr-clbench run --config configs/cohort_glm.json --runs 1
  cr-clbench run --config configs/cohort_glm.json --runs 5
  cr-clbench ids

Set CRA_API_KEY. Set CLBENCH_ROOT to a checkout of continual-learning-bench.
Codebase smoke is quick_test on {SMOKE_INSTANCE_ID}. Database smoke is
quick_test on question {DATABASE_SMOKE_QUESTION_ID}. Sales smoke is the first
two frozen lifecycle years. Cohort smoke is the first study of the default dataset.
All of them use one worker.
Database Exploration needs `clbench setup database_exploration`.
Sales Prediction needs `clbench setup sales_prediction` to pull its Docker image.
"""
    )


def _print_ids() -> None:
    for task_id, instance_id in (
        (TASK_NAME, SMOKE_INSTANCE_ID),
        (DATABASE_TASK, DATABASE_SMOKE_QUESTION_ID),
        (SALES_TASK, "sales_prediction:default:years:2027-2031"),
        (COHORT_TASK, "cohort_studies:herald_suburban"),
    ):
        stateful_run, stateful_session = build_ids(
            kind="stateful",
            run_index=0,
            task_id=task_id,
            instance_id=None,
        )
        stateless_run, stateless_session = build_ids(
            kind="stateless",
            run_index=None,
            task_id=task_id,
            instance_id=instance_id,
        )
        print(task_id)
        print(f"  stateful X-Run-Id:      {stateful_run}")
        print(f"  stateful X-Session-Id:  {stateful_session}")
        print(f"  stateless X-Run-Id:     {stateless_run}")
        print(f"  stateless X-Session-Id: {stateless_session}")
        print(f"  X-Workload: {workload_for(task_id)}")


def _reject_other_domains(args: list[str]) -> None:
    for token in args:
        if token in _OTHER_TASKS:
            raise SystemExit(
                f"{token} is outside this run. "
                f"Supported tasks: {', '.join(SUPPORTED_TASKS)}."
            )
    config = _config_path(args)
    if config is None or not config.is_file():
        return
    try:
        payload = json.loads(config.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read config {config}: {exc}") from exc
    task = (payload.get("task") or {}).get("name")
    if task and task not in SUPPORTED_TASKS:
        raise SystemExit(
            f"Config {config} selects task {task}. "
            f"Supported tasks: {', '.join(SUPPORTED_TASKS)}."
        )


def _ensure_system(args: list[str]) -> list[str]:
    if "--system" not in args and "-s" not in args:
        return [args[0], "--system", "icl", *args[1:]]
    for flag in ("--system", "-s"):
        if flag not in args:
            continue
        index = args.index(flag)
        if index + 1 >= len(args):
            raise SystemExit(f"{flag} needs a value")
        name = args[index + 1]
        if name != "icl":
            raise SystemExit(
                f"This repo runs the ICL wrapper as --system icl. Got {name}."
            )
    return args


def _selected_task(args: list[str]) -> tuple[str, str]:
    """Return ``(task name, schedule id)`` from the config, else codebase."""
    config = _config_path(args)
    if config is None or not config.is_file():
        for token in args:
            if token in SUPPORTED_TASKS:
                return token, ""
        return TASK_NAME, ""
    try:
        payload = json.loads(config.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read config {config}: {exc}") from exc
    task = (payload.get("task") or {}).get("name") or TASK_NAME
    schedule = str((payload.get("task") or {}).get("params", {}).get("schedule") or "")
    return str(task), schedule


def _require_task_data(args: list[str]) -> None:
    task, schedule = _selected_task(args)
    if task == DATABASE_TASK:
        required = _DATABASE_SMOKE_READY if schedule == "quick_test" else _DATABASE_READY
        missing = [path for path in required if not path.is_file()]
        if missing:
            names = ", ".join(str(path) for path in missing)
            raise SystemExit(
                f"Database Exploration is missing {names}. "
                "From the continual-learning-bench checkout run "
                "`clbench setup database_exploration`."
            )
        return
    if task == SALES_TASK:
        _require_files(
            _SALES_CORPUS,
            "Sales Prediction is missing {names}. "
            "The frozen lifecycle corpus lives in the continual-learning-bench "
            "checkout at data/sales_prediction/.",
        )
        return
    if task == COHORT_TASK:
        _require_files(
            _COHORT_READY,
            "Cohort Studies is missing {names}. "
            "The frozen default dataset lives in the continual-learning-bench "
            "checkout at data/cohort_studies/default/.",
        )
        return
    if not _CODEBASE_DATASET.is_file():
        raise SystemExit(
            "Dataset data/codebase_adaptation/final-dataset.jsonl was not found "
            "in the working directory. Clone continual-learning-bench at the "
            "pinned SHA and set CLBENCH_ROOT to that checkout."
        )


def _require_files(required: tuple[Path, ...], message: str) -> None:
    missing = [path for path in required if not path.is_file()]
    if not missing:
        return
    names = ", ".join(str(path) for path in missing)
    raise SystemExit(message.format(names=names))


def _config_path(args: list[str]) -> Path | None:
    if "--config" not in args:
        return None
    index = args.index("--config")
    if index + 1 >= len(args):
        raise SystemExit("--config needs a path")
    return Path(args[index + 1])


def _absolutize_config(args: list[str], root: Path) -> list[str]:
    if "--config" not in args:
        return args
    index = args.index("--config")
    path = Path(args[index + 1])
    if not path.is_absolute():
        path = root / path
    updated = list(args)
    updated[index + 1] = str(path)
    return updated
