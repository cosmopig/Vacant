#!/usr/bin/env bash
# 展場機開機腳本：手機 ↔ 電視那一整條線，一行起來。
#
# 為什麼要這一支（D3）：電視在 `file://` 下 `fetch` 會被 CORS 擋，**一個字都拿不到**。
# 所以展場一定要有一個本機靜態伺服器。這件事以前只活在某個人的記憶裡，
# 現在寫進開機腳本。
#
#   ┌ 8420  vacant_hm 的靜態站（電視）      ← python3 -m http.server
#   └ 8899  serve_twin.py（事件流＋/state＋/control＋/r/<cell>＋手機頁）
#
# 兩支都只綁在本機。要讓**手機**連得到，加 --lan：那會把 serve_twin 綁到
# 0.0.0.0，同一個區網（展場的 hotspot）上的任何人都按得動這台電視——
# 那是展場的現實，不是可以靜靜略過的細節。
#
#   ./exhibit_boot.sh                       本機兩台都起來
#   ./exhibit_boot.sh --lan                 手機連得到（區網）＋自動生 token
#   ./exhibit_boot.sh --lan --no-token      明知故犯：區網上任何人都按得動
#   ./exhibit_boot.sh --hm /path/vacant_hm  vacant_hm 不在預設位置
#   ./exhibit_boot.sh --dwell 25            沒人按的時候幾秒換一格
#   ./exhibit_boot.sh --lan --print-host    只印「區網 IP 抓到什麼」就結束
#                                           （0＝抓到、2＝抓不到並說明；1 是 bug）
#
# ⚠ `--lan` **一定會有 token**（2026-09-19 起）。沒給 `--token`／`VACANT_TWIN_TOKEN`
#   就這一次開機自動生一把，編進 QR 的網址裡。要關得明講 `--no-token`。
#   為什麼是自動生不是拒絕啟動：見
#   `decisions/DECISION_20260919_EXHIBIT_UNATTENDED.md` §一。
#
# 全程**零模型呼叫、零外網**。起來之後拔掉網路線照跑。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
HM="${VACANT_HM:-$(cd "$REPO/.." && pwd)/vacant_hm}"
PY="${PYTHON:-python3}"
TV_PORT=8420
TWIN_PORT=8899
DWELL=30
BIND=127.0.0.1
KIOSK=0
TOKEN="${VACANT_TWIN_TOKEN:-}"
NO_TOKEN=0
PRINT_HOST=0

while [ $# -gt 0 ]; do
  case "$1" in
    --lan)    BIND=0.0.0.0 ;;
    # 只跑「這台機器的區網 IP 抓不抓得到」然後印出來就結束，什麼都不啟動。
    # ⚠ **這一格的存在理由是一個真實事故**：區網 IP 偵測那一段以前
    #   **從來沒有被執行過**，只被「讀碼讀出來」寫進紀錄
    #   （DECISION_20260919_EXHIBIT_LINUX.md §1 說它會 fall back 到
    #   `hostname -I`——那句話是讀出來的，不是量出來的；`--lan` 那一整塊
    #   只有加 `--lan` 才會跑，而那一份跑的是不帶 `--lan` 的版本）。
    #   真的跑下去是 **exit 1、一個字都不印**。
    #   ⇒ 有了這一格，那一段就**量得到**了（`exhibit_preflight.sh --lan`
    #     與 `tests/test_serve_twin.py` 都在用它）。
    --print-host) PRINT_HOST=1 ;;
    --hm)     HM="$2"; shift ;;
    --dwell)  DWELL="$2"; shift ;;
    --tv-port)   TV_PORT="$2"; shift ;;
    --twin-port) TWIN_PORT="$2"; shift ;;
    --token)  TOKEN="$2"; shift ;;
    --no-token)  NO_TOKEN=1 ;;
    --kiosk)  KIOSK=1 ;;
    *) echo "不認得的參數：$1" >&2; exit 2 ;;
  esac
  shift
done

if [ "$PRINT_HOST" = "0" ] && [ ! -f "$HM/world3/index.html" ]; then
  echo "找不到電視那一頁：$HM/world3/index.html" >&2
  echo "用 --hm <路徑> 指過去，或設 VACANT_HM 環境變數。" >&2
  exit 2
fi
if [ "$PRINT_HOST" = "0" ] && [ ! -f "$REPO/ops/exhibit/twin/twin_pack.json" ]; then
  echo "找不到資料包：$REPO/ops/exhibit/twin/twin_pack.json" >&2
  echo "先跑：$PY $REPO/ops/exhibit/twin/pack.py --runs <run 目錄>" >&2
  exit 2
