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
