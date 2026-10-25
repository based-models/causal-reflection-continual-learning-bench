"""Put the raw command output in the user message that follows the command.

The coding encoder pairs an assistant ``command`` with the user message
directly after it. A second user message in between hides the runner result.
Pytest, vitest, and Go summaries sit at the end of that output, and the
encoder reads the first 2,000 characters of a plain-text user message. When
the summary would fall past that window, copy the summary line to the front
and keep the full output after it.
"""

from __future__ import annotations

import re

from .constants import OBSERVATION_HEAD_CHARS

_PYTEST_SUMMARY = re.compile(
    r"^(?:=+\s*)?"
    r"(?:\d+\s+(?:failed|passed|skipped|warnings?|errors?|xfailed|xpassed|deselected)"
    r"(?:,\s*)?)+\s+in\s+\d+(?:\.\d+)?s"
    r"(?:\s*=+)?\s*$",
    re.IGNORECASE,
)
_VITEST_TESTS = re.compile(
    r"^Tests\s+\d+\s+(?:failed|passed|skipped|todo)\b",
    re.IGNORECASE,
)
_GO_OK = re.compile(r"^ok\s+\S+\s+(?:\(cached\)|\d+(?:\.\d+)?s\b)")
_GO_FAIL = re.compile(r"^FAIL\s+\S+")


def runner_footer(text: str) -> str:
    """Last pytest, vitest, or Go summary line, or an empty string."""
    found = ""
    for line in (text or "").splitlines():
        stripped = line.strip()
        if (
            _PYTEST_SUMMARY.match(stripped)
            or _VITEST_TESTS.match(stripped)
            or _GO_OK.match(stripped)
            or _GO_FAIL.match(stripped)
        ):
            found = stripped
    return found


def promote_runner_footer(text: str) -> str:
    """Keep the full output, and repeat a late summary inside the encoder head."""
    raw = text or ""
    footer = runner_footer(raw)
    if not footer:
        return raw
    head = raw[:OBSERVATION_HEAD_CHARS]
    if footer in head:
        return raw
    return f"{footer}\n\n{raw}"


def merge_user_turn(
    observation: str, prompt: str, *, promote_footer: bool = True
) -> str:
    """One user turn: raw runner output, then the task's next prompt."""
    body = promote_runner_footer(observation) if promote_footer else (observation or "")
    body = body.strip()
    follow = (prompt or "").strip()
    if body and follow:
        return f"{body}\n\n{follow}"
    return body or follow
