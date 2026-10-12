#!/usr/bin/env bash
# 10-03 續跑（root，setsid）：人類確認兩台都載好 gemma 之後才發射。
# 1) t3L 的 void 格（預註冊：最後照順序補跑一次）移到 /srv/eval/void_try1/，用同一個前綴與計畫再跑 ⇒ 驅動只跑沒有 DONE 的那些格
# 2) d37L 第一次（被可行性規則停在 51 格）整批移到 /srv/eval/aborted_d37L_try1/，不進分析，從頭重跑
set -u
E=/srv/eval; DL=2026-12-31T00:00:00Z; PR=PREREG_20261002_VACANTDEV_REPLICATION_V37
wait_done() { until [ -f $E/DRIVER_DONE ] && [ -f $E/archive/PACKER_DONE ]; do sleep 60; done; }
rm -f $E/STOP $E/QUEUE_DONE
mkdir -p $E/void_try1 $E/aborted_d37L_try1
# void 清單由本機用完整紀錄（chunk）算好傳上來（VM 上的格子已瘦身，少了 pi_stdout，判不準）
cp /opt/eval/bin/t3L_void_try1.txt $E/void_try1/list.txt
echo "t3L void to rerun: $(wc -l < $E/void_try1/list.txt)" >> $E/queue.log
while read -r c; do mv $E/cells/$c $E/void_try1/; done < $E/void_try1/list.txt
for d in $E/cells/d37L-*; do [ -d "$d" ] && mv "$d" $E/aborted_d37L_try1/; done
# 打包程式依名字跳過已打包的格子 ⇒ 補跑的同名格子與重跑的 d37L 要從 packed_cells.txt 拿掉；機器決定檔清掉（void 都是成對的，見 RUNLOG）；瘦身常駐重開
if [ -f $E/archive/packed_cells.txt ]; then grep -vxFf $E/void_try1/list.txt $E/archive/packed_cells.txt | grep -v '^d37L-' > $E/archive/packed_cells.new; mv $E/archive/packed_cells.new $E/archive/packed_cells.txt; fi
mkdir -p $E/unit_up_try1 && mv $E/unit_up/* $E/unit_up_try1/ 2>/dev/null
setsid nohup bash /opt/eval/bin/cleanup_packed.sh > /dev/null 2>&1 < /dev/null &
echo "resume t3L-void $(date -u +%FT%TZ)" >> $E/queue.log
env -u MAX_TURNS UP=auto AGENT_TIMEOUT=1800 bash /opt/eval/bin/launch_batch.sh t3L $E/plan_t3.json 8 $DL $PR >> $E/queue.log 2>&1
sleep 30; wait_done
echo "d37L restart $(date -u +%FT%TZ)" >> $E/queue.log
MAX_TURNS=15 UP=auto AGENT_TIMEOUT=1800 bash /opt/eval/bin/launch_batch.sh d37L $E/plan_d37.json 8 $DL $PR >> $E/queue.log 2>&1
sleep 30; wait_done
echo "ALL_DONE $(date -u +%FT%TZ)" >> $E/queue.log; touch $E/QUEUE_DONE
