#!/bin/bash
# API 第 1 階：S26-api 一小時篩選（A 對 C，gemma-4-26b 開思考，付費批次同一組設定；2026-09-26）。
# 裁決：decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md §四（第 0 階通過才開、留出批次跑完之後才開）。
# 原型是檢討 workflow 寫的提案（ops/eval/evidence_20260926_local/review_effect/scripts/screen1h__screen_api.sh），這一份改了：
#   - base_url 明確指到付費記帳代理 :18901（run_one.sh 預設是 :18900＝本機模式，沒有 OpenRouter）；
#   - 預設 PAIRS=2（同時 4 個容器）、STOP_AT=4.70（付費帳本 4.80 硬上限之內）。
# 前置：付費代理要聽 docker 橋接（容器連得到）：
#   orproxy.py --config $S/evalrun/proxy.json --out $S/evalrun/ledger --host 172.17.0.1 --port 18901
# 題目：U＝付費 A 跑到 15 回合上限沒交的 18 題（容易題），K＝付費 A 答對、一跑 ≤ 300 秒的 8 題（種子 20260927）。26 對、52 跑。
# 用法：screen_api.sh <C 組的 vacant wheel> <jobs 目錄> [標籤前綴]
set -uo pipefail
S=/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad
REPO=$(cd "$(dirname "$0")/../../.." && pwd); H=$S/study/src/harbor
W=$1; J=$2; PFX=${3:-scrapi1}; PAIRS=${PAIRS:-2}; STOP_AT=${STOP_AT:-4.70}
export DABSTEP_PINNED=$S/dabstep_pinned/formal
mkdir -p "$J/logs"
TASKS=$(python3 -c "import random;t='3 7 10 15 16 17 18 19 39 43 47 48 58 62 65 69 71 72 8 12 25 30 35 42 56 63'.split();random.Random(20260927).shuffle(t);print(' '.join(t))")
spent() { python3 -c "import json;print(json.load(open('$S/evalrun/ledger/summary.json'))['spent_usd'])"; }
for t in $TASKS; do
  while [ "$(jobs -rp | wc -l)" -ge $((2*PAIRS)) ]; do sleep 5; done
  python3 -c "import sys;sys.exit(0 if float('$(spent)') < $STOP_AT else 1)" || { echo "budget stop before $t"; break; }
  for arm in A C; do
    tag="$PFX-g4-on-$arm-$t"
    bash "$REPO/ops/eval/pilot/run_one.sh" "$H" "$J" "$W" "$t" g4 on "$arm" \
      "http://172.17.0.1:18901/t/$tag/think/on/api/v1" > "$J/logs/$t-$arm.log" 2>&1 &
    sleep 2   # run_one.sh 沒有 --job-name；Harbor 預設的 job 名是秒級時間戳（RUNLOG §4 撞過）
  done
done
wait
echo "done; spent $(spent)"
