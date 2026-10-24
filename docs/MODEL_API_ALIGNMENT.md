# Model API alignment (Codebase Adaptation)

Cross-check against [cr-model-api-poc](https://github.com/based-models/cr-model-api-poc). If this file disagrees with production, the deployed API wins.

## Wiring

| Item | This run | Model API |
|---|---|---|
| Endpoint | `POST https://api.basedmodels.com/v1/chat/completions` | Chat completions. The Responses API is not implemented. |
| Model | `openai/glm-5.3-flash:causal-reflection` | Public id `glm-5.3-flash:causal-reflection`, Fireworks `accounts/fireworks/models/glm-5p3-flash` |
| Provider | `provider_mode=litellm_chat` | `auto` would send this `openai/` id to Responses |
| Headers | `X-Session-Id`, `X-Run-Id`, `X-Workload: coding` on every call | Workload freezes on the first turn; later calls still send it |
| Thinking | On | GLM thinking is always on. No `reasoning_effort`, no `chat_template_kwargs` |
| Structured output | ICL's `response_format` | Forwarded on the main completion for Fireworks models |
| Price | input $0.15 / cached $0.03 / output $0.50 per million | Same list rates as `ModelSpec` for GLM |
| Context | ICL `max_tokens=913408` | 1,048,576 window, 131,072 max output. LiteLLM has no row for this public id |

Sessions:

- Stateful: `clbench-codebase-glm-stateful-r{run}-codebase_adaptation`
- Stateless: `clbench-codebase-glm-stateless-r0-codebase_adaptation-{instance_id}`
- Run id: `clbench-codebase-glm-r{run}`

There is no graph on/off switch. A new session is an empty graph with the same prefix and readout tail.

## Why the observation is one user message

ICL's `observe()` appends `FEEDBACK:` as its own user turn, then the next `respond()` appends the follow-up prompt as a second user turn. The coding encoder (`_shell_observation`) uses the last user message and the assistant message directly before it. A user message in between drops the pair, so the pytest footer never becomes an edge.

`CausalReflectionICL.observe` holds the raw command output. The next `respond` places that output, then the task prompt, in the single user message after the assistant `{"command": ...}` JSON. The output is the mini-swe-agent observation, including `<returncode>` and the runner text.

The encoder classifies the first 2,000 characters of a plain-text user message (`_OBSERVATION_TEXT_CAP`). A pytest, vitest, or Go summary that would sit past that window is copied to the front. The full output stays in the message.

A pipe, a trailing `&`, or `head`/`tail` on the command still hides the runner result. This repo does not rewrite commands.

## Smoke

`codebase_adaptation` ships `schedules/default.json` only. This process registers `quick_test` as one instance, `jazzband__tablib-534`, with `runs=1` and `max_workers=1`. The tablib variant JSON is read from the checkout at `CLBENCH_ROOT` when the installed bench package omitted it.

Stop the run when:

- `response_format` is missing from the chat completion, or the API rejects it
- the reply does not parse to a `command` string

Leave the causal prefix on. `monthly spend cap reached` stops the run as well. That is `MONTHLY_SPEND_CAP_USD` on the API VM, currently $10, and it can fire during quick_test.

## Dashboard check

After smoke, the coding workload is on the session, `cost_usd` is set in the trace, the stateful rollout is one session, each stateless instance is its own session, and at least one edge follows a user message that contains a pytest, vitest, or Go footer.
