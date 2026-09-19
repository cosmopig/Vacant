#!/usr/bin/env bash
# R536 公開題庫閘門矩陣：10 題（R534 B 層）× 2 臂 × 1 次 ＝ 20 格，序列跑。
# 同一台（1004）、同一個模型、同一個 agent、同一天、同一組參數。
set -u
ROOT=/var/tmp/vacant_pbgate
cd "$ROOT" || exit 2
TASKS="lcb_3522 lcb_3583 lcb_3584 lcb_3637 lcb_3654 lcb_3681 lcb_3686 lcb_3700 lcb_3764 lcb_3794"
echo "#### 負控制：收據驗章器 selftest（發射前）"
cd "$ROOT/repo" && /usr/bin/python3 -m vacant.vrun.verify_receipts --selftest; cd "$ROOT"
echo "#### df 派工前"; df -h / | tail -1
echo "#### 版本"
export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:/home/user1/.local/bin:$PATH
printf "pi        "; pi --version 2>&1 | head -1
printf "python3   "; /usr/bin/python3 -V
echo $$ > "$ROOT/matrix.pid"
echo "#### LAUNCH $(date -u +%FT%TZ)  driver_pid=$$"
for arm in N V; do
  for t in $TASKS; do
    bash "$ROOT/pbgate_cell.sh" "$t" "$arm"
  done
done
echo "#### df 收工後"; df -h / | tail -1
echo "#### ALL DONE $(date -u +%FT%TZ)"
