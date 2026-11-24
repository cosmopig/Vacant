#!/bin/bash
# 孤兒行程看門狗（2026-11-22，vacant-hope 要求）：每 10 分鐘掃一次批次留下的脫離行程。
# 只砍「確定是孤兒」的：父行程是 init(1) 或 systemd --user，而且
#   (a) 工作目錄已被刪除（…(deleted)），或
#   (b) 工作目錄在某一格的目錄底下（redo_runs*/…/cells/<task>/rN/<arm>/…），而該格已經有 cell.json（格子已結束）。
# 每次發現都寫日誌（pid、跑了多久、指令、工作目錄、判定理由）；結案時用來在已知限制裡記一筆。
set -u
LOG=$HOME/dev/ops/orphan_watch.log
UPID=$(pgrep -u "$(id -u)" -x systemd | head -1); UPID=${UPID:-0}
say() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }
say "START (systemd --user pid=$UPID)"
while true; do
  for p in $(ps -eo pid=,ppid= | awk -v u="$UPID" '($2==1 || $2==u){print $1}'); do
    cwd=$(readlink /proc/$p/cwd 2>/dev/null) || continue
    cmd=$(tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | cut -c1-160)
    case "$cmd" in *python*unittest*|*pytest*|*jest*|*node*|*npm*test*|*"pi "*|*vacant*) ;; *) continue;; esac
    why=""
    case "$cwd" in
      *"(deleted)") case "$cwd" in *tmp_redo*|*redo_runs*|*vacant-work*|*/tmp/*) why="cwd deleted";; esac;;
      *redo_runs*/cells/*)
        cell=$(echo "$cwd" | grep -oE '.*/cells/[^/]+/r[0-9]+/[^/]+' | head -1)
        [ -n "$cell" ] && [ -f "$cell/cell.json" ] && why="cell finished ($cell/cell.json exists)";;
    esac
    [ -z "$why" ] && continue
    et=$(ps -o etime= -p $p | tr -d ' ')
    say "ORPHAN pid=$p etime=$et why=[$why] cwd=$cwd cmd=$cmd"
    if [ "${ORPHAN_DRY:-0}" = 1 ]; then say "DRY: would kill pid=$p"; else kill "$p" 2>/dev/null && say "killed pid=$p"; fi
  done
  [ "${ORPHAN_ONCE:-0}" = 1 ] && exit 0
  sleep 600
done
