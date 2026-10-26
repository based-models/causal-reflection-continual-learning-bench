"""Hooks that teach the stock harness about this run.

Workers spawn a fresh interpreter. Importing the system module installs the
hooks there, because the child unpickles the system class before it constructs
the task.
"""

from __future__ import annotations

import inspect
import os
import sys
from functools import wraps
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from .constants import SUPPORTED_TASKS
from .pricing import register_prices
from .schedule import (
    apply_database_smoke,
    apply_sales_smoke,
    cohort_quick_test_schedule,
    cohort_smoke_arguments,
    database_quick_test_schedule,
    quick_test_schedule,
    sales_quick_test_schedule,
)
from .sessions import RunScope

_SCOPE: ContextVar[RunScope | None] = ContextVar("cr_clbench_run_scope", default=None)


def current_scope() -> RunScope | None:
    return _SCOPE.get()


@contextmanager
def override_scope(scope: RunScope | None) -> Iterator[None]:
    token = _SCOPE.set(scope)
    try:
        yield
    finally:
        _SCOPE.reset(token)


def install_runtime() -> None:
    """Register prices, the smoke schedules, and the run-scope hook."""
    register_prices()
    _install_checkout_data()
    _install_quick_test()
    _install_database_smoke()
    _install_sales_runtime()
    _install_cohort_runtime()
    _install_run_scope_hook()


def task_data_dir(packaged: Path, family: str, kind: str) -> Path:
    """Prefer packaged JSON, then the continual-learning-bench checkout.

    A non-editable install of ``cl-benchmark`` ships the task module and drops
    ``schedules/*.json`` and ``variants/*.json``. The checkout named by
    ``CLBENCH_ROOT``, or the working directory when that is the checkout,
    still has those files. An editable install already has them beside the
    module, and that directory wins.
    """
    if packaged.is_dir() and any(packaged.glob("*.json")):
        return packaged
    checkout = _checkout_data_dir(family, kind)
    if checkout is not None:
        return checkout
    return packaged


def _checkout_data_dir(family: str, kind: str) -> Path | None:
    roots: list[Path] = []
    env = (os.environ.get("CLBENCH_ROOT") or "").strip()
    if env:
        roots.append(Path(env))
    cwd = Path.cwd()
    if cwd not in roots:
        roots.append(cwd)
    for root in roots:
        candidate = root / "src" / "tasks" / family / kind
        if candidate.is_dir() and any(candidate.glob("*.json")):
            return candidate
    return None


def _install_checkout_data() -> None:
    import src.tasks.schedules as schedules_mod
    import src.tasks.variants as variants_mod

    if not getattr(schedules_mod._schedule_dir, "_cr_checkout", False):
        original = schedules_mod._schedule_dir

        def schedule_dir(family: str) -> Path:
            return task_data_dir(original(family), family, "schedules")

        schedule_dir._cr_checkout = True  # type: ignore[attr-defined]
        schedules_mod._schedule_dir = schedule_dir

    if not getattr(variants_mod._variant_dir, "_cr_checkout", False):
        original_variant = variants_mod._variant_dir

        def variant_dir(family: str) -> Path:
            return task_data_dir(original_variant(family), family, "variants")

        variant_dir._cr_checkout = True  # type: ignore[attr-defined]
        variants_mod._variant_dir = variant_dir

    schedules_mod.list_task_schedules.cache_clear()
    variants_mod.list_task_variants.cache_clear()


