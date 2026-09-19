#!/usr/bin/env bash
# 一條 lane ＝ 一個 agent 序列跑完 10 題（R534 B 層全取）。三條 lane 同時跑
# ⇒ 同時最多 3 串打 1004（吞吐 4 串封頂，沒有超過）。
# ⚠ 與 pbgate2 同樣是三條 lane 並行 ⇒ 牆鐘的量測條件與 pbgate2 相同、
#   與 pbgate（2026-09-19 那批嚴格序列）不同。
set -u
ROOT=/var/tmp/vacant_pbgate3
TASKS="lcb_3522 lcb_3583 lcb_3584 lcb_3637 lcb_3654 lcb_3681 lcb_3686 lcb_3700 lcb_3764 lcb_3794"
lane() {
  local agent="$1"
  for tid in $TASKS; do
    PB_AGENT="$agent" bash "$ROOT/pbgate3_cell.sh" "$tid" V
  done
  echo "=== LANE DONE $agent $(date -u +%FT%TZ) ==="
}
lane "$1"
