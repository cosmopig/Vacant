#!/usr/bin/env bash
# 出網封鎖的**還原保險**：心跳檔 HOLD 超過 300 秒沒被摸過就自動 --undo。
# 目的不是保護 ssh（規則只打 uid=1001，不碰 uid 0/1000），而是保證
# 「這個 session 死掉 ⇒ 機器不會停在被改過的狀態」。
set -u
R=/var/tmp/v3egress
UID_AGENT="${1:?uid}"; PORT="${2:?port}"; MAXAGE="${3:-300}"
log() { echo "$(date -Is) $*" >> "$R/logs/watchdog.log"; }
log "watchdog start uid=$UID_AGENT port=$PORT maxage=$MAXAGE"
while true; do
  sleep 20
  if [ -f "$R/STOP_WATCHDOG" ]; then log "STOP_WATCHDOG 出現，退出（不動規則）"; exit 0; fi
  if [ ! -f "$R/HOLD" ]; then log "HOLD 不存在 ⇒ 還原"; break; fi
  age=$(( $(date +%s) - $(stat -c %Y "$R/HOLD") ))
  if [ "$age" -gt "$MAXAGE" ]; then log "HOLD 過期 ${age}s ⇒ 還原"; break; fi
done
bash "$R/ops/vacantrun/block_egress.sh" --uid "$UID_AGENT" --port "$PORT" --undo >> "$R/logs/watchdog.log" 2>&1
iptables -S OUTPUT >> "$R/logs/watchdog.log" 2>&1
log "watchdog 還原完畢"
