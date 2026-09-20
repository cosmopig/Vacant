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
STORE_PORT=8901
NO_TWIN=0
LAN=0
FAIL=0

while [ $# -gt 0 ]; do
  case "$1" in
    --tv-port)   TV_PORT="$2"; shift ;;
    --twin-port) TWIN_PORT="$2"; shift ;;
    --store-port) STORE_PORT="$2"; shift ;;
    --no-twin)   NO_TWIN=1 ;;
    --hm)        HM="$2"; shift ;;
    # 待會 ExecStart 會用 --lan ⇒ 先在這裡把「區網 IP 抓不抓得到」量一次。
    --lan)       LAN=1 ;;
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
#   `to_events` 會拉 `vacant_network.logbook`，而那個要 `cryptography`——**一個原生 wheel**。
#   乾淨的展場機不保證有（DECISION_20260919_EXHIBIT_LINUX.md §1 的那一段）。
#   ⚠ **故意不寫套件名。** 直接 import 真正要跑的那一支，比逐個猜套件名可靠——
#     而且套件名真的會變：2026-09-20 的 `fb7f4bfb` 把 `vacant` 改名成
#     `vacant_network`，這一關**一個字都不用改**就照樣是對的。
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
PORTS="$TV_PORT $TWIN_PORT"
# 8901＝`twinlink serve` 的唯讀端點。它以前不在這個名單上，於是「埠被佔」
# 這一關對數位分身那條線**整條沒有量過**（2026-09-21 補）。
[ "$NO_TWIN" = "0" ] && PORTS="$PORTS $STORE_PORT"
for p in $PORTS; do
  H=$(port_holder "$p")
  [ -z "$H" ] && { say "✓ 埠 $p 沒人佔"; continue; }
  PID=${H%% *}; CMD=${H#* }
  case "$CMD" in
    *serve_twin.py*|*http.server*|*twinlink.py*)
      if [ "${VACANT_EXHIBIT_KILL_STALE:-0}" = "1" ]; then
        warn "埠 $p 被上一次留下來的展件行程佔著（pid ${PID}）⇒ 砍掉重來"
        kill "$PID" 2>/dev/null; sleep 2; kill -9 "$PID" 2>/dev/null
        [ -n "$(port_holder "$p")" ] && bad "砍不掉 pid ${PID}，埠 $p 還是被佔著"
      else
        bad "埠 $p 被上一次留下來的展件行程佔著（pid $PID: ${CMD}）"
        bad "  ⇒ 設 VACANT_EXHIBIT_KILL_STALE=1 讓它自己砍，或手動 kill $PID"
      fi ;;
    *)
      bad "埠 $p 被**別的東西**佔著（pid $PID: ${CMD}）"
      bad "  ⇒ 這一支不會去砍它。改埠（--twin-port／--tv-port）或先停掉那個服務。" ;;
  esac
done

# ── 四、區網 IP（只有 --lan 才量）────────────────────────────────
# ⚠ **這一節是一個事故的遺物。** 2026-09-19 之前，這一段偵測邏輯
#   **從來沒有被執行過**——它只有加 `--lan` 才會跑，而當時的驗證跑的是
#   不帶 `--lan` 的版本，紀錄裡那句「會正確 fall back 到 hostname -I」
#   是**讀碼讀出來的描述，不是量出來的結果**。真的跑下去是
#   `set -euo pipefail` 底下當場斷掉：**exit 1、一個字都不印**，
#   在 systemd 底下就是每 10 秒重啟、journal 只有 status=1/FAILURE。
#   ⇒ 現在它有 `--print-host`，而這一節**每次開機都把它跑一遍**。
#     從讀碼描述一條路徑，不等於量過它。
if [ "$LAN" = "1" ]; then
  if HOSTOUT=$("$HERE/exhibit_boot.sh" --lan --print-host 2>&1); then
    say "✓ 區網 IP 抓得到：$(echo "$HOSTOUT" | tail -1)（QR 會指到這裡）"
    case "$(echo "$HOSTOUT" | tail -1)" in
      100.6[4-9].*|100.[7-9]?.*|100.1[01]?.*|100.12[0-7].*)
        warn "那是 CGNAT／Tailscale 那一段，展場 hotspot 上的手機多半連不到" ;;
    esac
  else
    RC=$?
    bad "區網 IP 抓不到（exhibit_boot.sh --print-host 回 ${RC}）：$(echo "$HOSTOUT" | tr '\n' ' ')"
    [ "$RC" = "1" ] && bad "  ⚠ 回 1 而不是 2 ＝ 腳本在某處當場斷掉沒說話，那是 bug 不是環境問題"
  fi
fi

# ── 四之二、分身快照寫得進去嗎（擋啟動）──────────────────────────
# `twinlink loop --out` 寫的就是電視 snapshot 那一層讀的檔。目錄不在／不可寫
# ＝ loop 每一輪都在 export 那一步炸，而電視只會安靜地停在舊快照上。
# ⚠ 這裡只量目錄，不去碰那個檔——它是 vacant_hm 版控裡的東西。
if [ "$NO_TWIN" = "0" ]; then
  SNAPDIR="$HM/world3/live"
  if [ ! -d "$SNAPDIR" ]; then
    bad "分身快照的目錄不在：${SNAPDIR}（VACANT_HM 指對了嗎）"
  elif [ ! -w "$SNAPDIR" ]; then
    bad "分身快照的目錄不可寫：$SNAPDIR ⇒ loop 每一輪都會在 export 炸掉"
  else
    say "✓ 分身快照寫得進去：$SNAPDIR/visitors.json"
  fi
fi

# ── 五、中文字型（警告，不擋）─────────────────────────────────────
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
