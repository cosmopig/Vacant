#!/bin/bash
# 用法：colab_keepalive_fetch.sh <state.json>
# 每 4 分鐘碰一下 Colab kernel（閒置 25–30 分鐘會被回收），每 10 分鐘 poll 一次；DONE 就 fetch（驗 sha256 後才 stop）。
# session 不見了就記一筆並結束（不自動重開，免得空燒單元）。
ST=$1; cd $HOME/dev/wt/nonpy
CB=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('colab_bin') or 'colab')" "$ST")
S=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['session'])" "$ST")
LOG=$(dirname "$ST")/keepalive.log
n=0
while true; do
  # 2026-11-22：一次沒看到不算——連續 3 次（間隔 60 秒）`"$CB" sessions` 成功結束卻都沒列出，才判定 session 消失；
  # 查詢本身失敗（非 0）一律不算數（JS 確認批 11/21 就是被一次暫時性失敗誤判而遺失）。
  miss=0; for _i in 1 2 3; do out=$(timeout 60 "$CB" sessions 2>/dev/null); rc=$?
    if [ $rc -eq 0 ] && ! echo "$out" | grep -q "\[$S\]"; then miss=$((miss+1)); else break; fi; [ $_i -lt 3 ] && sleep 60; done
  if [ $miss -ge 3 ]; then echo "$(date -u +%FT%TZ) SESSION_GONE $S (3 consecutive misses)" >> $LOG; exit 3; fi
  echo 'print("keepalive")' | timeout 120 "$CB" exec -s "$S" >/dev/null 2>&1 || echo "$(date -u +%FT%TZ) exec failed" >> $LOG
  n=$((n+1))
  if [ $((n % 3)) = 0 ]; then
    o=$(timeout 240 bash ops/redo/colab/poll_batch.sh "$ST" 2>&1)
    echo "$(date -u +%FT%TZ) $(echo "$o" | grep -E '^VM_READY|^STATUS|^DONE' | tr '\n' ' ')" >> $LOG
    if echo "$o" | grep -q "DONE     : YES"; then
      timeout 1800 bash ops/redo/colab/fetch_batch.sh "$ST" >> $LOG 2>&1 && { echo "$(date -u +%FT%TZ) FETCHED_AND_STOPPED" >> $LOG; exit 0; }
      echo "$(date -u +%FT%TZ) FETCH_FAILED (session left running for manual check)" >> $LOG; exit 4
    fi
  fi
  sleep 240
done
