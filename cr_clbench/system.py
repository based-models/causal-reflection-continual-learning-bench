"""ICL subclass that calls GLM 5.3 Flash through the causal-reflection API."""

from __future__ import annotations

import os
from dataclasses import replace

from src.interface import Observation, Query, Response
from src.systems.icl.system import ICLSystem

from .constants import (
    API_BASE,
    CONTEXT_BUDGET_TOKENS,
    LEADERBOARD_NAME,
    LITELLM_MODEL,
    TASK_NAME,
)
from .integrate import current_scope, install_runtime
from .litellm_bridge import completion_scope
from .pricing import register_prices
from .sessions import causal_headers, session_kind, workload_for
from .stop import (
    CausalReflectionStop,
    CommandParseStop,
    ResponseFormatStop,
    classify_stop,
)
from .transcript import merge_user_turn

install_runtime()


class CausalReflectionICL(ICLSystem):
    """Stock ICL, with gateway headers and one observation message per turn.

    ``provider_mode`` stays ``litellm_chat``. The context budget is the GLM
    5.3 Flash window minus output and the causal wrapper, so an unknown model
    id still truncates against the real limit.
    """

    supports_baseline = True

    def __init__(
        self,
        model: str = LITELLM_MODEL,
        max_tokens: int | None = CONTEXT_BUDGET_TOKENS,
        system_prompt: str = "",
        name: str = LEADERBOARD_NAME,
        reserve_tokens: int = 500,
        provider_mode: str = "litellm_chat",
        openai_store: bool = True,
        openai_include_encrypted_reasoning: bool = False,
        anthropic_max_tokens: int | None = None,
        api_base: str = API_BASE,
    ):
        if provider_mode != "litellm_chat":
            raise ValueError(
                "provider_mode must be litellm_chat. "
                "The gateway implements chat completions, and auto mode sends "
                "an openai/ model to the Responses API."
            )
        if max_tokens is None:
            max_tokens = CONTEXT_BUDGET_TOKENS
        register_prices()
        super().__init__(
            model=model,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            name=name,
            reserve_tokens=reserve_tokens,
            provider_mode=provider_mode,
            openai_store=openai_store,
            openai_include_encrypted_reasoning=openai_include_encrypted_reasoning,
            anthropic_max_tokens=anthropic_max_tokens,
        )
        self.api_base = api_base or API_BASE
        self._pending_observation = ""
        self._session_ids: list[str] = []

    def respond(self, query: Query) -> Response:
        api_key = (os.environ.get("CRA_API_KEY") or "").strip()
        if not api_key:
            raise CausalReflectionStop(
                "CRA_API_KEY is unset. Refusing to call the model API."
            )
        pending = self._pending_observation
        self._pending_observation = ""
        task_id = self._task_id()
        if pending:
            query = replace(
                query,
                prompt=merge_user_turn(
                    pending,
                    query.prompt or "",
                    promote_footer=workload_for(task_id) != "query",
                ),
            )
        headers = self._headers_for(query)
        with completion_scope(
            extra_headers=headers,
            api_base=self.api_base,
            api_key=api_key,
        ) as sent:
            try:
                response = super().respond(query)
            except CausalReflectionStop:
                raise
            except Exception as exc:
                stopped = classify_stop(exc)
                if stopped is not None:
                    raise stopped from exc
                raise
        if not sent or any(item.get("response_format") is None for item in sent):
            raise ResponseFormatStop(
                "ICL did not send response_format on the chat completion. "
                "Stopping. Leave the causal prefix on."
            )
        self._require_task_action(response, task_id)
        metadata = dict(response.metadata or {})
        metadata["causal_reflection"] = {
            "run_id": headers["X-Run-Id"],
            "session_id": headers["X-Session-Id"],
            "workload": headers["X-Workload"],
            "session_kind": session_kind(current_scope()),
            "response_format_sent": True,
            "model": self.model,
        }
        response.metadata = metadata
        self._session_ids.append(headers["X-Session-Id"])
        return response

    def observe(
        self, observation: Observation, next_query: Query | None = None
    ) -> None:
        """Hold the raw output for the next user message.

        Stock ICL appends ``FEEDBACK:`` as its own user turn. The encoder
        pairs the assistant action with the user message directly after it, so
        a second user message hides the runner output or the SQL result. The
        output is sent unchanged on the next respond.
        """
        del next_query
        content = (observation.content or "").strip()
        if content:
            self._pending_observation = content

    def reset(self) -> None:
        self._pending_observation = ""
        super().reset()

    def get_run_artifacts(self) -> dict:
        payload = super().get_run_artifacts()
        payload["causal_sessions"] = list(dict.fromkeys(self._session_ids))
        payload["leaderboard_name"] = LEADERBOARD_NAME
        return payload

    def _task_id(self) -> str:
        scope = current_scope()
        if scope is None or not scope.task_name:
            return TASK_NAME
        return scope.task_name

    def _require_task_action(self, response: Response, task_id: str) -> None:
        if workload_for(task_id) == "query":
            action = getattr(response.action, "action", None)
            content = getattr(response.action, "content", None)
            if not isinstance(action, str) or action.strip().upper() not in {
                "QUERY",
                "ANSWER",
            }:
                raise CommandParseStop(
                    "The parsed action is not QUERY or ANSWER. "
                    "Stopping. Leave the causal prefix on."
                )
            if not isinstance(content, str) or (
                action.strip().upper() == "QUERY" and not content.strip()
            ):
                raise CommandParseStop(
                    "QUERY has no SQL content. "
                    "Stopping. Leave the causal prefix on."
                )
            return
        command = getattr(response.action, "command", None)
        if not isinstance(command, str) or not command.strip():
            raise CommandParseStop(
                "The parsed action has no command string. "
                "Stopping. Leave the causal prefix on."
            )

    def _headers_for(self, query: Query) -> dict[str, str]:
        scope = current_scope()
        kind = session_kind(scope)
        task_id = self._task_id()
        run_index = None if scope is None else scope.run_index
        return causal_headers(
            kind=kind,
            run_index=run_index,
            task_id=task_id,
            instance_id=query.instance_id,
        )
