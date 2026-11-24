#!/bin/bash
# Colab 批次守門（2026-11-22，vacant-hope 核可的條件）：keepalive 意外結束、而 VM 還在時，重新起同一份 keepalive。
# 用法：colab_guard.sh <state.json> <keepalive_unit_name>
# 只在三個條件同時成立時動作：
#   1) keepalive unit 不是 active；
#   2) 伺服器 assignment 清單裡還有這個 session（`colab sessions` 成功結束、而且列出它；連續兩次才算；查詢失敗＝不動作）；
#   3) 結果還沒取回（state.json 沒有 fetched_utc）。
# 動作只有一個：重新起同一份、沒改過的 colab_keepalive_fetch.sh（先確認沒有第二個 keepalive 在跑）。
# 每次判斷與動作都寫日誌。乾跑：GUARD_DRY=1，並可用 GUARD_UNIT_ACTIVE_CMD／GUARD_SESSIONS_CMD／GUARD_PGREP_CMD 換成假指令。
set -u
ST=$1; UNIT=$2
DIR=$(dirname "$ST"); LOG=${GUARD_LOG:-$DIR/guard.log}
S=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['session'])" "$ST")
CB=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('colab_bin') or 'colab')" "$ST")
say() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }
unit_active() { ${GUARD_UNIT_ACTIVE_CMD:-systemctl --user is-active -q} "$1"; }
sessions_list() { if [ -n "${GUARD_SESSIONS_CMD:-}" ]; then $GUARD_SESSIONS_CMD; else timeout 60 "$CB" sessions; fi; }
KA=${GUARD_KEEPALIVE:-$HOME/dev/ops/colab_keepalive_fetch3.sh}
other_keepalive() { ${GUARD_PGREP_CMD:-pgrep -f} "colab_keepalive_fetch[0-9]*\\.sh $ST" >/dev/null; }
fetched() { python3 -c "import json,sys;sys.exit(0 if json.load(open(sys.argv[1])).get('fetched_utc') else 1)" "$ST"; }
assigned_once() { local out rc; out=$(sessions_list 2>/dev/null); rc=$?; [ $rc -eq 0 ] || return 2; echo "$out" | grep -q "\[$S\]"; }
n_restart=0
say "GUARD_START session=$S unit=$UNIT keepalive=$KA dry=${GUARD_DRY:-0}"
while true; do
  if fetched; then say "results fetched; guard exits"; exit 0; fi
  if unit_active "$UNIT"; then say "unit $UNIT active; ok"; sleep ${GUARD_INTERVAL:-300}; [ "${GUARD_ONCE:-0}" = 1 ] && exit 0; continue; fi
  say "keepalive unit $UNIT is NOT active; checking assignment"
  assigned_once; a1=$?
  sleep ${GUARD_RECHECK:-30}
  assigned_once; a2=$?
  if [ $a1 -eq 2 ] || [ $a2 -eq 2 ]; then say "assignment query failed (rc a1=$a1 a2=$a2); no action"
  elif [ $a1 -ne 0 ] || [ $a2 -ne 0 ]; then say "session not listed (a1=$a1 a2=$a2); VM likely gone; no action, guard exits"; exit 3
  elif other_keepalive; then say "another keepalive for this state is already running; no action"
  else
    n_restart=$((n_restart+1)); NEW="${UNIT%%-ka*}-ka$n_restart"
    if [ "${GUARD_DRY:-0}" = 1 ]; then say "DRY: would restart keepalive as unit $NEW"
    else
      systemd-run --user --unit="$NEW" -p KillMode=process --setenv=PATH="$PATH" \
        "$KA" "$ST" >> "$LOG" 2>&1 && say "RESTARTED keepalive as unit $NEW" || say "restart FAILED"
    fi
    UNIT=$NEW
  fi
  [ "${GUARD_ONCE:-0}" = 1 ] && exit 0
  sleep ${GUARD_INTERVAL:-300}
done
