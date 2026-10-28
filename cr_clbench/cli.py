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
    POKER_TASK,
    PUBLIC_MODEL_ID,
    SALES_TASK,
    SPECTRUM_TASK,
    SUPPORTED_TASKS,
    TASK_NAME,
)
from .schedule import DATABASE_SMOKE_QUESTION_ID, SMOKE_INSTANCE_ID
from .sessions import build_ids, workload_for

_OTHER_TASKS: set[str] = set()
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
_SPECTRUM_READY = (
    Path("src/tasks/blind_spectrum_monitoring/schedules/default.json"),
    Path("src/tasks/blind_spectrum_monitoring/variants/five_ch_wide.json"),
    Path("src/tasks/blind_spectrum_monitoring/variants/five_plus_four_mixed.json"),
    Path("src/tasks/blind_spectrum_monitoring/variants/full_grid_active.json"),
    Path("src/tasks/blind_spectrum_monitoring/templates/instance.j2"),
    Path("src/tasks/blind_spectrum_monitoring/templates/task.j2"),
    Path("src/tasks/blind_spectrum_monitoring/templates/feedback.j2"),
    Path("data/blind_spectrum_monitoring/mixed_grid_lifecycle.jsonl"),
    Path("data/blind_spectrum_monitoring/mixed_grid_lifecycle_metadata.json"),
)
_POKER_READY = (
    Path("src/tasks/exploitable_poker/schedules/quick_test.json"),
    Path("src/tasks/exploitable_poker/schedules/default.json"),
    Path("src/tasks/exploitable_poker/variants/calling_station.json"),
    Path("src/tasks/exploitable_poker/variants/fit_or_fold.json"),
    Path("src/tasks/exploitable_poker/variants/loose_aggressive.json"),
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
  cr-clbench run --config configs/poker_glm_smoke.json
  cr-clbench run --config configs/poker_glm.json --runs 1
  cr-clbench run --config configs/poker_glm.json --runs 5
  cr-clbench run --config configs/spectrum_glm_smoke.json
  cr-clbench run --config configs/spectrum_glm.json --runs 1
  cr-clbench run --config configs/spectrum_glm.json --runs 5
  cr-clbench ids

Set CRA_API_KEY. Set CLBENCH_ROOT to a checkout of continual-learning-bench.
Codebase smoke is quick_test on {SMOKE_INSTANCE_ID}. Database smoke is
quick_test on question {DATABASE_SMOKE_QUESTION_ID}. Sales smoke is the first
two frozen lifecycle years. Cohort smoke is the first study of the default dataset.
Poker smoke is five hands against Tom. Spectrum smoke is the first two
scans of the frozen mixed-grid corpus. All of them use one worker.
Database Exploration needs `clbench setup database_exploration`.
Sales Prediction needs `clbench setup sales_prediction` to pull its Docker image.
Exploitable Poker needs `texasholdem==0.11.0` in the bench venv. No Docker image.
Blind Spectrum Monitoring needs the frozen mixed_grid_lifecycle corpus in the
bench checkout. No Docker image.
"""
    )


def _print_ids() -> None:
    for task_id, instance_id in (
        (TASK_NAME, SMOKE_INSTANCE_ID),
        (DATABASE_TASK, DATABASE_SMOKE_QUESTION_ID),
        (SALES_TASK, "sales_prediction:default:years:2027-2031"),
        (COHORT_TASK, "cohort_studies:herald_suburban"),
        (POKER_TASK, "poker:calling_station:hand:stage0_seed42_hand1"),
        (
            SPECTRUM_TASK,
            "blind_spectrum_monitoring:five_ch_wide:corpus:mixed_grid_lifecycle:scan:1",
        ),
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
    if task == POKER_TASK:
        _require_files(
            _POKER_READY,
            "Exploitable Poker is missing {names}. "
            "The schedules and variants live in the continual-learning-bench "
            "checkout at src/tasks/exploitable_poker/.",
        )
        try:
            import texasholdem  # noqa: F401
        except ModuleNotFoundError as exc:
            raise SystemExit(
                "Exploitable Poker needs texasholdem==0.11.0 in the bench venv. "
                "From that venv run `uv pip install 'texasholdem==0.11.0'`."
            ) from exc
        return
    if task == SPECTRUM_TASK:
        _require_files(
            _SPECTRUM_READY,
            "Blind Spectrum Monitoring is missing {names}. "
            "The schedule, variants, templates, and frozen mixed_grid_lifecycle "
            "corpus live in the continual-learning-bench checkout.",
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
