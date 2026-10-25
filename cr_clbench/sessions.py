"""Session ids for one domain.

A session starts empty and still receives the causal prefix and readout tail.
The difference between the two phases is whether that graph is kept:

- stateful: one session for every instance of a rollout
- stateless: one session per instance, cleared when the harness resets

Codebase Adaptation and Database Exploration do not share ids. Each domain
has its own slug and workload.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .constants import DATABASE_TASK, QUERY_WORKLOAD, TASK_NAME, WORKLOAD

_UNSAFE = re.compile(r"[\s,]+")


@dataclass(frozen=True)
class RunScope:
    """What the harness is doing while the system answers one rollout."""

    phase: str
    reset_between_instances: bool
    run_index: int | None
    task_name: str = TASK_NAME


def session_kind(scope: RunScope | None) -> str:
    """Baseline resets between instances. A rollout keeps one system."""
    if scope is None:
        return "stateful"
    if scope.phase == "baseline" or scope.reset_between_instances:
        return "stateless"
    return "stateful"


def run_label(kind: str, run_index: int | None) -> str:
    """Stateless baseline is r0. Rollout repeat 0 is r1, then r2, and so on."""
    if kind == "stateless":
        return "0"
    if run_index is None:
        return "1"
    return str(int(run_index) + 1)


def sanitize_id(value: str) -> str:
    """Keep header values free of spaces and commas.

    A comma in ``X-Session-Id`` is how the API joins two session headers into
    one stored id.
    """
    cleaned = _UNSAFE.sub("-", (value or "").strip())
    cleaned = cleaned.strip("-")
    if not cleaned:
        raise ValueError("session id component is empty")
    return cleaned


def run_tag() -> str:
    """Optional suffix so a repeated smoke starts a new graph.

    Unset, the ids match the campaign scheme exactly. Set ``CLBENCH_RUN_TAG``
    when a previous r0 or r1 session should not be resumed.
    """
    raw = (os.environ.get("CLBENCH_RUN_TAG") or "").strip()
    if not raw:
        return ""
    return sanitize_id(raw)


def workload_for(task_id: str) -> str:
    """Coding pack for shell tasks. Query pack for Database Exploration."""
    if task_id == DATABASE_TASK:
        return QUERY_WORKLOAD
    return WORKLOAD


def id_slug(task_id: str) -> str:
    """Short id piece. The two domains must not resume each other's graphs."""
    if task_id == DATABASE_TASK:
        return "database"
    return "codebase"


def build_ids(
    *,
    kind: str,
    run_index: int | None,
    task_id: str,
    instance_id: str | None,
) -> tuple[str, str]:
    """Return ``(run_id, session_id)`` for one completion."""
    label = run_label(kind, run_index)
    tag = run_tag()
    suffix = f"-{tag}" if tag else ""
    task = sanitize_id(task_id)
    slug = id_slug(task_id)
    run_id = f"clbench-{slug}-glm-r{label}{suffix}"
    if kind == "stateful":
        session_id = f"clbench-{slug}-glm-stateful-r{label}{suffix}-{task}"
        return run_id, session_id
    if not instance_id:
        raise ValueError("stateless session requires an instance id")
    instance = sanitize_id(instance_id)
    session_id = f"clbench-{slug}-glm-stateless-r{label}{suffix}-{task}-{instance}"
    return run_id, session_id


def causal_headers(
    *,
    kind: str,
    run_index: int | None,
    task_id: str,
    instance_id: str | None,
) -> dict[str, str]:
    """Headers sent on every completion. ``X-Session-Id`` is always present."""
    run_id, session_id = build_ids(
        kind=kind,
        run_index=run_index,
        task_id=task_id,
        instance_id=instance_id,
    )
    return {
        "X-Session-Id": session_id,
        "X-Run-Id": run_id,
        "X-Workload": workload_for(task_id),
    }
