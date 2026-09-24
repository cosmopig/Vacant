#!/usr/bin/env bash
# 一個後端一個 worker：等自己那台的 pilot 收完 → 從共用佇列領題（mkdir 原子鎖）→ 跑完一題再領下一題。
# 截止前 25 分鐘起不再領新題（預註冊 §七）。
set -u
source /var/tmp/vacant_piext_20260924/bcb_tools/bcb_common.sh
mkdir -p $OUT; exec >> $OUT/worker.log 2>&1
deadline=$(cat $RUN/deadline_epoch); stop_claim=$((deadline - 25*60))
# 同一台的 pilot（R534，描述性）在發射時被叫停（bcb_launch.sh 殺掉它的迴圈，不殺正在跑的格子）。
# 這裡等那台**還在跑的 pilot 格子**自然結束，再開始領題——同一台不會有兩批同時搶。
pilot_busy() {
  for pid in $(pgrep -f "pilot_tools/cell.sh" 2>/dev/null); do
    tr '\0' '\n' < /proc/$pid/environ 2>/dev/null | grep -qx "PILOT=$P" && return 0
  done
  return 1
}
echo "$(date -u +%FT%TZ) worker $BACKEND 起；等 pilot_$BACKEND 手上的格子跑完"
while pilot_busy; do sleep 30; done
grep -q ALLDONE $P/logs/progress.log 2>/dev/null || echo "ALLDONE（$(date -u +%FT%TZ) BCB 發射，pilot 提前停止）" >> $P/logs/progress.log
echo "$(date -u +%FT%TZ) pilot 已停，開始領題"
idx=0
while read -r tid; do
  [ -z "$tid" ] && continue
  now=$(date +%s)
  if [ $now -ge $stop_claim ]; then echo "$(date -u +%FT%TZ) 到了停止領題時間"; break; fi
  if mkdir $RUN/claims/$tid 2>/dev/null; then
    echo "$BACKEND" > $RUN/claims/$tid/backend
    echo "$(date -u +%FT%TZ) 領 $tid"
    bash $T/bcb_task.sh $tid $idx
    idx=$((idx+1))
  fi
done < $RUN/queue.txt
date -u +%FT%TZ > $OUT/WORKER_DONE
echo "$(date -u +%FT%TZ) worker $BACKEND 收工"
# 最後一個收工的 worker 負責跑分析（預註冊：只在全部收尾後跑一次）
if [ -f $RUN/1004/WORKER_DONE ] && [ -f $RUN/1003/WORKER_DONE ] && [ -f $RUN/gemini/WORKER_DONE ] \
   && mkdir $RUN/analysis_lock 2>/dev/null; then
  $VENV/bin/python $T/bcb_analyze.py $RUN > $RUN/analysis.stdout 2> $RUN/analysis.stderr
  echo "$(date -u +%FT%TZ) 分析完成 rc=$?"
fi
