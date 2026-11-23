#!/usr/bin/env bash
# Run one Inkling domain on the bench VM.
#
# Usage: scripts/run_inkling.sh <domain> <smoke|full1|runs5>
# Domains: codebase database sales cohort poker spectrum
#
# Sets CLBENCH_MODEL_SLUG=inkling so the session id cannot resume a GLM graph.
# Sets a fresh CLBENCH_RUN_TAG. Do not reuse a tag.
set -euo pipefail

domain="${1:?domain: codebase database sales cohort poker spectrum}"
mode="${2:?mode: smoke full1 runs5}"

root="$(cd "$(dirname "$0")/.." && pwd)"
export CLBENCH_MODEL_SLUG=inkling

case "$domain-$mode" in
  codebase-smoke) config="$root/configs/codebase_inkling_smoke.json"; tag=inkling-codebase-smoke; runs= ;;
  codebase-full1) config="$root/configs/codebase_inkling.json"; tag=inkling-codebase-full1; runs=1 ;;
  codebase-runs5) config="$root/configs/codebase_inkling.json"; tag=inkling-codebase-runs5; runs=5 ;;
  database-smoke) config="$root/configs/database_inkling_smoke.json"; tag=inkling-db-smoke; runs= ;;
  database-full1) config="$root/configs/database_inkling.json"; tag=inkling-db-full1; runs=1 ;;
  database-runs5) config="$root/configs/database_inkling.json"; tag=inkling-db-runs5; runs=5 ;;
  sales-smoke) config="$root/configs/sales_inkling_smoke.json"; tag=inkling-sales-smoke; runs= ;;
  sales-full1) config="$root/configs/sales_inkling.json"; tag=inkling-sales-full1; runs=1 ;;
  sales-runs5) config="$root/configs/sales_inkling.json"; tag=inkling-sales-runs5; runs=5 ;;
  cohort-smoke) config="$root/configs/cohort_inkling_smoke.json"; tag=inkling-cohort-smoke; runs= ;;
  cohort-full1) config="$root/configs/cohort_inkling.json"; tag=inkling-cohort-full1; runs=1 ;;
  cohort-runs5) config="$root/configs/cohort_inkling.json"; tag=inkling-cohort-runs5; runs=5 ;;
  poker-smoke) config="$root/configs/poker_inkling_smoke.json"; tag=inkling-poker-smoke; runs= ;;
  poker-full1) config="$root/configs/poker_inkling.json"; tag=inkling-poker-full1; runs=1 ;;
  poker-runs5) config="$root/configs/poker_inkling.json"; tag=inkling-poker-runs5; runs=5 ;;
  spectrum-smoke) config="$root/configs/spectrum_inkling_smoke.json"; tag=inkling-spectrum-smoke; runs= ;;
  spectrum-full1) config="$root/configs/spectrum_inkling.json"; tag=inkling-spectrum-full1; runs=1 ;;
  spectrum-runs5) config="$root/configs/spectrum_inkling.json"; tag=inkling-spectrum-runs5; runs=5 ;;
  *)
    echo "Unknown $domain $mode" >&2
    exit 2
    ;;
esac

export CLBENCH_RUN_TAG="$tag"
if [[ -n "$runs" ]]; then
  exec cr-clbench run --config "$config" --runs "$runs"
fi
exec cr-clbench run --config "$config"
