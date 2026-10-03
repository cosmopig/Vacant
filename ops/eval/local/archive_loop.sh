#!/bin/bash
# 原始資料定期歸檔進 repo（2026-09-27）：每 INTERVAL 秒跑一次 archive_raw.py，有新的包就 commit＋push（重試 2/4/8/16 秒）。
# 驅動跑完（STOP_FILE 出現）之後再歸檔最後一次就結束。git 被別的 commit 占著（index.lock）就等下一輪，不搶。
# 用法：archive_loop.sh <jobs> <代理 ledger 目錄> <標籤前綴> <repo 裡的證據目錄（相對 repo 根）> <秒> <停止旗標檔>
set -uo pipefail
JOBS=$1; LEDGER=$2; PFX=$3; OUT=$4; INTERVAL=${5:-7200}; STOP_FILE=$6
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$REPO"
round() {
  python3 ops/eval/local/archive_raw.py --jobs "$JOBS" --ledger "$LEDGER" --prefix "$PFX" --out "$OUT" || return 1
  [ -e .git/index.lock ] && { echo "[$(date -u +%FT%TZ)] git busy; next round"; return 0; }
  git add "$OUT" && git diff --cached --quiet -- "$OUT" && { echo "[$(date -u +%FT%TZ)] nothing new"; return 0; }
  git commit -q -m "原始資料歸檔：$PFX（$(date -u +%FT%TZ)）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01MubgqryqvfE5urfHU21Pvd" -- "$OUT" || return 1
  for i in 2 4 8 16; do git push -q -u origin "$(git branch --show-current)" && break; sleep $i; done
  echo "[$(date -u +%FT%TZ)] archived and pushed $(git log --oneline -1)"
}
while true; do
  if [ -e "$STOP_FILE" ]; then round; echo "[$(date -u +%FT%TZ)] final archive done"; exit 0; fi
  round
  for _ in $(seq 1 $((INTERVAL / 30))); do [ -e "$STOP_FILE" ] && break; sleep 30; done
done