fi

# 展場機自己看得到的位址。--lan 的時候手機要用這一台的**區網 IP**。
#
# ⚠ 這個值不是拿來印好看的：`serve_twin` 用它畫 QR，而 QR 是觀眾唯一的入口。
#   抓錯（或抓到 127.0.0.1）＝ QR 指到手機自己的迴路位址 ⇒ 掃了一定連不到，
#   而且現場沒有人會回報，只會看到人掃完就走掉。
HOST=127.0.0.1
if [ "$BIND" = "0.0.0.0" ]; then
  LAN_IP="${VACANT_LAN_IP:-}"
  # macOS：介面名字是 en0／en1，`ipconfig getifaddr` 只吐 IPv4。
  if [ -z "$LAN_IP" ]; then
    for IF in en0 en1; do
      LAN_IP="$(ipconfig getifaddr "$IF" 2>/dev/null || true)"
      [ -n "$LAN_IP" ] && break
    done
  fi
  # Linux：**不要猜介面名字。**
  #
  # ⚠ 2026-09-19 在 vacant-dev（Ubuntu 24.04）實測到的兩個坑，兩個都會
  #   讓展場當天壞掉而且**畫面上看不出來**：
  #   (a) 舊版寫死 `en0 en1 eth0 wlan0`，而這台的介面叫 `ens33`
  #       ——名單全部落空。展場機叫什麼沒有人保證得了。
  #   (b) 更糟的是舊版那一行 `LAN_IP="$(ip ... | awk | cut | head)"`
  #       **沒有 `|| true`**，而這支腳本開著 `set -o pipefail`：
  #       `ip` 對不存在的介面回 1 ⇒ 整條管線回 1 ⇒ `set -e` 當場結束腳本，
  #       **exit 1、一個字都不印**，連下面那個 `hostname -I` 的退路都走不到。
  #       在 systemd 底下就是每 10 秒重啟一次、journal 裡只有 status=1/FAILURE。
  #   ⇒ 改成列出**真的存在的** global scope IPv4，並跳過不是區網的那幾類介面。
  if [ -z "$LAN_IP" ] && command -v ip >/dev/null 2>&1; then
    LAN_IP="$(ip -4 -o addr show scope global 2>/dev/null \
              | awk '$2 !~ /^(tailscale|docker|veth|br-|virbr|zt|wg)/ {print $4}' \
              | cut -d/ -f1 | head -1 || true)"
  fi
  if [ -z "$LAN_IP" ]; then
    LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
  fi
  case "$LAN_IP" in
    ""|127.*|169.254.*)
      echo "抓不到可用的區網 IP（抓到 '${LAN_IP:-空}'）。" >&2
      echo "手機會連不到 ⇒ **不啟動**，免得展場掛一張掃不開的 QR。" >&2
      echo "用 VACANT_LAN_IP=<位址> 指定，或先把網路接好。" >&2
      exit 2 ;;
    100.6[4-9].*|100.[7-9]?.*|100.1[01]?.*|100.12[0-7].*)
      # 100.64.0.0/10 ＝ CGNAT，Tailscale 就住在這裡。展場 hotspot 上的手機
      # **連不到這種位址**。這一條只警告不擋：有些場地真的用得到。
      echo "⚠ 抓到的是 $LAN_IP（100.64.0.0/10＝CGNAT／Tailscale 那一段）。" >&2
      echo "  展場 hotspot 上的手機多半連不到它 ⇒ QR 會掃不開。" >&2
      echo "  要指定就用 VACANT_LAN_IP=<展場那張網卡的位址>。" >&2 ;;
  esac
  HOST="$LAN_IP"
fi

# `--print-host`：到這裡就結束。**這一行是那一段偵測唯一的可執行判準。**
# 離開碼的語意是契約，測試釘著它：
#   0 ＝ 抓到了（stdout 就是那個位址）
#   2 ＝ 抓不到，而且**上面已經印了為什麼**（fail-closed，不是安靜跑錯）
#   1 ＝ **不該出現**。真的出現就代表又有一條路徑在 `set -euo pipefail`
#        底下當場斷掉、一個字都不印——那正是 2026-09-19 那個 bug 的形狀。
if [ "$PRINT_HOST" = "1" ]; then
  echo "$HOST"
  exit 0
fi

