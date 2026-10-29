# Submission names

Public row for the six finished five-run domains. The harness is stock ICL. The model id stays `openai/glm-5.3-flash:causal-reflection`.

| Role | Value |
|---|---|
| `final_results/runs/` directory (`run_name`) | `icl-glm-5.3-flash-causal-reflection` |
| `MODEL_DISPLAY` key in `scripts/generate_leaderboard.py` | `glm-5.3-flash-causal-reflection` |
| `MODEL_DISPLAY` value | `GLM 5.3 Flash Causal Reflection` |
| Website `display_name` | `ICL · GLM 5.3 Flash Causal Reflection` |
| `summary.system.params.name` | `ICL · GLM 5.3 Flash Causal Reflection` |
| `summary.system.name` | `icl` |
| `summary.system.params.model` | `openai/glm-5.3-flash:causal-reflection` |

`generate_leaderboard.py` builds the site label from the directory name. With that `MODEL_DISPLAY` entry, `icl-glm-5.3-flash-causal-reflection` becomes **ICL · GLM 5.3 Flash Causal Reflection**. Add the same slug to `DEFAULT_RUN_NAMES` in `scripts/analyze_final_results.py`, or pass `--run icl-glm-5.3-flash-causal-reflection`.

Those two edits belong in the continual-learning-bench pull request. They are not in this repo.

Future runs in this repo use the same `params.name` via `LEADERBOARD_NAME` and the GLM configs. The five-run files below were recorded with `ICL + GLM 5.3 Flash`. The packaged copies on the VM were rewritten to the new name. Scores, `run_group_id`, traces, `system.name`, and `params.model` were left as recorded. The original `viewer_artifact_*.json.gz` files were not rewritten.

## Packaged copies

On `deep-swe-bench-run`, under `~/continual-learning-bench/final_results/runs/icl-glm-5.3-flash-causal-reflection/tasks/`.

| Task file | Source viewer artifact | Tag |
|---|---|---|
| `codebase_adaptation.json.gz` | `results/codebase_adaptation/viewer_artifact_2026-10-25T15-56-07.908259Z_20261025_192607.json.gz` | `runs5b` |
| `database_exploration.json.gz` | `results/database_exploration/viewer_artifact_2026-10-25T23-35-17.581405Z_20261026_014555.json.gz` | `db-runs5` |
| `sales_prediction.json.gz` | `results/sales_prediction/viewer_artifact_2026-10-26T19-43-47.587911Z_20261026_214541.json.gz` | `sales-runs5` |
| `cohort_studies.json.gz` | `results/cohort_studies/viewer_artifact_2026-10-27T01-24-50.796441Z_20261027_051314.json.gz` | `cohort-runs5` |
| `exploitable_poker.json.gz` | `results/exploitable_poker/viewer_artifact_2026-10-28T03-45-34.734640Z_20261028_162154.json.gz` | `poker-runs5c` |
| `blind_spectrum_monitoring.json.gz` | `results/blind_spectrum_monitoring/viewer_artifact_2026-10-28T18-42-45.296806Z_20261028_223736.json.gz` | `spectrum-runs5` |

Paths are relative to `~/continual-learning-bench`. Each source is a five-run `viewer_artifact`. Copy these task files into the bench checkout at `final_results/runs/icl-glm-5.3-flash-causal-reflection/tasks/` for the pull request. `run-all` does not pick up a viewer artifact from an earlier invocation.
