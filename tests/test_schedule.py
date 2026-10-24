"""quick_test is visible to the stock codebase task loader."""

import json
import sys
import types
from pathlib import Path

import pytest

from cr_clbench.integrate import install_runtime, task_data_dir
from cr_clbench.schedule import SMOKE_INSTANCE_ID


def _assert_smoke(spec) -> None:
    assert spec.id == "quick_test"
    assert spec.run_defaults is not None
    assert spec.run_defaults.runs == 1
    assert spec.run_defaults.max_workers == 1
    assert spec.stages[0].schedule["instance_ids"] == [SMOKE_INSTANCE_ID]
    assert SMOKE_INSTANCE_ID == "jazzband__tablib-534"


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