# token：**這一支自己決定，不要交給 serve_twin 自己生**。
#
# 理由很實際：QR 與開機橫幅都是這一支印的，而 serve_twin 自動生的那一把
# 只活在它自己的 stdout 裡。兩邊各生一把＝橫幅印 A、伺服器認 B，
# 而那個錯只有在展場有人按下去的時候才看得出來。
# （serve_twin 那一端的自動生仍然留著，那是給「直接跑 serve_twin.py」的人的
#   第二道保險，不是這條線的來源。）
TOKEN_WHY=none
if [ "$NO_TOKEN" = "1" ]; then
  TOKEN=""
  TOKEN_WHY=off-explicit
elif [ -n "$TOKEN" ]; then
  TOKEN_WHY=given
elif [ "$BIND" = "0.0.0.0" ]; then
  TOKEN="$("$PY" -c 'import secrets;print(secrets.token_urlsafe(9))')"
  TOKEN_WHY=auto
else
  TOKEN_WHY=off-loopback
fi

cleanup(){ kill ${TV_PID:-} ${TWIN_PID:-} 2>/dev/null || true; }
trap cleanup EXIT INT TERM

( cd "$HM" && exec "$PY" -m http.server "$TV_PORT" --bind 127.0.0.1 >/dev/null 2>&1 ) &
TV_PID=$!

# --base-url 就是 QR 會編進去的東西。**一定要傳**，預設值是 127.0.0.1。
TWIN_ARGS=(--bind "$BIND" --port "$TWIN_PORT" --dwell "$DWELL"
           --base-url "http://$HOST:$TWIN_PORT")
if [ -n "$TOKEN" ]; then
  TWIN_ARGS+=(--token "$TOKEN")
else
  TWIN_ARGS+=(--no-token)
fi
"$PY" "$REPO/ops/exhibit/twin/serve_twin.py" "${TWIN_ARGS[@]}" &
TWIN_PID=$!

sleep 1

# ⚠ **驗那個位址真的連得到**，不是只印出來。換一個網路環境、介面抓錯、
#   防火牆擋住——三種都會讓 QR 變成一張掃不開的圖，而畫面照樣叫人掃。
if ! curl -fsS --max-time 3 "http://$HOST:$TWIN_PORT/state" >/dev/null 2>&1; then
  echo "起來了，但 http://$HOST:$TWIN_PORT/state 連不到自己。" >&2
  echo "QR 會指到一個連不到的位址 ⇒ **不繼續**。" >&2
  exit 2
fi
echo "  ✓ http://$HOST:$TWIN_PORT 自己連得到（QR 指的就是這個）"

LIVE="http://$HOST:$TWIN_PORT/live/events.jsonl"
TV_URL="http://127.0.0.1:$TV_PORT/world3/index.html?live=$LIVE&poll=2000"
PHONE_URL="http://$HOST:$TWIN_PORT/phone.html"
[ -n "$TOKEN" ] && PHONE_URL="$PHONE_URL?t=$TOKEN"

echo
echo "───────────────────────────────────────────────"
echo " 電視 　$TV_URL"
echo " 手機 　$PHONE_URL   ← QR 編的就是這一行"
echo " 收據 　http://$HOST:$TWIN_PORT/viewer.html"
echo " QR   　http://$HOST:$TWIN_PORT/qr.png（執行期畫的）"
echo "───────────────────────────────────────────────"
if [ "$BIND" != "0.0.0.0" ]; then
  echo " ⚠ 只綁本機：手機連不到。展場要用 --lan。"
else
  case "$TOKEN_WHY" in
    auto)  echo " ✓ /control 要 token（這次開機自動生的）：$TOKEN"
           echo "   重開就會換一把。舊的分頁會收到 403，頁面上會叫他重掃。"
           echo "   ⚠ 這不是身分驗證：看得到電視的人都按得動。它擋的是"
           echo "     「連上同一個 hotspot、但沒站在展件前面」的人。" ;;
    given) echo " ✓ /control 要 token（外面指定的），已編進 QR" ;;
    *)     echo " ⚠⚠ --no-token：同一個區網上的任何人都按得動這台電視。"
           echo "    只有在「展件自己一台獨立熱點」時才是對的。" ;;
  esac
fi
echo " （Ctrl-C 結束）"
echo

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [ "$KIOSK" = "1" ] && [ -x "$CHROME" ]; then
  "$CHROME" --kiosk --incognito --noerrdialogs \
    --disable-session-crashed-bubble --disable-infobars \
    --autoplay-policy=no-user-gesture-required \
    --user-data-dir=/tmp/vacant-twin-kiosk "$TV_URL" >/dev/null 2>&1 &
fi

wait $TWIN_PID