def _install_quick_test() -> None:
    import src.tasks.schedules as schedules_mod

    current = schedules_mod.get_task_schedule
    if getattr(current, "_cr_quick_test", False):
        wrapped = current
    else:
        original = current

        def wrapped(family: str, schedule_id: str) -> Any:
            if schedule_id == "quick_test" and family == "codebase_adaptation":
                return quick_test_schedule()
            if schedule_id == "quick_test" and family == "database_exploration":
                return database_quick_test_schedule()
            if schedule_id == "quick_test" and family == "sales_prediction":
                return sales_quick_test_schedule()
            if schedule_id == "quick_test" and family == "cohort_studies":
                return cohort_quick_test_schedule()
            return original(family, schedule_id)

        wrapped._cr_quick_test = True  # type: ignore[attr-defined]
        schedules_mod.get_task_schedule = wrapped

    for module_name in (
        "src.tasks.codebase_adaptation.task",
        "src.tasks.database_exploration.task",
        "src.tasks.sales_prediction.task",
        "src.tasks.cohort_studies.task",
        "src.cli",
    ):
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, "get_task_schedule"):
            module.get_task_schedule = wrapped


def _install_database_smoke() -> None:
    from src.tasks.database_exploration.task import DatabaseExploration

    original_init = DatabaseExploration.__init__
    if not getattr(original_init, "_cr_smoke_init", False):

        @wraps(original_init)
        def wrapped_init(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            apply_database_smoke(self)

        wrapped_init._cr_smoke_init = True  # type: ignore[attr-defined]
        DatabaseExploration.__init__ = wrapped_init  # type: ignore[method-assign]

    current = DatabaseExploration.build_canonical_run_state
    if getattr(current, "_cr_smoke", False):
        return

    def wrapped(self: Any) -> None:
        apply_database_smoke(self)
        return current(self)

    wrapped._cr_smoke = True  # type: ignore[attr-defined]
    DatabaseExploration.build_canonical_run_state = wrapped  # type: ignore[method-assign]


def _checkout_file(family: str, name: str) -> Path | None:
    """A data file in the continual-learning-bench checkout, if it is there."""
    roots: list[Path] = []
    env = (os.environ.get("CLBENCH_ROOT") or "").strip()
    if env:
        roots.append(Path(env))
    cwd = Path.cwd()
    if cwd not in roots:
        roots.append(cwd)
    for root in roots:
        candidate = root / "data" / family / name
        if candidate.is_file():
            return candidate
    return None


def _install_sales_runtime() -> None:
    """Point the frozen corpus at the checkout, and keep smoke to one year."""
    try:
        import src.tasks.sales_prediction.corpus as corpus
        import src.tasks.sales_prediction.task as sales_task
    except Exception:
        return

    packaged = corpus.DATA_DIR / "sales_lifecycle_panel.jsonl"
    checkout = _checkout_file("sales_prediction", "sales_lifecycle_panel.jsonl")
    if not packaged.is_file() and checkout is not None:
        corpus.DATA_DIR = checkout.parent

    current_id = sales_task._corpus_id_for_schedule
    if not getattr(current_id, "_cr_sales_corpus", False):

        def corpus_id(schedule: str | None) -> str | None:
            if schedule == "quick_test":
                return "sales_lifecycle"
            return current_id(schedule)

        corpus_id._cr_sales_corpus = True  # type: ignore[attr-defined]
        sales_task._corpus_id_for_schedule = corpus_id

    original_init = sales_task.SalesPredictionTask.__init__
    if not getattr(original_init, "_cr_sales_init", False):

        @wraps(original_init)
        def wrapped_init(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            apply_sales_smoke(self)

        wrapped_init._cr_sales_init = True  # type: ignore[attr-defined]
        sales_task.SalesPredictionTask.__init__ = wrapped_init  # type: ignore[method-assign]

    current = sales_task.SalesPredictionTask.build_canonical_run_state
    if getattr(current, "_cr_sales_build", False):
        return

    def wrapped_build(self: Any) -> None:
        current(self)
        apply_sales_smoke(self)

    wrapped_build._cr_sales_build = True  # type: ignore[attr-defined]
    sales_task.SalesPredictionTask.build_canonical_run_state = wrapped_build  # type: ignore[method-assign]


def _install_cohort_runtime() -> None:
    """Find the frozen studies, and make smoke the first default instance."""
    try:
        import src.tasks.cohort_studies.task as cohort_task
    except Exception:
        return

    _redirect_cohort_schedule_open(cohort_task)
    _redirect_cohort_dataset(cohort_task)

    original_init = cohort_task.CohortStudiesTask.__init__
    if getattr(original_init, "_cr_cohort_init", False):
        return

    @wraps(original_init)
    def wrapped_init(self: Any, *args: Any, **kwargs: Any) -> None:
        updated, smoke = cohort_smoke_arguments(kwargs)
        original_init(self, *args, **updated)
        if not smoke:
            return
        self.num_instances = 1
        if getattr(self, "instances", None):
            self.instances = list(self.instances)[:1]

    wrapped_init._cr_cohort_init = True  # type: ignore[attr-defined]
    cohort_task.CohortStudiesTask.__init__ = wrapped_init  # type: ignore[method-assign]


def _redirect_cohort_dataset(cohort_task: Any) -> None:
    current = cohort_task._default_dataset_dir
    if getattr(current, "_cr_cohort_data", False):
        return

    def dataset_dir(schedule_id: str = "default") -> Path:
        packaged = current(schedule_id)
        if (packaged / "metadata.json").is_file():
            return packaged
        checkout = _checkout_file("cohort_studies", f"{schedule_id}/metadata.json")
        if checkout is not None:
            return checkout.parent
        return packaged

    dataset_dir._cr_cohort_data = True  # type: ignore[attr-defined]
    cohort_task._default_dataset_dir = dataset_dir


def _redirect_cohort_schedule_open(cohort_task: Any) -> None:
    """The task opens ``schedules/<id>.json`` beside the installed module.

    A non-editable install drops that file. The checkout still has it.
    """
    current_open = getattr(cohort_task, "open", open)
    if getattr(current_open, "_cr_cohort_open", False):
        return
    original_open = current_open

    def open_schedule(file: Any, *args: Any, **kwargs: Any) -> Any:
        path = Path(file)
        if (
            path.name.endswith(".json")
            and path.parent.name == "schedules"
            and not path.is_file()
        ):
            checkout = _checkout_data_dir("cohort_studies", "schedules")
            if checkout is not None and (checkout / path.name).is_file():
                file = checkout / path.name
        return original_open(file, *args, **kwargs)

    open_schedule._cr_cohort_open = True  # type: ignore[attr-defined]
    cohort_task.open = open_schedule


def scope_task_name(task: Any, logged: Any) -> str:
    """Prefer the task object. Baseline workers do not bind a log task name."""
    try:
        from src.registry import TASKS_REGISTRY
    except Exception:
        TASKS_REGISTRY = {}
    if task is not None:
        for name, cls in TASKS_REGISTRY.items():
            if isinstance(task, cls):
                return name
    if isinstance(logged, str) and logged.strip():
        return logged.strip()
    return SUPPORTED_TASKS[0]


def _logged_value(key: str) -> Any:
    try:
        from src.logging_utils import _LOG_CONTEXT
    except Exception:
        return None
    return _LOG_CONTEXT.get().get(key)


def _install_run_scope_hook() -> None:
    from src.runtime import runner

    current = runner.run_task
    if getattr(current, "_cr_hook", False):
        return
    original: Callable[..., Any] = current

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        bound = inspect.signature(original).bind_partial(*args, **kwargs)
        phase = str(bound.arguments.get("phase", "rollout"))
        reset_between = bool(bound.arguments.get("reset_between_instances", False))
        run_index = _logged_value("run_index")
        if not isinstance(run_index, int):
            run_index = None
        task_name = scope_task_name(bound.arguments.get("task"), _logged_value("task"))
        token = _SCOPE.set(
            RunScope(
                phase=phase,
                reset_between_instances=reset_between,
                run_index=run_index,
                task_name=task_name,
            )
        )
        try:
            return original(*args, **kwargs)
        finally:
            _SCOPE.reset(token)

    wrapped._cr_hook = True  # type: ignore[attr-defined]
    runner.run_task = wrapped
