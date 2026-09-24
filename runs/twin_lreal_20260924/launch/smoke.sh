#!/usr/bin/env bash
# 冒煙：1 居民 × s1_01_addmul（兩份題面），與 09-19 smoke.sh 同參數，外加 --events。
set -uo pipefail
. /var/tmp/vacant_lreal_20260924/env.sh
cd /var/tmp/vacant_lreal_20260924/repo
python3 ops/exhibit/twin/run_twin.py --out /var/tmp/vacant_lreal_20260924/smoke \
  --residents 1 --tasks s1_01_addmul \
  --upstream http://100.86.226.21:1234 --model gemma-4-12b-it-qat \
  --evidence L-real --retry revise --max-attempts 3 --timeout 300 \
  --events /var/tmp/vacant_lreal_20260924/smoke/lifecycle.jsonl \
  -- /var/tmp/vacant_lreal_20260924/repo/ops/vacantrun/wrap_agent.sh pi "{TASK}"
echo "SMOKE_RC=$?"
