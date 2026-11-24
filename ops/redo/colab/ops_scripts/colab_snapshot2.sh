#!/bin/bash
# Colab 批次每小時唯讀快照（2026-11-22，vacant-hope 核可）：把 VM 上目前的 run root（cells、runner.log、REPORT…）打包拉回本機
# <state 目錄>/snapshots/，不停機、不動 runner。用途：VM 萬一沒了，可在同規格新 VM 上用同計畫、同 root 續跑（已完成的格不重跑）。
# 只保留最新 3 份。結果取回（fetched_utc）後自動結束。照 state.json 的 colab_bin 選帳號。
# v2.2（11/24）：排除工作區副本、接受 tar rc 1、exec 帶 --timeout；舊版 colab_snapshot2_v21.sh。
# v2.1（11/22 第五次 review）：失敗後 10 分鐘內再試，最多再試 2 次（confirm3 曾因一次連線失敗留下約兩小時空窗）；
#   批次剛開始的第一個小時多拍一份（啟動後約 30 分鐘一份，之後每 interval 一份）。舊版留在 colab_snapshot2_v1.sh。
# 用法：colab_snapshot2.sh <state.json> [interval_s]
set -u
ST=$1; IV=${2:-3600}; RETRY_WAIT=${SNAP_RETRY_WAIT:-600}; FIRST=${SNAP_FIRST_EXTRA:-1800}
CB=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('colab_bin') or 'colab')" "$ST")
DIR=$(dirname "$ST"); OUT=$DIR/snapshots; LOG=$DIR/snapshot.log; mkdir -p "$OUT"
S=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['session'])" "$ST")
say() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }
fetched() { python3 -c "import json,sys;sys.exit(0 if json.load(open(sys.argv[1])).get('fetched_utc') else 1)" "$ST"; }
snap_once() {
  local TS SHA
  TS=$(date -u +%Y%m%dT%H%M%SZ)
  # v2.2（11/24，W3-5 JS 重跑 VOID 的根因 3）：排除工作區副本（node_modules 等，與 vm_run_batch.sh 同一份清單），
  # tar 回 1（file changed as we read it）照常接受，`colab exec` 帶 --timeout（之前 30 秒沒輸出就放棄）。
  printf 'import subprocess\nr=subprocess.run("tar czf /content/redo_snapshot.tar.gz -C /srv/redo --exclude=node_modules --exclude=\x27attempt_*/w\x27 --exclude=\x27snap-*\x27 --exclude=\x27start-copy-*\x27 --exclude=\x27start-snap-*\x27 --exclude=\x27bkp-*\x27 --exclude=__pycache__ run; rc=$?; [ $rc -le 1 ] && sha256sum /content/redo_snapshot.tar.gz", shell=True, capture_output=True, text=True)\nprint("SNAP_RC", r.returncode); print(r.stdout.strip()); print(r.stderr[-300:])\n' \
    | timeout 1900 "$CB" exec -s "$S" --timeout 1800 > "$OUT/.exec_$TS.txt" 2>&1
  if grep -q 'SNAP_RC 0' "$OUT/.exec_$TS.txt"; then
    SHA=$(grep -oE '^[0-9a-f]{64}' "$OUT/.exec_$TS.txt" | head -1)
    if timeout 900 "$CB" download -s "$S" /content/redo_snapshot.tar.gz "$OUT/snap_$TS.tar.gz" >> "$LOG" 2>&1 \
       && [ "$(sha256sum "$OUT/snap_$TS.tar.gz" | cut -c1-64)" = "$SHA" ]; then
      say "SNAPSHOT_OK $OUT/snap_$TS.tar.gz sha256=$SHA cells=$(tar tzf "$OUT/snap_$TS.tar.gz" | grep -c 'cell.json$')"
      ls -1t "$OUT"/snap_*.tar.gz | tail -n +4 | xargs -r rm -f
      rm -f "$OUT/.exec_$TS.txt"; return 0
    fi
    say "SNAPSHOT_DOWNLOAD_FAILED"; rm -f "$OUT/snap_$TS.tar.gz"
  else say "SNAPSHOT_TAR_FAILED: $(tail -2 "$OUT/.exec_$TS.txt" | tr '\n' ' ')"; fi
  rm -f "$OUT/.exec_$TS.txt"; return 1
}
snap_with_retry() {
  local i
  for i in 0 1 2; do
    fetched && return 0
    [ $i -gt 0 ] && { say "retry $i/2 in ${RETRY_WAIT}s"; sleep "$RETRY_WAIT"; fetched && return 0; }
    snap_once && return 0
  done
  say "SNAPSHOT_GAVE_UP after 2 retries (next regular snapshot in ${IV}s)"
}
START=$(date +%s); extra_done=0
while true; do
  fetched && { say "fetched; snapshot loop exits"; exit 0; }
  snap_with_retry
  if [ $extra_done = 0 ] && [ $(( $(date +%s) - START )) -lt "$FIRST" ]; then
    extra_done=1; sleep $(( FIRST - ($(date +%s) - START) )); continue   # 第一個小時多拍一份
  fi
  extra_done=1
  sleep "$IV"
done
