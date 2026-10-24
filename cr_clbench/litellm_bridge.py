"""LiteLLM chat-completion bridge for the causal-reflection gateway.

The bench's auto mode sends an ``openai/`` model to the Responses API. This
gateway implements chat completions, so every call goes through
``litellm.completion`` with ``provider_mode=litellm_chat``. Thinking stays on:
these calls do not send ``reasoning_effort`` or ``chat_template_kwargs``.
``response_format`` is left exactly as ICL set it.
"""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator
from typing import Any

import litellm

from .constants import API_BASE

_DROPPED = ("reasoning_effort", "chat_template_kwargs")


def prepare_completion_kwargs(
    kwargs: dict[str, Any],
    *,
    extra_headers: dict[str, str],
    api_base: str,
    api_key: str,
) -> dict[str, Any]:
    """Return the kwargs for one chat completion."""
    prepared = dict(kwargs)
    headers = dict(extra_headers)
    incoming = prepared.get("extra_headers") or {}
    if isinstance(incoming, dict):
        headers.update({str(key): str(value) for key, value in incoming.items()})
    for name in ("X-Session-Id", "X-Run-Id", "X-Workload"):
        if not headers.get(name):
            raise ValueError(f"missing {name} on a causal-reflection completion")
    prepared["extra_headers"] = headers
    prepared["api_base"] = api_base or API_BASE
    prepared["api_key"] = api_key
    for name in _DROPPED:
        prepared.pop(name, None)
    extra_body = prepared.get("extra_body")
    if isinstance(extra_body, dict):
        body = dict(extra_body)
        for name in _DROPPED:
            body.pop(name, None)
        if body:
            prepared["extra_body"] = body
        else:
            prepared.pop("extra_body", None)
    return prepared


@contextmanager
def completion_scope(
    *,
    extra_headers: dict[str, str],
    api_base: str,
    api_key: str,
) -> Iterator[list[dict[str, Any]]]:
    """Inject gateway kwargs into ``litellm.completion`` for one system turn.

    Records whether each outgoing call still carried ``response_format``.
    The list does not include the API key.
    """
    original = litellm.completion
    sent: list[dict[str, Any]] = []

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        prepared = prepare_completion_kwargs(
            kwargs,
            extra_headers=extra_headers,
            api_base=api_base,
            api_key=api_key,
        )
        sent.append(
            {
                "response_format": prepared.get("response_format"),
                "extra_headers": dict(prepared["extra_headers"]),
                "model": prepared.get("model"),
            }
        )
        return original(*args, **prepared)

    litellm.completion = wrapped
    try:
        yield sent
    finally:
        litellm.completion = original
