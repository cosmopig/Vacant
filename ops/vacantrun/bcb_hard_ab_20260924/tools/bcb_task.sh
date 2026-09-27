#!/usr/bin/env bash
# 一題的四組：OFF／CH／GATE（本機同時跑；Gemini 依序、組序輪換），GATE 拒交（rc 20）就重抽，最多再 2 次。
# 用法：bcb_task.sh <task_dir_name> <題在佇列裡的序號>
set -u
source /var/tmp/vacant_piext_20260924/bcb_tools/bcb_common.sh
tid=$1; idx=${2:-0}
mkdir -p $OUT/tasks
if [ "$BACKEND" = gemini ]; then
  case $((idx % 3)) in 0) order="OFF CH GATE";; 1) order="CH GATE OFF";; 2) order="GATE OFF CH";; esac
  for a in $order; do bash $T/bcb_cell.sh $a $tid 1 >> $OUT/progress.log 2>&1; done
else
  for a in OFF CH GATE; do bash $T/bcb_cell.sh $a $tid 1 >> $OUT/progress.log 2>&1 & done
  wait
fi
att=1
while [ "$(cat $OUT/cells/GATE_${tid}_a${att}/rc 2>/dev/null)" = 20 ] && [ $att -lt 3 ]; do
  att=$((att+1)); bash $T/bcb_cell.sh GATE $tid $att >> $OUT/progress.log 2>&1
done
date -u +%FT%TZ > $OUT/tasks/$tid.done
