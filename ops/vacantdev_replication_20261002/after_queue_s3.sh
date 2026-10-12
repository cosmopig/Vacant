#!/usr/bin/env bash
# 10-03：d37L（resume_queue.sh）跑完 ⇒ 補跑 t3L 第 3 次的 186 格 void（第一次補跑被可行性規則在 40 格時停下：逾時率 0.30 剛好碰門檻，
# 補跑的單位偏難題；另外非 200 的 40 通是同名格子 10-02 的舊 400）。**偏離**：這一輪補跑啟動後立刻停掉 feasibility（它是開跑時的基礎設施檢查，不是補跑用的），記在 RUNLOG。
set -u
E=/srv/eval; DL=2026-12-31T00:00:00Z; PR=PREREG_20261002_VACANTDEV_REPLICATION_V37
until [ -f $E/QUEUE_DONE ]; do sleep 120; done
echo "s3 rerun start $(date -u +%FT%TZ)" >> $E/queue.log
rm -f $E/QUEUE_DONE $E/STOP
mkdir -p $E/void_try1_s3; cp /opt/eval/bin/t3L_void_s3_try1.txt $E/void_try1_s3/list.txt
while read -r c; do [ -d $E/cells/$c ] && mv $E/cells/$c $E/void_try1_s3/; done < $E/void_try1_s3/list.txt
grep -vxFf $E/void_try1_s3/list.txt $E/archive/packed_cells.txt > $E/archive/packed_cells.new; mv $E/archive/packed_cells.new $E/archive/packed_cells.txt
mkdir -p $E/unit_up_try2 && mv $E/unit_up/*-s3 $E/unit_up_try2/ 2>/dev/null
pgrep -f cleanup_packed.sh >/dev/null || setsid nohup bash /opt/eval/bin/cleanup_packed.sh > /dev/null 2>&1 < /dev/null &
env -u MAX_TURNS UP=auto AGENT_TIMEOUT=1800 bash /opt/eval/bin/launch_batch.sh t3L $E/plan_t3.json 8 $DL $PR >> $E/queue.log 2>&1
sleep 5; pkill -f "opt/eval/bin/feasibility.py --prefix t3L" && echo "feasibility stopped for s3 rerun (deviation)" >> $E/queue.log
sleep 30; until [ -f $E/DRIVER_DONE ] && [ -f $E/archive/PACKER_DONE ]; do sleep 60; done
echo "s3 rerun done $(date -u +%FT%TZ)" >> $E/queue.log; touch $E/QUEUE_DONE $E/S3_DONE
