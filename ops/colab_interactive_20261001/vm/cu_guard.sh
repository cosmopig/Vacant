#!/usr/bin/env bash
# 運算單位護欄（Mac，常駐迴圈）：每 INT 秒看一次 `colab usage`；餘額低於門檻 ⇒ 在 VM 上放停止檔（驅動不再開新題，已開始的跑完）。
# 用法：cu_guard.sh <session> <門檻 CU> [間隔秒數，預設 600]   紀錄：stdout（一行一次）
# 預註冊第五節：「餘額低於 25 CU 就放停止檔」。Mac 睡著時這支停住——VM 那邊還有驅動自己的時間上限兜底。
set -u
S=$1; TH=$2; INT=${3:-600}
COLAB=${COLAB:-$HOME/.local/bin/colab}
while true; do
  bal=$("$COLAB" usage 2>/dev/null | sed -n 's/.*Current balance: \([0-9.]*\).*/\1/p')
  echo "$(date -u +%FT%TZ) balance=${bal:-?}"
  if [ -n "$bal" ] && python3 -c "import sys; sys.exit(0 if float('$bal') < float('$TH') else 1)"; then
    printf 'echo "CU guard: balance %s < %s at $(date -u +%%FT%%TZ)" > /srv/eval/STOP\nexit\n' "$bal" "$TH" | "$COLAB" console -s "$S" >/dev/null 2>&1 &
    p=$!; sleep 40; kill $p 2>/dev/null
    echo "$(date -u +%FT%TZ) STOP 已放（餘額 $bal < ${TH}）"; exit 0
  fi
  sleep "$INT"
done
