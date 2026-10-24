"""Stop conditions that must not be scored as an ordinary failed issue."""

from __future__ import annotations


class CausalReflectionStop(Exception):
    """A failure the harness should surface instead of zero-crediting the issue."""


class ResponseFormatStop(CausalReflectionStop):
    """ICL omitted ``response_format``, or the API rejected it.

    Leave the causal prefix on. This run does not switch to a prompt-only
    workaround.
    """


class CommandParseStop(CausalReflectionStop):
    """The completion did not parse as ``{"thought": "...", "command": "..."}``."""


class SpendCapStop(CausalReflectionStop):
    """The API key hit ``MONTHLY_SPEND_CAP_USD``. That is an API limit."""


def _chain_text(exc: BaseException) -> str:
    parts: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        parts.append(type(current).__name__)
        parts.append(str(current))
        current = current.__cause__ or current.__context__
    return "\n".join(parts)


def _chain_types(exc: BaseException) -> set[str]:
    names: set[str] = set()
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        names.add(type(current).__name__)
        current = current.__cause__ or current.__context__
    return names


def classify_stop(exc: BaseException) -> CausalReflectionStop | None:
    """Return a terminal error, or None when the bench should handle it."""
    text = _chain_text(exc).lower()
    if "monthly spend cap" in text:
        return SpendCapStop(
            "The API rejected the call because this key reached its monthly "
            "spend cap (MONTHLY_SPEND_CAP_USD). That is an API limit. "
            "Raise the cap on the API VM before a full schedule."
        )
    types = _chain_types(exc)
    if "response_format" in text and (
        "responseformat" in text
        or any(name in types for name in ("BadRequestError", "APIError", "ValidationError"))
    ):
        return ResponseFormatStop(
            "The completion failed around response_format. "
            "Stopping. Leave the causal prefix on.\n"
            f"{exc}"
        )
    if types & {"ValidationError", "JSONDecodeError"}:
        return CommandParseStop(
            "The model reply did not parse as "
            '{"thought": "...", "command": "..."}. '
            "Stopping. Leave the causal prefix on.\n"
            f"{exc}"
        )
    return None
