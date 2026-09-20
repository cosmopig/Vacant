#!/usr/bin/env bash
# 把 `pi_tty_cell.sh` 的格子排成矩陣，用 N 條 lane 跑。
#
# ⚠ **每條 lane 混臂、也混重複次序**（同 abpi §二）：後端會隨時間漂，
#   臂與時間綁在一起就分不開「呼叫形態造成的差」與「跑得比較晚造成的差」。
# ⚠ **1003 only**。1004 的 4 串是別人的實驗在用。lane 數預設 3（留一串餘裕）。
# ⚠ **磁碟擋門**：低於 1500MB 整條 lane 停下來講話（那台只有 38G）。
set -u
ROOT=${TTY_ROOT:-/var/tmp/vacant_tty_20260920}
CELL=$ROOT/repo/ops/vacantrun/pi_tty_20260920/pi_tty_cell.sh
LANES=${TTY_LANES:-3}
TASKS=${TTY_TASKS:-"lcb_3522 lcb_3584 lcb_3649 lcb_3715 lcb_3789"}
REPS=${TTY_REPS:-2}
ARMS=${TTY_ARMS:-"PRT PTP INT"}
mkdir -p "$ROOT/logs"

# ── 格子清單。順序刻意交錯：rep 外層、task 中層、arm 內層 ────────────
LIST=$ROOT/cells.txt
: > "$LIST"
for r in $(seq 1 "$REPS"); do
  for t in $TASKS; do
    for a in $ARMS; do echo "$t $a $r" >> "$LIST"; done
  done
done
N=$(wc -l < "$LIST")
echo "共 $N 格，$LANES 條 lane"

run_lane() {
  local lane="$1" i=0
  while IFS=' ' read -r t a r; do
    i=$((i+1))
    [ $(( (i-1) % LANES )) -eq "$lane" ] || continue
    free=$(df -Pm / | awk 'NR==2{print $4}')
    if [ "$free" -lt 1500 ]; then
      echo "LANE$lane 磁碟只剩 ${free}MB（<1500）⇒ 停。" >&2
      return 9
    fi
    bash "$CELL" "$t" "$a" "$r" >> "$ROOT/logs/lane$lane.log" 2>&1
  done < "$LIST"
}

for l in $(seq 0 $((LANES-1))); do
  run_lane "$l" &
done
wait
echo "矩陣跑完 $(date -u +%FT%T.%NZ)"
