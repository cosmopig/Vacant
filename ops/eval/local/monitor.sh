#!/bin/bash
# 批次監測（2026-09-27）：每分鐘看一次；出現問題就印一行、結束（喚醒 agent）。不讀任何評分的值。
# 問題＝沒有結果的跑變多、磁碟 < 2.5 GB、代理 :18900 沒回應、dockerd 沒了、驅動死了但沒有寫完成旗標。
# 用法：monitor.sh <jobs> <驅動行程的樣式（pgrep -f）> <完成旗標檔>
set -uo pipefail
JOBS=$1; PAT=$2; DONE_FILE=$3
cnt() { if [ -f "$JOBS/progress.jsonl" ]; then grep -c '"has_result": false' "$JOBS/progress.jsonl"; else echo 0; fi; }
b0=$(cnt)
while true; do
  [ -e "$DONE_FILE" ] && { echo "DONE: batch finished at $(date -u +%H:%M)"; exit 0; }
  b=$(cnt); av=$(df -k "$JOBS" | awk 'NR==2{print $4}')
  [ "$b" -gt "$b0" ] && { echo "PROBLEM: runs without result rose to $b at $(date -u +%H:%M)"; exit 0; }
  [ "$av" -lt 2621440 ] && { echo "PROBLEM: disk low ($av KB) at $(date -u +%H:%M)"; exit 0; }
  curl -s -m 10 -o /dev/null http://127.0.0.1:18900/ || { echo "PROBLEM: proxy :18900 not answering at $(date -u +%H:%M)"; exit 0; }
  pgrep -x dockerd >/dev/null || { echo "PROBLEM: dockerd gone at $(date -u +%H:%M)"; exit 0; }
  pgrep -f "$PAT" >/dev/null || { sleep 5; [ -e "$DONE_FILE" ] || { echo "PROBLEM: driver gone without done flag at $(date -u +%H:%M)"; exit 0; }; }
  sleep 60
done
