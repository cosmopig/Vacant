#!/usr/bin/env bash
# 開機自動啟動之前跑的那一關（`vacant-exhibit.service` 的 ExecStartPre）。
#
# 為什麼要它（DECISION_20260919_EXHIBIT_UNATTENDED.md §二）：
# `exhibit_boot.sh` 自己也會檢查幾件事，但它是**給站在鍵盤前面的人**寫的
# ——檢查失敗就把理由印在終端機上。開機自動啟動沒有那個人。
# 這一支的差別只有一個：**它把理由寫進 journal**，而且把「會讓展件起不來」
# 與「會讓展件很難看」分成兩種離開碼。
#
#   0  可以起
#   1  起不來（缺檔、缺 cryptography、埠被別人佔著）——systemd 會重試
#
# ⚠ **字型只是警告，不擋啟動。** 乾淨的 Ubuntu 沒有 U+6A5F「機」，整頁會是豆腐字。
#   那很難看，但「很難看的展件」比「黑畫面」離可用近得多，而開機的時候沒有人
#   能去跑 apt。布展當天那一關在 `venue_check.sh` 第五節，**那一節是硬傷**。
#
#   ./exhibit_preflight.sh [--twin-port 8899] [--tv-port 8420] [--hm <路徑>]
#
# 環境變數：
#   VACANT_EXHIBIT_KILL_STALE=1  埠被**我們自己上一次**留下來的行程佔著時砍掉它
#                                （只砍 cmdline 對得上 serve_twin.py／http.server 的，
#                                 對不上就照樣失敗——不要拿展件當理由去砍別人的東西）
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
HM="${VACANT_HM:-$(cd "$REPO/.." && pwd)/vacant_hm}"
PY="${PYTHON:-python3}"
TV_PORT=8420
TWIN_PORT=8899
FAIL=0

while [ $# -gt 0 ]; do
  case "$1" in
    --tv-port)   TV_PORT="$2"; shift ;;
    --twin-port) TWIN_PORT="$2"; shift ;;
    --hm)        HM="$2"; shift ;;
    *) echo "preflight：不認得的參數 $1" >&2; exit 2 ;;
  esac
  shift
done

say()  { echo "[preflight] $*"; }
bad()  { echo "[preflight] ✗ $*" >&2; FAIL=$((FAIL+1)); }
warn() { echo "[preflight] ! $*" >&2; }

# ── 一、檔案在不在 ──────────────────────────────────────────────
[ -f "$REPO/ops/exhibit/twin/twin_pack.json" ] \
  || bad "沒有資料包 $REPO/ops/exhibit/twin/twin_pack.json ⇒ 展件沒有東西可以播"
[ -f "$HM/world3/index.html" ] \
  || bad "沒有電視那一頁 $HM/world3/index.html ⇒ 電視會是白畫面（VACANT_HM 指對了嗎）"

# ── 二、import 得起來嗎 ─────────────────────────────────────────
# ⚠ 這一關擋的是 `cryptography`。`serve_twin.py` 自己只有 stdlib，但它 import 的
#   `to_events` 會拉 `vacant.logbook`，而那個要 `cryptography`——**一個原生 wheel**。
#   乾淨的展場機不保證有（DECISION_20260919_EXHIBIT_LINUX.md §1 的那一段）。
#   直接 import 真正要跑的那一支，比逐個猜套件名可靠。
if IMPORT_ERR=$("$PY" -c "
import sys
sys.path.insert(0, '$REPO')
from ops.exhibit.twin import serve_twin   # noqa: F401
" 2>&1); then
  say "✓ serve_twin import 得起來（cryptography 在）"
else
  bad "serve_twin import 不起來：$(echo "$IMPORT_ERR" | tail -2 | tr '\n' ' ')"
  bad "  多半是缺 cryptography ⇒ sudo apt install -y python3-cryptography"
fi

# ── 三、埠 ─────────────────────────────────────────────────────
port_holder() {   # $1=port → "pid cmdline" 或空
  local p="$1" pid
  pid=$(ss -ltnp 2>/dev/null | awk -v p=":$p\$" '$4 ~ p' \
        | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2)
  [ -n "$pid" ] && echo "$pid $(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null)"
}
for p in "$TV_PORT" "$TWIN_PORT"; do
  H=$(port_holder "$p")
  [ -z "$H" ] && { say "✓ 埠 $p 沒人佔"; continue; }
  PID=${H%% *}; CMD=${H#* }
  case "$CMD" in
    *serve_twin.py*|*http.server*)
      if [ "${VACANT_EXHIBIT_KILL_STALE:-0}" = "1" ]; then
        warn "埠 $p 被上一次留下來的展件行程佔著（pid $PID）⇒ 砍掉重來"
        kill "$PID" 2>/dev/null; sleep 2; kill -9 "$PID" 2>/dev/null
        [ -n "$(port_holder "$p")" ] && bad "砍不掉 pid $PID，埠 $p 還是被佔著"
      else
        bad "埠 $p 被上一次留下來的展件行程佔著（pid $PID: $CMD）"
        bad "  ⇒ 設 VACANT_EXHIBIT_KILL_STALE=1 讓它自己砍，或手動 kill $PID"
      fi ;;
    *)
      bad "埠 $p 被**別的東西**佔著（pid $PID: $CMD）"
      bad "  ⇒ 這一支不會去砍它。改埠（--twin-port／--tv-port）或先停掉那個服務。" ;;
  esac
done

# ── 四、中文字型（警告，不擋）─────────────────────────────────────
if ! command -v fc-list >/dev/null 2>&1; then
  warn "沒有 fc-list，量不到字型（＝沒量到，不是量到 0）"
else
  N=$(fc-list :lang=zh 2>/dev/null | wc -l)
  if [ "$N" -eq 0 ]; then
    warn "⚠⚠ 一個中文字型都沒有 ⇒ 電視與手機會**整頁豆腐字**（連「機」都畫不出來）"
    warn "    sudo apt install -y fonts-noto-cjk fonts-noto-cjk-extra && fc-cache -f"
    warn "    然後**重開瀏覽器**。展件照樣啟動——黑畫面比豆腐字更難救。"
  else
    say "✓ 中文字型 $N 個"
  fi
fi

if [ "$FAIL" -gt 0 ]; then
  echo "[preflight] ✗ $FAIL 條擋住啟動。systemd 會重試；理由在上面。" >&2
  exit 1
fi
say "✓ 可以起"
exit 0
