#!/usr/bin/env bash
# 排隊（root，setsid）：t3L（任務導向 94 題 × A／C37 × 3）跑完、打包完 ⇒ d37L（DABstep 79 題 × A／C37／C37R × 3，15 回合）。
set -u
E=/srv/eval; DL=2026-12-31T00:00:00Z; PR=PREREG_20261002_VACANTDEV_REPLICATION_V37
wait_done() { until [ -f $E/DRIVER_DONE ] && [ -f $E/archive/PACKER_DONE ]; do sleep 60; done; }
echo "t3L start $(date -u +%FT%TZ)" >> $E/queue.log
env -u MAX_TURNS UP=auto AGENT_TIMEOUT=1800 bash /opt/eval/bin/launch_batch.sh t3L $E/plan_t3.json 8 $DL $PR >> $E/queue.log 2>&1
sleep 30; wait_done
echo "d37L start $(date -u +%FT%TZ)" >> $E/queue.log
MAX_TURNS=15 UP=auto AGENT_TIMEOUT=1800 bash /opt/eval/bin/launch_batch.sh d37L $E/plan_d37.json 8 $DL $PR >> $E/queue.log 2>&1
sleep 30; wait_done
echo "ALL_DONE $(date -u +%FT%TZ)" >> $E/queue.log; touch $E/QUEUE_DONE
