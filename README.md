# Causal reflection on Continual Learning Bench

Score **ICL · GLM 5.3 Flash Causal Reflection** on [Continual Learning Bench](https://continual-learning-bench.com/) through the Based Models causal-reflection API. The harness is stock [continual-learning-bench](https://github.com/pgasawa/continual-learning-bench) at `5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26`. This repo subclasses its ICL system. It does not copy ICL.

The finished domains so far are Codebase Adaptation (`X-Workload: coding`), Database Exploration (`X-Workload: query`), Sales Prediction (`X-Workload: forecast`), Cohort Studies (`X-Workload: cohort`), Exploitable Poker (`X-Workload: strategy`), and Blind Spectrum Monitoring (`X-Workload: registry`).

The comparison is retained state under the same wrapper. A new session starts with an empty graph and still receives the causal prefix and readout tail. The stateful rollout keeps one session across instances. The stateless baseline starts a new session for every instance.

| Phase | Harness | Session id |
|---|---|---|
| Stateful rollout | `reset_between_instances=False` | `clbench-{slug}-glm-stateful-r{run}-{task}` |
| Stateless baseline | baseline phase, reset between instances | `clbench-{slug}-glm-stateless-r0-{task}-{instance_id}` |

`slug` is `codebase`, `database`, `sales`, `cohort`, `poker`, or `spectrum`. The task id is `codebase_adaptation`, `database_exploration`, `sales_prediction`, `cohort_studies`, `exploitable_poker`, or `blind_spectrum_monitoring`.

`{run}` is 1-based. Rollout repeat 0 is `r1`. The baseline is `r0`. A new rollout repeat gets a new session. Set `CLBENCH_RUN_TAG` when a repeated smoke should not resume an existing `r0` or `r1` graph.

Leaderboard name: **ICL · GLM 5.3 Flash Causal Reflection**. Model id: `glm-5.3-flash:causal-reflection`. Submission folder, display map, and the six viewer paths are in [docs/SUBMISSION.md](docs/SUBMISSION.md).

## What this run scores

Codebase Adaptation, Database Exploration, Sales Prediction, Cohort Studies, Exploitable Poker, and Blind Spectrum Monitoring. Each domain is one `cr-clbench run`. `run-all` stays rejected: it would start every domain at once, and it does not adopt a trace that already finished.

The coding pack reads the assistant JSON `command` field as the shell command. An edge needs the next user message in that same session to contain a real runner footer: a pytest line such as `3 passed in 0.42s`, a vitest `Tests` line, or a Go `ok <pkg>` / `FAIL <pkg>` line. The wrapper keeps the environment's raw command output in that user message. A pipe, a trailing `&`, or `head`/`tail` on the command hides the runner result from the encoder.

The query pack reads `{"action": "QUERY", "content": "<sql>"}`. `.tables`, `.schema`, and `PRAGMA` can record the schema. A repeated data query records no progress. `ANSWER` records nothing. The migration notice `schema or contents may have changed` drops schema edges. The wrapper keeps the SQL result, then the next question, in that one user message.

The forecast pack reads a bash `command` during analysis and a `predictions` list at submission. A shell exit code is not an outcome. The score edge is attached when a later user message contains `Predictions recorded for year` or the `feedback_year` / `entries` JSON, and only if an earlier command was a `.py` or `.R` script or carried `--model`. `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` does not replace that remembered script.

The cohort pack reads the tool result in the user message. A `=== Columns ===` listing and a grouped `S(12m)=` table become edges. The KL section does not. `Report submitted for <STUDY>.` drops that study's column facts and stores nothing for the 108 survival numbers.

The strategy pack reads the user message. A decision prompt stores `Opponent: Tom` and writes nothing. `Action taken` writes nothing. `Net chip change this hand` is booked to the opponent stored from the decision prompt, then a `NOTICE` or the next `Opponent:` line becomes the seated name. One edge per opponent carries the running chip total. An auto-resolved hand after `Additional auto-resolved hand while advancing to the next prompt:` is booked to the notice name.

The registry pack reads `freq:` lines between `Detected peaks:` and `Band:`. `Scan N recorded.` writes nothing. A peak within 4 MHz of a stored center is that center. A new center is quantized to 0.5 MHz. The first sight is stored and writes no edge. The second sight of that center writes one edge, `defines seen_N <center>`, and a later sight replaces it. A scan with no peaks leaves every center in place. The model's own transmitter list is not the evidence.

## Codebase Adaptation result to keep

Five-run group `2026-10-25T15-56-07.908259Z`, tag `runs5b`, on `deep-swe-bench-run`. This is the Codebase Adaptation piece of a later submission. Do not re-run it.

```text
~/continual-learning-bench/results/codebase_adaptation/traces/2026-10-25T15-56-07.908259Z
~/continual-learning-bench/results/codebase_adaptation/viewer_artifact_2026-10-25T15-56-07.908259Z_20261025_192607.json.gz
```

The gzip is the summary a submission copies to `final_results/runs/<name>/tasks/codebase_adaptation.json.gz`. The trace directory is the full record. A later `run-all` only harvests artifacts from the invocation it just started, so this file has to be copied in by hand when the other domains are ready.

## API

| | |
|---|---|
| Base URL | `https://api.basedmodels.com/v1` |
| Endpoint | `POST /v1/chat/completions` |
| Auth | `Authorization: Bearer` with a dashboard API key (`CRA_API_KEY`) |
| LiteLLM model | `openai/glm-5.3-flash:causal-reflection` |
| `provider_mode` | `litellm_chat` |

The bench's `auto` mode treats an `openai/` model as the OpenAI Responses API. This gateway implements chat completions, so the system forces `litellm_chat`. Thinking stays on. Calls do not send `reasoning_effort` or `chat_template_kwargs`. ICL's `response_format` is left in place. Codebase Adaptation's action schema is `{"thought": "...", "command": "<one bash command>"}`. Database Exploration's schema is `{"action": "QUERY"|"ANSWER", "content": "<sql or exact value>"}`. Sales Prediction uses the command schema, then a `predictions` list. Cohort Studies uses `{"thought", "tool_call"}`, then the flat survival fields. Exploitable Poker uses `{"thinking", "action", "amount"}`, where `action` is `FOLD`, `CALL`, `CHECK`, or `RAISE` and `amount` is the raise total.

Every completion sends `X-Session-Id`, `X-Run-Id`, and `X-Workload` (`coding`, `query`, `forecast`, `cohort`, or `strategy`), including after the API has frozen workload on the session. `X-Session-Id` is always set. A missing session id lets the API resume an older session by message-prefix match, and parallel work on one key can cross-wire.

Price registered for the model id the bench looks up, per million tokens: input `$0.15`, cached input `$0.03`, output `$0.50`. The bench reads `prompt_tokens`, `completion_tokens`, and `prompt_tokens_details.cached_tokens`. A missing cache count is 0. The ICL context budget is set to **913,408** tokens: GLM 5.3 Flash's 1,048,576 window, minus the 131,072 output cap and 4,096 tokens for the causal prefix and readout tail.

`MONTHLY_SPEND_CAP_USD` for this campaign is $1000 on the API VM. A cap rejection is an API limit.

If a completion drops `response_format`, or the reply does not match the task schema, the run stops. Leave the causal prefix on.

## Upstream schedule

The task slug is `codebase_adaptation`. The checkout ships one schedule, `default`: nine tablib issues, then ten tenacity issues, five runs, twelve workers. It has no `quick_test` file. `quick_test` in this repo is one tablib issue, `jazzband__tablib-534`, one run, one worker, registered in-process so the stock task loader accepts `--schedule quick_test`.

A non-editable install of the bench keeps the Python modules and drops `schedules/*.json` and `variants/*.json`. `CLBENCH_ROOT` (or a working directory that is the checkout) supplies those files and `data/codebase_adaptation/final-dataset.jsonl`. `uv sync` in the checkout is editable, so the files already sit beside the task module.

## Bench VM

Use `deep-swe-bench-run` in `us-west1-b`. The model API stays on `cr-model-api-poc`. This bench VM needs Docker: Codebase Adaptation executes in a container, and model calls go out from the host to `https://api.basedmodels.com`.

Python **3.13**. On Debian, `python3` may already be 3.13. On Ubuntu 22.04, install 3.13 before `uv` or `venv`.

```bash
sudo apt-get update
sudo apt-get install -y docker.io git tmux
sudo usermod -aG docker "$USER"
# log out and back in so docker works without sudo

curl -LsSf https://astral.sh/uv/install.sh | sh

git clone https://github.com/pgasawa/continual-learning-bench.git ~/continual-learning-bench
cd ~/continual-learning-bench
git checkout 5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26
uv sync --extra codebase_adaptation
source .venv/bin/activate

git clone https://github.com/based-models/causal-reflection-continual-learning-bench.git ~/causal-reflection-continual-learning-bench
uv pip install -e ~/causal-reflection-continual-learning-bench

cp ~/causal-reflection-continual-learning-bench/.env.example ~/causal-reflection-continual-learning-bench/.env
# put the dashboard key in CRA_API_KEY

export CLBENCH_ROOT=~/continual-learning-bench
cd "$CLBENCH_ROOT"
clbench setup codebase_adaptation
```

`clbench setup` pulls the Docker images named by the schedules. The key stays in `.env`. Do not commit it.

## Smoke

One worker, `quick_test`, Codebase Adaptation only. This runs the stateless baseline and one stateful rollout on `jazzband__tablib-534`.

```bash
cd "$CLBENCH_ROOT"
export CLBENCH_ROOT
set -a && source ~/causal-reflection-continual-learning-bench/.env && set +a
cr-clbench run --config ~/causal-reflection-continual-learning-bench/configs/codebase_glm_smoke.json
```

Print the ids without calling the model:

```bash
cr-clbench ids
```

After the smoke, check:

- Dashboard sessions for this run show workload `coding`.
- The stateful rollout is one session across its instances. Each stateless instance is its own session. Trace responses carry `metadata.causal_reflection.session_id`.
- `cost_usd` is filled in on the trace usage.
- At least one coding edge appears after a user message that contains a pytest, vitest, or Go footer.
- Stop if the API drops `response_format` or the reply has no `command` string.

A full `default` schedule is `configs/codebase_glm.json` (five runs, one worker).

## Database Exploration

Local SQLite, not Docker. Download the databases once:

```bash
cd "$CLBENCH_ROOT"
export CLBENCH_ROOT
set -a && source ~/causal-reflection-continual-learning-bench/.env && set +a
clbench setup database_exploration
```

Smoke, one question, one worker:

```bash
screen -S clbench
export CLBENCH_RUN_TAG=db-smoke
cr-clbench run --config ~/causal-reflection-continual-learning-bench/configs/database_glm_smoke.json
```

One full pass, then five repeats, each with a new tag:

```bash
export CLBENCH_RUN_TAG=db-full1
cr-clbench run --config ~/causal-reflection-continual-learning-bench/configs/database_glm.json --runs 1

export CLBENCH_RUN_TAG=db-runs5
cr-clbench run --config ~/causal-reflection-continual-learning-bench/configs/database_glm.json --runs 5
```

`default` is schema drift: 20 questions, then the migration notice, then 20 questions on `products_drifted.db`. `max_workers` stays 1. Reusing a tag resumes that graph. The smoke session is `clbench-database-glm-stateful-r1-db-smoke-database_exploration`.

## Sales Prediction

Docker, one container at a time. Pull the image once, from the bench checkout:

```bash
cd "$CLBENCH_ROOT"
export CLBENCH_ROOT
set -a && source ~/causal-reflection-continual-learning-bench/.env && set +a
clbench setup sales_prediction
```

The bench venv also needs the sales extra if it is not already installed: `pandas`, `numpy`, `scikit-learn`, and `pyyaml`. `mini-swe-agent` is already there from Codebase Adaptation.

Smoke is the first two frozen lifecycle years. The second year is the one that sends the first year's score back to the model. One full pass is 12 years. Five repeats use a new tag. Deploy the API build that contains the forecast pack before the first call.

```bash
screen -S clbench
export CLBENCH_RUN_TAG=sales-smoke
cr-clbench run --config ~/causal-reflection-continual-learning-bench/configs/sales_glm_smoke.json
```

```bash
export CLBENCH_RUN_TAG=sales-full1
cr-clbench run --config ~/causal-reflection-continual-learning-bench/configs/sales_glm.json --runs 1

export CLBENCH_RUN_TAG=sales-runs5
cr-clbench run --config ~/causal-reflection-continual-learning-bench/configs/sales_glm.json --runs 5
```

`max_workers` stays 1. The stateful session is `clbench-sales-glm-stateful-r1-<tag>-sales_prediction`. Reusing a tag resumes that graph.

## Cohort Studies

Local SQLite. The frozen studies are already in the bench checkout at `data/cohort_studies/default/`. The bench venv needs `lifelines` and `pandas`. No Docker image. Deploy the API build that contains the cohort pack before the first call.

Smoke is the first HERALD study. One full pass is 20 studies. Five repeats use a new tag.

```bash
screen -S clbench
export CLBENCH_RUN_TAG=cohort-smoke
cr-clbench run --config ~/causal-reflection-continual-learning-bench/configs/cohort_glm_smoke.json
```

```bash
export CLBENCH_RUN_TAG=cohort-full1
cr-clbench run --config ~/causal-reflection-continual-learning-bench/configs/cohort_glm.json --runs 1

export CLBENCH_RUN_TAG=cohort-runs5
cr-clbench run --config ~/causal-reflection-continual-learning-bench/configs/cohort_glm.json --runs 5
```

`max_workers` stays 1. The stateful session is `clbench-cohort-glm-stateful-r1-<tag>-cohort_studies`. Reusing a tag resumes that graph.

## Exploitable Poker

In-process heads-up Hold'em. No Docker image. The bench venv needs `texasholdem==0.11.0`. The schedules and opponent variants are already in the bench checkout. Deploy the API build that contains the strategy pack before the first call.

Smoke is five hands against Tom. The second hand is the one that sends the first hand's chip change back to the model. One full pass is 120 hands: Tom, Alex, Tom, Adam, Alex. Five repeats use a new tag. The smoke config sets `runs` to 1 because the upstream `quick_test` schedule asks for 3.

```bash
~/.local/bin/uv pip install 'texasholdem==0.11.0'
export CLBENCH_RUN_TAG=poker-smoke
cr-clbench run --config ~/causal-reflection-continual-learning-bench/configs/poker_glm_smoke.json
```

```bash
export CLBENCH_RUN_TAG=poker-full1
cr-clbench run --config ~/causal-reflection-continual-learning-bench/configs/poker_glm.json --runs 1

export CLBENCH_RUN_TAG=poker-runs5
cr-clbench run --config ~/causal-reflection-continual-learning-bench/configs/poker_glm.json --runs 5
```

`max_workers` stays 1. The stateful session is `clbench-poker-glm-stateful-r1-<tag>-exploitable_poker`. Reusing a tag resumes that graph. An action string other than `FOLD`, `CALL`, `CHECK`, or `RAISE` is returned to the task, which rejects it and repeats the decision. A reply with no action string stops the run.

## Blind Spectrum Monitoring

Each scan is one transmitter report. No Docker image. The frozen `mixed_grid_lifecycle` corpus, the default schedule, the three variants, and the Jinja templates are in the bench checkout. Deploy the API build that contains the registry pack before the first call. `repeat_instructions` stays false, matching the official ICL config, so the long instructions appear only on scan 1.

Smoke is the first two scans of that corpus. Scan 2 is the turn that sends `Scan 1 recorded.` and the next peak list. One full pass is 90 scans. Five repeats use a new tag. The header must be `registry`. `spectrum` and the task name fall through to the generic pack.

```bash
export CLBENCH_RUN_TAG=spectrum-smoke
cr-clbench run --config ~/causal-reflection-continual-learning-bench/configs/spectrum_glm_smoke.json
```

```bash
export CLBENCH_RUN_TAG=spectrum-full1
cr-clbench run --config ~/causal-reflection-continual-learning-bench/configs/spectrum_glm.json --runs 1

export CLBENCH_RUN_TAG=spectrum-runs5
cr-clbench run --config ~/causal-reflection-continual-learning-bench/configs/spectrum_glm.json --runs 5
```

`max_workers` stays 1. The stateful session is `clbench-spectrum-glm-stateful-r1-<tag>-blind_spectrum_monitoring`. Reusing a tag resumes that graph. A report is a `transmitters` list, and an empty list is a legal report. A reply with no list stops the run.

## Layout

```text
cr_clbench/          # ICL subclass, headers, price entry, quick_test schedule
configs/             # smoke (quick_test) and default schedule
docs/MODEL_API_ALIGNMENT.md
docs/SUBMISSION.md
tests/
```

## Related repos

| Repo | Role |
|---|---|
| [cr-model-api-poc](https://github.com/based-models/cr-model-api-poc) | Production API. Unchanged by this run. |
| [continual-learning-bench](https://github.com/pgasawa/continual-learning-bench) | Harness and Codebase Adaptation task. |
| [causal-reflection-terminal-bench](https://github.com/based-models/causal-reflection-terminal-bench) | Same API, Harbor Terminus, `X-Workload: coding`. |
| [causal-reflection-tau2-bench](https://github.com/based-models/causal-reflection-tau2-bench) | Same API, `X-Workload: tool-use`. |
