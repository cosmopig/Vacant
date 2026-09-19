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
#   ./exhibit_boot.sh --lan                 手機連得到（區網）
#   ./exhibit_boot.sh --hm /path/vacant_hm  vacant_hm 不在預設位置
#   ./exhibit_boot.sh --dwell 25            沒人按的時候幾秒換一格
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

while [ $# -gt 0 ]; do
  case "$1" in
    --lan)    BIND=0.0.0.0 ;;
    --hm)     HM="$2"; shift ;;
    --dwell)  DWELL="$2"; shift ;;
    --tv-port)   TV_PORT="$2"; shift ;;
    --twin-port) TWIN_PORT="$2"; shift ;;
    --kiosk)  KIOSK=1 ;;
    *) echo "不認得的參數：$1" >&2; exit 2 ;;
  esac
  shift
done

if [ ! -f "$HM/world3/index.html" ]; then
  echo "找不到電視那一頁：$HM/world3/index.html" >&2
  echo "用 --hm <路徑> 指過去，或設 VACANT_HM 環境變數。" >&2
  exit 2
fi
if [ ! -f "$REPO/ops/exhibit/twin/twin_pack.json" ]; then
  echo "找不到資料包：$REPO/ops/exhibit/twin/twin_pack.json" >&2
  echo "先跑：$PY $REPO/ops/exhibit/twin/pack.py --runs <run 目錄>" >&2
  exit 2
fi

# 展場機自己看得到的位址。--lan 的時候手機要用這一台的區網 IP，下面會印出來。
HOST=127.0.0.1
LAN_IP="$( (ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}') || true)"
[ "$BIND" = "0.0.0.0" ] && [ -n "$LAN_IP" ] && HOST="$LAN_IP"

cleanup(){ kill ${TV_PID:-} ${TWIN_PID:-} 2>/dev/null || true; }
trap cleanup EXIT INT TERM

( cd "$HM" && exec "$PY" -m http.server "$TV_PORT" --bind 127.0.0.1 >/dev/null 2>&1 ) &
TV_PID=$!

"$PY" "$REPO/ops/exhibit/twin/serve_twin.py" \
  --bind "$BIND" --port "$TWIN_PORT" --dwell "$DWELL" \
  --base-url "http://$HOST:$TWIN_PORT" &
TWIN_PID=$!

sleep 1
LIVE="http://$HOST:$TWIN_PORT/live/events.jsonl"
TV_URL="http://127.0.0.1:$TV_PORT/world3/index.html?live=$LIVE&poll=2000"

echo
echo "───────────────────────────────────────────────"
echo " 電視 　$TV_URL"
echo " 手機 　http://$HOST:$TWIN_PORT/phone.html"
echo " 收據 　http://$HOST:$TWIN_PORT/viewer.html"
echo "───────────────────────────────────────────────"
if [ "$BIND" != "0.0.0.0" ]; then
  echo " ⚠ 只綁本機：手機連不到。展場要用 --lan。"
else
  echo " ⚠ 綁在 0.0.0.0：同一個區網上的任何人都按得動這台電視。"
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
