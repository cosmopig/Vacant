#!/usr/bin/env bash
# 20 格 ＝ 10 題（R534 B 層全取）× 2 個 agent（pi / Claude Code）× 臂 V × 1 次。
#
# 兩條 lane **同時**跑（pi 一條、Claude Code 一條）⇒ 同時最多 2 串打 1003
# （`lms ps` 實測 parallel=4，沒有超過封頂）。
# ⚠ 這與上一輪（嚴格序列、同時只有一格）**不同**，所以逐格牆鐘不是同一個
#   量測條件；判決欄位不受影響，但 `agent_wall_s` 的跨輪比較要帶這一句。
set -u
ROOT=/var/tmp/vacant_pbgate2
TASKS="lcb_3522 lcb_3583 lcb_3584 lcb_3637 lcb_3654 lcb_3681 lcb_3686 lcb_3700 lcb_3764 lcb_3794"
lane() {
  local agent="$1"
  for tid in $TASKS; do
    PB_AGENT="$agent" bash "$ROOT/pbgate2_cell.sh" "$tid" V
  done
  echo "=== LANE DONE $agent $(date -u +%FT%TZ) ==="
}
lane "$1"
