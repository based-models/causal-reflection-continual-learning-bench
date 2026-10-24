"""Entry point. Registers the ICL wrapper, then dispatches to ``clbench``."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .constants import (
    API_BASE,
    CONTEXT_BUDGET_TOKENS,
    LEADERBOARD_NAME,
    LITELLM_MODEL,
    PUBLIC_MODEL_ID,
    TASK_NAME,
)
from .schedule import SMOKE_INSTANCE_ID
from .sessions import build_ids

_OTHER_TASKS = {
    "exploitable_poker",
    "poker",
    "sales_prediction",
    "cohort_studies",
    "database_exploration",
    "blind_spectrum_monitoring",
}
_DATASET = Path("data/codebase_adaptation/final-dataset.jsonl")
_NEEDS_DATASET = {"run", "smoke", "setup", "run-all"}


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
            "run-all scores every domain. This run is codebase_adaptation only."
        )
    _reject_other_domains(args)
    if args[0] in {"run", "smoke"}:
        args = _ensure_system(args)
    args = _absolutize_config(args, original)
    root = (os.environ.get("CLBENCH_ROOT") or "").strip()
    if root:
        os.chdir(root)
    if args[0] in _NEEDS_DATASET and not _DATASET.is_file():
        raise SystemExit(
            "Dataset data/codebase_adaptation/final-dataset.jsonl was not found "
            "in the working directory. Clone continual-learning-bench at the "
            "pinned SHA and set CLBENCH_ROOT to that checkout."
        )
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
        f"""cr-clbench — Codebase Adaptation through the causal-reflection API

Leaderboard name: {LEADERBOARD_NAME}
Model: {PUBLIC_MODEL_ID}
LiteLLM model: {LITELLM_MODEL}
API: {API_BASE}
Context budget: {CONTEXT_BUDGET_TOKENS} tokens

Commands:
  cr-clbench run --config configs/codebase_glm_smoke.json
  cr-clbench run --config configs/codebase_glm.json --runs 1 --max-workers 1
  cr-clbench ids

Set CRA_API_KEY. Set CLBENCH_ROOT to a checkout of continual-learning-bench
when this repo is not already sitting on that dataset. The smoke schedule is
quick_test: one tablib issue ({SMOKE_INSTANCE_ID}), one worker.
"""
    )


def _print_ids() -> None:
    stateful_run, stateful_session = build_ids(
        kind="stateful",
        run_index=0,
        task_id=TASK_NAME,
        instance_id=None,
    )
    stateless_run, stateless_session = build_ids(
        kind="stateless",
        run_index=None,
        task_id=TASK_NAME,
        instance_id=SMOKE_INSTANCE_ID,
    )
    print(f"stateful X-Run-Id:     {stateful_run}")
    print(f"stateful X-Session-Id: {stateful_session}")
    print(f"stateless X-Run-Id:    {stateless_run}")
    print(f"stateless X-Session-Id: {stateless_session}")
    print("X-Workload: coding")


def _reject_other_domains(args: list[str]) -> None:
    for token in args:
        if token in _OTHER_TASKS:
            raise SystemExit(
                f"{token} is outside this run. The scored task is {TASK_NAME}."
            )
    config = _config_path(args)
    if config is None or not config.is_file():
        return
    try:
        payload = json.loads(config.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read config {config}: {exc}") from exc
    task = (payload.get("task") or {}).get("name")
    if task and task != TASK_NAME:
        raise SystemExit(
            f"Config {config} selects task {task}. This run scores {TASK_NAME} only."
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
