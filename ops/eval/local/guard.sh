#!/bin/bash
# 批次的保險絲（2026-09-27；RUNLOG §17：容器重啟時 dockerd 與代理停了、驅動還活著，28 秒內把 27 題標成開始過、54 格秒敗）。
# 每 5 秒看 dockerd 與代理 :18900；連續兩次有一個不在 ⇒ 依序停啟動檔、驅動（和交接文件 8.5 同一個順序），寫一行到 guard.log 後結束。
# 在跑的跑不動（它們會自己失敗或跑完）；重開要人（或 agent）先把 dockerd、代理接回來。
# 用法：guard.sh <jobs 目錄>（啟動檔與驅動的命令列都含這個目錄）
set -uo pipefail
JOBS=$1; bad=0
while true; do
  if docker info >/dev/null 2>&1 && curl -s -m 5 -o /dev/null http://127.0.0.1:18900/; then bad=0; else bad=$((bad + 1)); fi
  if [ "$bad" -ge 2 ]; then
    for p in $(pgrep -f "[l]aunch_.*\.sh .*$JOBS"); do kill "$p"; done
    sleep 1
    for p in $(pgrep -f "[r]un_pairs\.py .*--jobs $JOBS "); do kill "$p"; done
    echo "[$(date -u +%FT%TZ)] dockerd or proxy down twice in a row: stopped launcher and driver" >> "$JOBS/guard.log"
    exit 0
  fi
  [ -e "$JOBS/DONE" ] && exit 0
  sleep 5
done
