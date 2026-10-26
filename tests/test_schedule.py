"""quick_test is visible to the stock codebase task loader."""

import inspect
import json
import sys
import types
from pathlib import Path

import pytest

from cr_clbench.integrate import (
    _prefer_checkout_templates,
    install_runtime,
    scope_task_name,
    task_data_dir,
)
from cr_clbench.schedule import (
    DATABASE_SMOKE_QUESTION_ID,
    SMOKE_INSTANCE_ID,
    apply_database_smoke,
    apply_sales_smoke,
    cohort_smoke_arguments,
)


def _assert_smoke(spec) -> None:
    assert spec.id == "quick_test"
    assert spec.run_defaults is not None
    assert spec.run_defaults.runs == 1
    assert spec.run_defaults.max_workers == 1
    assert spec.stages[0].schedule["instance_ids"] == [SMOKE_INSTANCE_ID]
    assert SMOKE_INSTANCE_ID == "jazzband__tablib-534"


def test_database_quick_test_is_one_question_and_turns_drift_off():
    install_runtime()
    import src.tasks.schedules as schedules_mod

    spec = schedules_mod.get_task_schedule("database_exploration", "quick_test")
    assert spec.id == "quick_test"
    assert spec.run_defaults is not None
    assert spec.run_defaults.runs == 1
    assert spec.run_defaults.max_workers == 1
    assert spec.stages[0].variant == "schema_drift"
    assert DATABASE_SMOKE_QUESTION_ID == "1"

    class _Task:
        schedule = "quick_test"
        _schema_drift_enabled = True
        num_questions = 40
        num_instances = 40

    task = _Task()
    apply_database_smoke(task)
    assert task._schema_drift_enabled is False
    assert task.num_questions == 1
    assert task.num_instances == 1


def test_database_smoke_keeps_the_schedule_parameter():
    """The bench reads task params from the init signature. A wrapper must keep it."""
    install_runtime()
    from src.tasks.database_exploration.task import DatabaseExploration

    assert "schedule" in inspect.signature(DatabaseExploration.__init__).parameters


def test_database_smoke_reports_one_instance_from_init(monkeypatch, tmp_path: Path):
    """The benchmark counts baseline workers from num_instances during init."""
    variant_dir = (
        tmp_path / "checkout" / "src" / "tasks" / "database_exploration" / "variants"
    )
    variant_dir.mkdir(parents=True)
    (variant_dir / "schema_drift.json").write_text(
        json.dumps(
            {
                "id": "schema_drift",
                "display_name": "Schema Drift",
                "description": "Forty questions unless the smoke overrides it.",
                "defaults": {
                    "db_path": "data/database_exploration/products.db",
                    "questions_path": "data/database_exploration/questions.json",
                    "num_questions": 40,
                    "max_queries_per_question": 15,
                    "seed": 42,
                },
                "config": {
                    "schema_drift": True,
                    "pre_drift_count": 20,
                    "post_drift_count": 20,
                },
            }
        )
    )
    monkeypatch.setenv("CLBENCH_ROOT", str(tmp_path / "checkout"))
    install_runtime()
    import src.tasks.variants as variants_mod

    variants_mod.list_task_variants.cache_clear()
    from src.tasks.database_exploration.task import DatabaseExploration

    task = DatabaseExploration(schedule="quick_test")
    assert task.schedule == "quick_test"
    assert task.num_instances == 1
    assert task.num_questions == 1
    assert task._schema_drift_enabled is False


def test_scope_task_name_prefers_the_task_object_over_a_missing_log():
    class _Database:
        pass

    import src.registry as registry

    previous = registry.TASKS_REGISTRY.get("database_exploration")
    registry.TASKS_REGISTRY["database_exploration"] = _Database
    try:
        assert scope_task_name(_Database(), None) == "database_exploration"
    finally:
        if previous is None:
            registry.TASKS_REGISTRY.pop("database_exploration", None)
        else:
            registry.TASKS_REGISTRY["database_exploration"] = previous


def test_sales_quick_test_is_one_instance_of_the_lifecycle_corpus():
    install_runtime()
    import src.tasks.schedules as schedules_mod

    spec = schedules_mod.get_task_schedule("sales_prediction", "quick_test")
    assert spec.stages[0].schedule["num_instances"] == 2
    assert spec.run_defaults is not None
    assert spec.run_defaults.max_workers == 1

    class _Task:
        def __init__(self) -> None:
            self.schedule = "quick_test"
            self.num_instances = 12
            self.instances = ["2027", "2028", "2029"]

    task = _Task()
    apply_sales_smoke(task)
    assert task.num_instances == 2
    assert task.instances == ["2027", "2028"]


def test_cohort_smoke_asks_the_default_loader_for_one_instance():
    updated, smoke = cohort_smoke_arguments({"schedule": "quick_test", "seed": 42})
    assert smoke is True
    assert updated == {"schedule": "default", "seed": 42, "num_instances": 1}
    unchanged, full = cohort_smoke_arguments({"schedule": "default"})
    assert full is False
    assert unchanged == {"schedule": "default"}


