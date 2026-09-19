#!/usr/bin/env bash
# `dnslog.py` 的那一條 nat 規則。**只打被量的那個 uid**，機器其餘部分不受影響。
# 分成獨立一支（不併進 egress_gauge.sh）是為了讓兩個量具的失敗互相隔離：
# DNS 記錄器掛掉不該讓封包計數器跟著不能用。
set -uo pipefail
UID_AGENT=""; DNSPORT=5353; UNDO=0
while [ $# -gt 0 ]; do
  case "$1" in
    --uid)      UID_AGENT="$2"; shift 2 ;;
    --dns-port) DNSPORT="$2";   shift 2 ;;
    --undo)     UNDO=1;         shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
[ "$(id -u)" = "0" ] || { echo "需要 root。停。" >&2; exit 3; }
case "$UID_AGENT" in ''|*[!0-9]*) echo "--uid 必須是數字。停。" >&2; exit 2 ;; esac
if [ "$UID_AGENT" = "0" ] || [ "$UID_AGENT" = "1000" ]; then
  echo "不要導 root／user1 的 DNS。停。" >&2; exit 2
fi

MATCH=(-m owner --uid-owner "$UID_AGENT" -p udp --dport 53 -j REDIRECT --to-ports "$DNSPORT")
if [ "$UNDO" = "1" ]; then
  for i in 1 2 3 4 5; do
    iptables -t nat -D OUTPUT "${MATCH[@]}" 2>/dev/null || break
  done
  left=$(iptables -t nat -S OUTPUT | grep -c -- "--uid-owner $UID_AGENT" || true)
  echo "DNS 導流已拆，殘留=$left（要是 0）"
  [ "$left" = "0" ] || exit 4
else
  iptables -t nat -I OUTPUT 1 "${MATCH[@]}"
  echo "DNS 導流已上：uid=$UID_AGENT 的 53/udp → 127.0.0.1:$DNSPORT"
fi
