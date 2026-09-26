#!/bin/bash
# 正式批次（PREREG_20260926_ZERO_CONFIG_V3_LOCAL）跑完之後：
#   1. 它的 infra_void 照順序補跑一次（那一份第四節；rerun_void.py 移開、同一組參數再跑）；
#   2. 開留出批次（PREREG_20260926_ZERO_CONFIG_V34_HELDOUT 第五節）。
# 兩個批次不同時用兩台機器。停止規則只看時間，這支不讀任何評分的值。
# 用法：after_formal.sh <harbor> <local 暫存根目錄> <釘死的題目根目錄> <C1 wheel> <C2 wheel> <C3 wheel>
#   <釘死的題目根目錄> 底下要有 formal/（79 題）與 dabstep/（450 題）
set -uo pipefail
HARBOR=$1; L=$2; PIN=$3; W1=$4; W2=$5; W3=$6
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
PY=$REPO/.venv/bin/python
DEADLINE=2026-09-27T04:00:00Z
cd "$REPO"
echo "[$(date -u +%FT%TZ)] waiting for the formal driver"
while pgrep -f "run_batch.py --harbor .* --jobs $L/formal_v3 " >/dev/null; do sleep 60; done
echo "[$(date -u +%FT%TZ)] formal driver finished; infra_void re-runs"
"$PY" ops/eval/local/rerun_void.py --jobs "$L/formal_v3" --ledger "$L/ledger" --dataset "$PIN/formal" --prefix v3local
python3 ops/eval/local/run_batch.py --harbor "$HARBOR" --jobs "$L/formal_v3" --dataset "$PIN/formal" \
  --arms A=- C1="$W1" C2="$W2" --samples 1 2 3 --upstreams w401:3 1003:1 --deadline "$DEADLINE" --prefix v3local \
  >> "$L/formal_v3/driver_rerun.log" 2>&1
echo "[$(date -u +%FT%TZ)] formal re-runs done; starting the held-out batch"
TASKS=$(python3 -c "import json;print(' '.join(t['task'] for t in json.load(open('ops/eval/evidence_20260926_local/heldout/HELDOUT_MANIFEST.json'))['tasks']))")
mkdir -p "$L/heldout_v34"
python3 ops/eval/local/run_batch.py --harbor "$HARBOR" --jobs "$L/heldout_v34" --dataset "$PIN/dabstep" \
  --tasks $TASKS --arms A=- C3="$W3" --samples 1 2 --upstreams w401:3 1003:1 --seed 20260927 \
  --deadline "$DEADLINE" --prefix h34 > "$L/heldout_v34/driver.log" 2>&1
echo "[$(date -u +%FT%TZ)] held-out driver finished; infra_void re-runs"
"$PY" ops/eval/local/rerun_void.py --jobs "$L/heldout_v34" --ledger "$L/ledger" --dataset "$PIN/dabstep" --prefix h34
python3 ops/eval/local/run_batch.py --harbor "$HARBOR" --jobs "$L/heldout_v34" --dataset "$PIN/dabstep" \
  --tasks $TASKS --arms A=- C3="$W3" --samples 1 2 --upstreams w401:3 1003:1 --seed 20260927 \
  --deadline "$DEADLINE" --prefix h34 >> "$L/heldout_v34/driver_rerun.log" 2>&1
echo "[$(date -u +%FT%TZ)] all done"
