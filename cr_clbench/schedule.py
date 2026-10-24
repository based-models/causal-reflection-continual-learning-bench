"""In-process ``quick_test`` schedule for Codebase Adaptation.

The upstream task ships a ``default`` schedule only. ``quick_test`` on this
bench is the poker schedule. This run registers one tablib issue so
``--schedule quick_test`` resolves inside the stock task loader.
"""

from __future__ import annotations

from src.tasks.schedules import (
    TaskScheduleRunDefaults,
    TaskScheduleSpec,
    TaskScheduleStageSpec,
)

# First issue of the tablib block in schedules/default.json.
SMOKE_INSTANCE_ID = "jazzband__tablib-534"


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
