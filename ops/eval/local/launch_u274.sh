#!/bin/bash
# 預註冊 PREREG_20260927_NOCAP_UNSEEN 的啟動檔（2026-09-27）：先驗 wheel 與題目清單的 sha256（對不上就不跑），
# 跑共用佇列驅動；結束後 infra_void 移開、同一組參數補跑一次（過了時間上限也只補開始過的題）；最後寫 DONE。
# 用法：launch_u274.sh <harbor 目錄> <jobs 目錄> <釘死的 450 題目錄> <C361 wheel> <代理 ledger 目錄>
set -uo pipefail
HARBOR=$1; JOBS=$2; DATA=$3; WHEEL=$4; LEDGER=$5
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
MAN=$REPO/ops/eval/evidence_20260927_nocap/unseen/UNSEEN_MANIFEST.json
[ "$(sha256sum < "$WHEEL" | cut -d' ' -f1)" = 4ec156d6648d214baa9bc5be4093f8b8731112f16a6ee61b6118d70b41def0b4 ] || { echo "wheel sha256 mismatch"; exit 1; }
[ "$(sha256sum < "$MAN" | cut -d' ' -f1)" = 43a8f4eebd94da98ccdb31822115e5ec64f36c789d7f6807f01094f5baf28ef0 ] || { echo "manifest sha256 mismatch"; exit 1; }
mkdir -p "$JOBS"
export MAX_TURNS=none
drive() {
  python3 "$REPO/ops/eval/local/run_pairs.py" --harbor "$HARBOR" --jobs "$JOBS" --dataset "$DATA" --manifest "$MAN" \
    --arms A=- "C361=$WHEEL" --samples 1 --upstreams ${UPSTREAMS:-w401:4 1003:4} --seed 20260929 --prefix u274 \
    --deadline 2026-09-28T00:00:00Z
}
echo "[$(date -u +%FT%TZ)] start (${UPSTREAMS:-w401:4 1003:4})"
drive >> "$JOBS/driver.log" 2>&1
echo "[$(date -u +%FT%TZ)] driver finished; infra_void rerun"
"$REPO/.venv/bin/python" "$REPO/ops/eval/local/rerun_void.py" --jobs "$JOBS" --ledger "$LEDGER" --dataset "$DATA" --prefix u274 >> "$JOBS/rerun_void.log" 2>&1
drive >> "$JOBS/driver_rerun.log" 2>&1
echo "[$(date -u +%FT%TZ)] all runs finished"
touch "$JOBS/DONE"