def test_quick_test_resolves_from_the_schedule_module():
    install_runtime()
    import src.tasks.schedules as schedules_mod

    _assert_smoke(schedules_mod.get_task_schedule("codebase_adaptation", "quick_test"))


def test_quick_test_rebinds_a_task_module_imported_earlier():
    """The task file binds get_task_schedule at import. Rebind that name too."""

    def unbound(family: str, schedule_id: str):
        raise KeyError(schedule_id)

    fake = types.ModuleType("src.tasks.codebase_adaptation.task")
    fake.get_task_schedule = unbound
    previous = sys.modules.get("src.tasks.codebase_adaptation.task")
    sys.modules["src.tasks.codebase_adaptation.task"] = fake
    try:
        install_runtime()
        _assert_smoke(fake.get_task_schedule("codebase_adaptation", "quick_test"))
    finally:
        if previous is None:
            sys.modules.pop("src.tasks.codebase_adaptation.task", None)
        else:
            sys.modules["src.tasks.codebase_adaptation.task"] = previous


def test_missing_task_templates_are_loaded_from_the_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from jinja2 import Environment, FileSystemLoader

    packaged = tmp_path / "installed" / "templates"
    packaged.mkdir(parents=True)
    checkout = tmp_path / "checkout" / "src" / "tasks" / "sales_prediction" / "templates"
    checkout.mkdir(parents=True)
    (checkout / "instance.j2").write_text("year {{ target_year }}")
    monkeypatch.setenv("CLBENCH_ROOT", str(tmp_path / "checkout"))
    module = types.SimpleNamespace(
        _jinja_env=Environment(loader=FileSystemLoader(str(packaged)))
    )
    _prefer_checkout_templates(module, "sales_prediction", "instance.j2")
    assert module._jinja_env.get_template("instance.j2").render(target_year=2027) == "year 2027"


def test_packaged_json_wins_over_the_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    packaged = tmp_path / "packaged"
    packaged.mkdir()
    (packaged / "default.json").write_text("{}")
    monkeypatch.setenv("CLBENCH_ROOT", str(tmp_path / "checkout"))
    assert task_data_dir(packaged, "codebase_adaptation", "schedules") == packaged


def test_checkout_json_is_used_when_the_package_omits_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    packaged = tmp_path / "packaged"
    packaged.mkdir()
    checkout = tmp_path / "checkout" / "src" / "tasks" / "codebase_adaptation" / "variants"
    checkout.mkdir(parents=True)
    (checkout / "tablib.json").write_text("{}")
    monkeypatch.setenv("CLBENCH_ROOT", str(tmp_path / "checkout"))
    assert task_data_dir(packaged, "codebase_adaptation", "variants") == checkout


def test_working_directory_supplies_json_without_clbench_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    packaged = tmp_path / "packaged"
    packaged.mkdir()
    checkout = tmp_path / "checkout"
    variant_dir = checkout / "src" / "tasks" / "codebase_adaptation" / "schedules"
    variant_dir.mkdir(parents=True)
    (variant_dir / "default.json").write_text("{}")
    monkeypatch.delenv("CLBENCH_ROOT", raising=False)
    monkeypatch.chdir(checkout)
    assert task_data_dir(packaged, "codebase_adaptation", "schedules") == variant_dir


def test_variant_and_default_schedule_load_from_the_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import src.tasks.schedules as schedules_mod
    import src.tasks.variants as variants_mod

    packaged = (
        Path(variants_mod.__file__).resolve().parent
        / "codebase_adaptation"
        / "variants"
    )
    if packaged.is_dir() and any(packaged.glob("*.json")):
        pytest.skip("installed package already contains variant JSON")

    variants = tmp_path / "src" / "tasks" / "codebase_adaptation" / "variants"
    variants.mkdir(parents=True)
    (variants / "tablib.json").write_text(
        json.dumps(
            {
                "id": "tablib",
                "display_name": "Checkout tablib",
                "description": "loaded-from-checkout",
                "defaults": {},
                "config": {"repo": "jazzband/tablib"},
            }
        )
    )
    schedules = tmp_path / "src" / "tasks" / "codebase_adaptation" / "schedules"
    schedules.mkdir(parents=True)
    (schedules / "default.json").write_text(
        json.dumps(
            {
                "id": "default",
                "display_name": "Checkout default",
                "description": "loaded-from-checkout",
                "stages": [],
            }
        )
    )
    monkeypatch.setenv("CLBENCH_ROOT", str(tmp_path))
    install_runtime()
    try:
        variant = variants_mod.get_task_variant("codebase_adaptation", "tablib")
        schedule = schedules_mod.get_task_schedule("codebase_adaptation", "default")
    finally:
        variants_mod.list_task_variants.cache_clear()
        schedules_mod.list_task_schedules.cache_clear()
    assert variant.description == "loaded-from-checkout"
    assert schedule.description == "loaded-from-checkout"
