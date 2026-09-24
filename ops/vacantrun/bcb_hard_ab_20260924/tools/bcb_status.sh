#!/usr/bin/env bash
# 進度（只看計數與異常，不看結果——預註冊 §七）
R=/var/tmp/vacant_piext_20260924; RUN=$R/bcb_run
[ -f $RUN/launch_record.json ] || { echo "還沒發射"; exit 0; }
echo "截止：$(date -d @$(cat $RUN/deadline_epoch) '+%F %T %Z')；現在 $(date '+%T')；已領題 $(ls $RUN/claims | wc -l)/$(wc -l < $RUN/queue.txt)"
for b in 1004 1003 gemini; do
  d=$RUN/$b; n=$(ls $d/tasks 2>/dev/null | wc -l); c=$(ls $d/cells 2>/dev/null | wc -l)
  st=$([ -f $d/WORKER_DONE ] && echo 收工 || (grep -q "開始領題" $d/worker.log 2>/dev/null && echo 在跑 || echo 等pilot))
  echo "  $b：$st；完成題 $n；格子 $c；最後一行：$(tail -1 $d/worker.log 2>/dev/null)"
done
[ -f $RUN/report.md ] && echo "報告：$RUN/report.md"
