#!/usr/bin/env bash
# 10-04（root，setsid）：不限時間的兩批，依序。人類：「派一樣的題目，然後不限時間」。
# 每格安全網 AGENT_TIMEOUT=14400（4 小時；防原地打轉永遠佔位，撞到的照實列出）；兩批都不設回合上限（MAX_TURNS 空）。
set -u
E=/srv/eval; DL=2026-12-31T00:00:00Z; PR=PREREG_20261004_VACANTDEV_UNLIMITED_V37
wait_done() { until [ -f $E/DRIVER_DONE ] && [ -f $E/archive/PACKER_DONE ]; do sleep 60; done; }
rm -f $E/QUEUE_DONE $E/U_DONE $E/STOP
pgrep -f cleanup_packed.sh >/dev/null || setsid nohup bash /opt/eval/bin/cleanup_packed.sh > /dev/null 2>&1 < /dev/null &
cp /opt/eval/bin/plan_t3u.json /opt/eval/bin/plan_d37u.json $E/
echo "t3U start $(date -u +%FT%TZ)" >> $E/queue.log
env -u MAX_TURNS UP=auto AGENT_TIMEOUT=14400 bash /opt/eval/bin/launch_batch.sh t3U $E/plan_t3u.json 8 $DL $PR >> $E/queue.log 2>&1
sleep 30; wait_done
echo "d37U start $(date -u +%FT%TZ)" >> $E/queue.log
env -u MAX_TURNS UP=auto AGENT_TIMEOUT=14400 bash /opt/eval/bin/launch_batch.sh d37U $E/plan_d37u.json 8 $DL $PR >> $E/queue.log 2>&1
sleep 30; wait_done
echo "U ALL_DONE $(date -u +%FT%TZ)" >> $E/queue.log; touch $E/QUEUE_DONE $E/U_DONE
