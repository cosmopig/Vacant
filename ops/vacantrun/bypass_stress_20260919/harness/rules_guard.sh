#!/usr/bin/env bash
# 改網路規則的**三層保險**（照抄 V3 那份的作法，加上 nat 與 v6）。
#
#   1. 只打新建的 uid（1001）。規則從來不碰 uid 0／1000 ⇒ ssh 與 proxy 不可能被鎖住。
#   2. root 心跳 watchdog：HOLD 檔超過 MAXAGE 沒被摸過就自動拆。
#      這個 session 死掉 ⇒ 機器不會停在被改過的狀態。
#   3. 全量快照 ＋ 收工後**逐行比對**還原。還原本身要被驗證，不是宣稱。
#
# 用法：
#   rules_guard.sh snapshot     # 收工前先做
#   rules_guard.sh watchdog &   # root，背景
#   rules_guard.sh verify       # 收工後：跟快照逐行比
set -uo pipefail
R=/var/tmp/vbypass
CMD="${1:?snapshot|watchdog|verify}"
MAXAGE="${2:-420}"

dump() {   # 全量：filter/nat/mangle × v4/v6
  for t in filter nat mangle; do
    echo "### iptables -t $t -S"; sudo -n iptables  -t "$t" -S 2>&1
    echo "### ip6tables -t $t -S"; sudo -n ip6tables -t "$t" -S 2>&1
  done
}

case "$CMD" in
snapshot)
  mkdir -p "$R/out"
  dump > "$R/out/rules_before.txt"
  wc -l "$R/out/rules_before.txt"
  ;;
verify)
  dump > "$R/out/rules_after.txt"
  if diff -u "$R/out/rules_before.txt" "$R/out/rules_after.txt" > "$R/out/rules_diff.txt"; then
    echo "還原已驗證：全量規則（filter/nat/mangle × v4/v6）與快照**逐行相同**。"
    exit 0
  else
    echo "⚠ 還原沒回到起點——差異如下（也在 $R/out/rules_diff.txt）："
    cat "$R/out/rules_diff.txt"
    exit 9
  fi
  ;;
watchdog)
  [ "$(id -u)" = "0" ] || { echo "watchdog 要 root。停。" >&2; exit 3; }
  log() { echo "$(date -Is) $*" >> "$R/logs/watchdog.log"; }
  log "watchdog start maxage=$MAXAGE"
  while true; do
    sleep 20
    [ -f "$R/STOP_WATCHDOG" ] && { log "STOP_WATCHDOG ⇒ 退出，不動規則"; exit 0; }
    [ -f "$R/HOLD" ] || { log "HOLD 不存在 ⇒ 還原"; break; }
    age=$(( $(date +%s) - $(stat -c %Y "$R/HOLD") ))
    [ "$age" -gt "$MAXAGE" ] && { log "HOLD 過期 ${age}s ⇒ 還原"; break; }
  done
  bash "$R/bin/egress_gauge.sh"  --undo --uid 1001 >> "$R/logs/watchdog.log" 2>&1
  bash "$R/bin/dns_redirect.sh" --undo --uid 1001 >> "$R/logs/watchdog.log" 2>&1
  log "watchdog 還原完畢"
  ;;
*) echo "unknown: $CMD" >&2; exit 2 ;;
esac
