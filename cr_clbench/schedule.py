"""In-process ``quick_test`` schedules.

Upstream Codebase Adaptation ships a ``default`` schedule only, and its
``quick_test`` name belongs to poker. Database Exploration's ``default``
schedule is forty questions. These schedules are one instance each, registered
in-process so the stock loader accepts ``--schedule quick_test``.
"""

from __future__ import annotations

from src.tasks.schedules import (
    TaskScheduleRunDefaults,
    TaskScheduleSpec,
    TaskScheduleStageSpec,
)

# First issue of the tablib block in schedules/default.json.
SMOKE_INSTANCE_ID = "jazzband__tablib-534"
# questions.json[0]. Schema drift is off for the smoke, so this question is
# the only instance and the order is not shuffled.
DATABASE_SMOKE_QUESTION_ID = "1"


def quick_test_schedule() -> TaskScheduleSpec:
    return TaskScheduleSpec(
        id="quick_test",
        display_name="Codebase Adaptation smoke",
        description=(
            "One tablib issue for a one-worker wiring smoke. "
            "The upstream codebase_adaptation package has no quick_test file."
        ),
        tags=["smoke"],
        run_defaults=TaskScheduleRunDefaults(
            runs=1,
            max_workers=1,
            mode="replicate",
        ),
        stages=[
            TaskScheduleStageSpec(
                variant="tablib",
                label="Tablib",
                notify_change=False,
                schedule={"instance_ids": [SMOKE_INSTANCE_ID]},
            )
        ],
    )


def database_quick_test_schedule() -> TaskScheduleSpec:
    return TaskScheduleSpec(
        id="quick_test",
        display_name="Database Exploration smoke",
        description=(
            "One question on the original products database. "
            "The upstream database_exploration package has no quick_test file."
        ),
        tags=["smoke"],
        run_defaults=TaskScheduleRunDefaults(
            runs=1,
            max_workers=1,
            mode="replicate",
        ),
        stages=[
            TaskScheduleStageSpec(
                variant="schema_drift",
                label="Smoke",
                notify_change=False,
                schedule={"num_questions": 1},
            )
        ],
    )


def sales_quick_test_schedule() -> TaskScheduleSpec:
    return TaskScheduleSpec(
        id="quick_test",
        display_name="Sales Prediction smoke",
        description=(
            "The first two years of the frozen sales lifecycle. "
            "The second year is what carries the first year's score back to the model. "
            "The upstream sales_prediction package has no quick_test file."
        ),
        tags=["smoke"],
        run_defaults=TaskScheduleRunDefaults(
            runs=1,
            max_workers=1,
            mode="replicate",
        ),
        stages=[
            TaskScheduleStageSpec(
                variant=None,
                label="First two forecast years",
                notify_change=False,
                schedule={"num_instances": 2},
            )
        ],
    )


def cohort_quick_test_schedule() -> TaskScheduleSpec:
    return TaskScheduleSpec(
        id="quick_test",
        display_name="Cohort Studies smoke",
        description=(
            "The first HERALD instance of the frozen default dataset. "
            "The task reads its schedule JSON directly, so the runner "
            "asks that loader for one instance of default."
        ),
        tags=["smoke"],
        run_defaults=TaskScheduleRunDefaults(
            runs=1,
            max_workers=1,
            mode="replicate",
        ),
        stages=[
            TaskScheduleStageSpec(
                variant="herald",
                label="HERALD smoke",
                notify_change=False,
                schedule={"num_instances": 1},
            )
        ],
    )


def apply_sales_smoke(task: object) -> None:
    """Keep the smoke on the first two frozen lifecycle years.

    The frozen corpus lists every year. Loading it would ignore the
    two-year stage, so the smoke shortens the list after that load.
    The second year is what sends the first year's score to the model.
    """
    if getattr(task, "schedule", None) != "quick_test":
        return
    task.num_instances = 2  # type: ignore[attr-defined]
    instances = getattr(task, "instances", None)
    if instances:
        task.instances = list(instances)[:2]  # type: ignore[attr-defined]


def cohort_smoke_arguments(kwargs: dict) -> tuple[dict, bool]:
    """One instance of the default frozen dataset.

    Cohort Studies opens ``schedules/<id>.json`` itself. ``quick_test`` is
    not a file there. The stock loader understands ``default`` and
    ``num_instances``.
    """
    schedule = kwargs.get("schedule")
    schedule_id = kwargs.get("schedule_id")
    if schedule != "quick_test" and schedule_id != "quick_test":
        return kwargs, False
    updated = dict(kwargs)
    if schedule == "quick_test":
        updated["schedule"] = "default"
    if schedule_id == "quick_test":
        updated["schedule_id"] = "default"
    updated["num_instances"] = 1
    return updated, True


def apply_database_smoke(task: object) -> None:
    """Keep the smoke on the first question of the original database.

    The schema_drift variant fixes the run at 20 questions, then 20 more, and
    ignores the stage's ``num_questions``. The smoke turns that drift off
    before questions are loaded, so the task reads ``questions.json`` and
    keeps the first row.
    """
    if getattr(task, "schedule", None) != "quick_test":
        return
    task._schema_drift_enabled = False  # type: ignore[attr-defined]
    task.num_questions = 1  # type: ignore[attr-defined]
    task.num_instances = 1  # type: ignore[attr-defined]
