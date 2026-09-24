#!/usr/bin/env bash
# 展場機開機腳本：手機 ↔ 電視那一整條線，一行起來。
#
# 為什麼要這一支（D3）：電視在 `file://` 下 `fetch` 會被 CORS 擋，**一個字都拿不到**。
# 所以展場一定要有一個本機靜態伺服器。這件事以前只活在某個人的記憶裡，
# 現在寫進開機腳本。
#
#   ┌ 8420  vacant_hm 的靜態站（電視）      ← python3 -m http.server
#   ├ 8899  serve_twin.py（事件流＋/state＋/control＋/r/<cell>＋手機頁）
#   │        電視事件只有一個來源：lifecycle 錄影（`recordings/*.jsonl`，重播）
#   │        或 `--live <lifecycle.jsonl>`（真跑，有就先播）。2026-09-24 起沒有
#   │        「從 run 目錄事後推事件」那一條了（`to_events.py` 已刪）。
#   └ 8901  twinlink serve（**唯讀**：數位分身真相來源 /visitors.json）
#
# ⚠ **8901 那一行是 2026-09-21 補上的。** 在那之前，`twinlink`／`twinstore`／
#   `visitors.json`／`&twin=` 這四個字在 `exhibit_boot.sh`、`exhibit_preflight.sh`、
#   `venue_check.sh` 與三個 systemd 檔裡的 grep 命中數**全部是 0**
#   （正控制：同一個 grep 打在 `twinlink.py` 上 16 命中 ⇒ grep 量得動）。
#   也就是說：整條「觀眾手機 → 公網 → 庫 → 1003 → 螢幕」的線寫好了、測過了、
#   **但沒有接在開機路徑上**，而布展當天 venue_check 會印綠。
#   ⇒ 現在電視網址帶 `&twin=`、開機起唯讀端點、`twinlink loop` 有自己的 unit、
#     `venue_check.sh` 第八節會去敲它。守著這件事的是
#     `tests/test_exhibit_twin_wiring.py`（含正控制）。
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
#   ./exhibit_boot.sh --recording a.jsonl   只重播這一份錄影（可給多次；
#                                           不給＝ops/exhibit/twin/recordings/*.jsonl）
#   ./exhibit_boot.sh --live runs/x/lifecycle.jsonl --live-runs runs/x
#                                           tail 真跑：有真跑就先播真跑，閒下來回到重播；
#                                           --live-runs 讓那幾格跑完就有收據頁
#   ./exhibit_boot.sh --lan --print-host    只印「區網 IP 抓到什麼」就結束
#                                           （0＝抓到、2＝抓不到並說明；1 是 bug）
#   ./exhibit_boot.sh --no-twin             不接數位分身（回到 09-21 之前的行為）
#   ./exhibit_boot.sh --no-twin-loop        起唯讀端點但不起 loop（庫是唯讀的）
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
# 數位分身那一條線（twinstore 真相來源 → twinlink serve 唯讀端點 → 電視 &twin=）。
STORE_PORT=8901
NO_TWIN=0
NO_TWIN_LOOP=0
TWIN_DB="${VACANT_TWIN_DB:-}"
DWELL=30
BIND=127.0.0.1
KIOSK=0
TOKEN="${VACANT_TWIN_TOKEN:-}"
NO_TOKEN=0
PRINT_HOST=0
RECORDINGS=()
LIVE_SRC=""
LIVE_RUNS=""

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
    --recording) RECORDINGS+=("$2"); shift ;;
    --live)   LIVE_SRC="$2"; shift ;;
    # 真跑那一次 run_twin.py 的 --out：給了，那一格跑完就即時打包收據（/v/live.html）。
    --live-runs) LIVE_RUNS="$2"; shift ;;
    --tv-port)   TV_PORT="$2"; shift ;;
    --twin-port) TWIN_PORT="$2"; shift ;;
    --store-port) STORE_PORT="$2"; shift ;;
    --twin-db)   TWIN_DB="$2"; shift ;;
    --no-twin)   NO_TWIN=1 ;;
    --no-twin-loop) NO_TWIN_LOOP=1 ;;
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
# 電視要播的東西：lifecycle 錄影（重播）。一份都沒有又沒給 --live ⇒ 電視會是空的。
# ⚠ `twin_pack.json` **不再是事件來源**，只剩收據頁（/r/<cell>）在用；沒有它
#   展件照樣起得來，只是 /r/<cell> 會一律 404 並講明（不會帶人去看別的鏈）。
if [ "$PRINT_HOST" = "0" ] && [ -z "$LIVE_SRC" ] && [ "${#RECORDINGS[@]}" -eq 0 ] \
   && ! ls "$REPO"/ops/exhibit/twin/recordings/*.jsonl >/dev/null 2>&1; then
  echo "找不到任何 lifecycle 錄影：$REPO/ops/exhibit/twin/recordings/*.jsonl" >&2
  echo "先跑：bash $REPO/ops/exhibit/twin/record_fixture.sh（L-none 備援），" >&2
  echo "或用 --recording 指一份、用 --live 接真跑。" >&2
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

cleanup(){ kill ${TV_PID:-} ${TWIN_PID:-} ${STORE_PID:-} ${LOOP_PID:-} 2>/dev/null || true; }
trap cleanup EXIT INT TERM

( cd "$HM" && exec "$PY" -m http.server "$TV_PORT" --bind 127.0.0.1 >/dev/null 2>&1 ) &
TV_PID=$!

# --base-url 就是 QR 會編進去的東西。**一定要傳**，預設值是 127.0.0.1。
TWIN_ARGS=(--bind "$BIND" --port "$TWIN_PORT" --dwell "$DWELL"
           --base-url "http://$HOST:$TWIN_PORT")
for R in "${RECORDINGS[@]+"${RECORDINGS[@]}"}"; do TWIN_ARGS+=(--recording "$R"); done
[ -n "$LIVE_SRC" ] && TWIN_ARGS+=(--live "$LIVE_SRC")
[ -n "$LIVE_RUNS" ] && TWIN_ARGS+=(--live-runs "$LIVE_RUNS")
if [ -n "$TOKEN" ]; then
  TWIN_ARGS+=(--token "$TOKEN")
else
  TWIN_ARGS+=(--no-token)
fi
"$PY" "$REPO/ops/exhibit/twin/serve_twin.py" "${TWIN_ARGS[@]}" &
TWIN_PID=$!

# ── 數位分身：唯讀端點（電視 `&twin=` 指的就是這一台）────────────────────
#
# ⚠ `twinlink serve` 是 `mode=ro` 開檔——**庫不在的時候每一次 GET 都 500**，
#   而畫面上只會變成「一個都讀不到」，沒有人查得出為什麼。所以先確保庫在
#   （`view` 走的是非唯讀建構子，schema 全是 `CREATE ... IF NOT EXISTS`，
#    對已經有資料的庫是 no-op ⇒ 不會覆寫 1003 上那個真相來源）。
STORE_URL=""
if [ "$NO_TWIN" = "0" ]; then
  TL="$REPO/ops/exhibit/twin/twinlink.py"
  DBARGS=()
  [ -n "$TWIN_DB" ] && DBARGS=(--db "$TWIN_DB")
  # stderr 落盤再取 `$?`。`cmd | tee` 之後的 `$?` 是 tee 的，那個坑在這個 repo
  # 有名字（工作紀律：不要吞 stderr）。
  ERRF="$(mktemp -t twinboot)"
  if ! "$PY" "$TL" "${DBARGS[@]+"${DBARGS[@]}"}" view >/dev/null 2>"$ERRF"; then
    echo "twinlink 開不了庫 ⇒ 數位分身那一條線起不來：" >&2
    tail -3 "$ERRF" >&2
    rm -f "$ERRF"
    echo "要先把展件跑起來、分身晚點再說，就加 --no-twin（那是一個決定，不是預設）。" >&2
    exit 2
  fi
  rm -f "$ERRF"
  "$PY" "$TL" "${DBARGS[@]+"${DBARGS[@]}"}" serve --bind 127.0.0.1 --port "$STORE_PORT" &
  STORE_PID=$!
  STORE_URL="http://127.0.0.1:$STORE_PORT/visitors.json"
fi

# ⚠ **不要只 sleep 一次再敲一次。** 2026-09-21 實測：機器忙的時候（另一個
#   工作在跑整套測試）三支 python 一秒之內起不來，於是這裡會判「起不來」
#   而其實只是還沒好——那是**誤殺**，而展場開機正是最忙的那一刻
#   （systemd 同時拉起所有東西、字型快取、瀏覽器）。
#   ⇒ 改成輪詢一個窗口。**fail-loud 沒有被稀釋**：窗口過完還是敲不到就 exit 2，
#     只是不再把「還沒好」講成「壞了」。（kiosk unit 等 8420 用的是同一招。）
BOOT_WAIT_S="${VACANT_EXHIBIT_BOOT_WAIT_S:-20}"
wait_for() {   # $1=url  → 0 敲到了／1 窗口內都沒敲到
  local i=0
  while [ "$i" -lt "$BOOT_WAIT_S" ]; do
    curl -fsS --max-time 3 "$1" >/dev/null 2>&1 && return 0
    i=$((i+1)); sleep 1
  done
  return 1
}

# ⚠ **驗那個位址真的連得到**，不是只印出來。換一個網路環境、介面抓錯、
#   防火牆擋住——三種都會讓 QR 變成一張掃不開的圖，而畫面照樣叫人掃。
if ! wait_for "http://$HOST:$TWIN_PORT/state"; then
  echo "等了 ${BOOT_WAIT_S}s，http://$HOST:$TWIN_PORT/state 還是連不到自己。" >&2
  echo "QR 會指到一個連不到的位址 ⇒ **不繼續**。" >&2
  exit 2
fi
echo "  ✓ http://$HOST:$TWIN_PORT 自己連得到（QR 指的就是這個）"

# 🔴 **電視那一台以前完全沒有健檢。** `python3 -m http.server` 在埠被佔的時候
#    當場死掉，而這支腳本照樣把「電視 http://…」印在漂亮橫幅裡——操作員
#    由下往上讀，看到的是一切正常。橫幅印出來的每一個網址都要先敲過。
if ! wait_for "http://127.0.0.1:$TV_PORT/world3/index.html"; then
  echo "等了 ${BOOT_WAIT_S}s，電視那一頁還是敲不到：http://127.0.0.1:$TV_PORT/world3/index.html" >&2
  echo "靜態站沒起來（埠 $TV_PORT 被佔？）⇒ 電視會是白畫面 ⇒ **不繼續**。" >&2
  exit 2
fi
echo "  ✓ http://127.0.0.1:$TV_PORT/world3/index.html 拿得到（電視不會是白的）"

# 唯讀端點也要敲，而且**要敲到欄位**不是只看 200：一個回 200 的空殼跟
# 一個真的讀得到庫的端點，在 curl 眼裡長得一樣。
if [ -n "$STORE_URL" ]; then
  if ! wait_for "$STORE_URL"; then
    echo "等了 ${BOOT_WAIT_S}s，分身唯讀端點還是敲不到：$STORE_URL" >&2
    echo "電視的 &twin= 會指到一個連不到的位址 ⇒ **不繼續**（要跳過就 --no-twin）。" >&2
    exit 2
  fi
  # 上面 wait_for 才剛敲到過，這裡又敲不到 ⇒ 它在這兩秒之間死掉了。
  # 少見但真實（庫被別的行程鎖住、磁碟滿），所以留著而不是假設不會發生。
  if ! SV=$(curl -fsS --max-time 5 "$STORE_URL" 2>/dev/null); then
    echo "分身唯讀端點剛剛還在、現在敲不到了：$STORE_URL" >&2
    echo "電視的 &twin= 會指到一個連不到的位址 ⇒ **不繼續**（要跳過就 --no-twin）。" >&2
    exit 2
  fi
  if ! NV=$(printf '%s' "$SV" | "$PY" -c 'import json,sys
d=json.load(sys.stdin)
n=(d.get("counts") or {}).get("visitors")
assert isinstance(n,int) and not isinstance(n,bool), n
print(n)' 2>/dev/null); then
    echo "$STORE_URL 回了 200，但讀不到 counts.visitors ⇒ 形狀不對，**不繼續**。" >&2
    exit 2
  fi
  # `${NV}` 的大括號不是風格：bash 3.2 會把後面全形括號的第一個 byte
  # 吃進變數名，`set -u` 之下當場 unbound variable（2026-09-21 實測踩到）。
  echo "  ✓ $STORE_URL 讀得到（counts.visitors=${NV}）"
fi

# ── 數位分身：ingest→generate→publish→export 的迴圈 ─────────────────────
#
# 🔴 沒有它，`world3/live/visitors.json` 那個 snapshot **沒有任何東西會去寫**
#    （commit 進 vacant_hm 的那一份是 `people: []`＋`generated_at: null` 的佔位檔）。
#    ⇒ 觀眾用手機投的卡永遠不會變成分身，而畫面平靜地說「分身讀本機快照」。
#    展場那台 Linux 用的是 `vacant-twin-loop.service`（`Restart=always`）；
#    這裡起的是給「人站在鍵盤前面」那一種跑法用的。
LOOP_WHY=off
# ⚠ 這個值要跟 `twin_loop.sh` **算出同一條路徑**，否則橫幅會印一個沒人在寫的檔。
#   2026-09-21 實跑抓到：橫幅寫死 `$HM/...`，而 `VACANT_TWIN_OUT` 一設，
#   loop 其實寫到別的地方去了——操作員照著橫幅去看那個檔，會看到它永遠不動。
TWIN_OUT="${VACANT_TWIN_OUT:-$HM/world3/live/visitors.json}"
if [ "$NO_TWIN" = "0" ] && [ "$NO_TWIN_LOOP" = "0" ]; then
  if [ -n "${VACANT_TWIN_CLOUD_TOKEN:-}" ]; then
    VACANT_HM="$HM" "$REPO/ops/exhibit/twin/twin_loop.sh" &
    LOOP_PID=$!
    LOOP_WHY=on
  else
    LOOP_WHY=no-token
  fi
elif [ "$NO_TWIN_LOOP" = "1" ]; then
  LOOP_WHY=off-explicit
fi

LIVE="http://$HOST:$TWIN_PORT/live/events.jsonl"
TV_URL="http://127.0.0.1:$TV_PORT/world3/index.html?live=$LIVE&poll=2000"
# 🔴 `&twin=` 就是電視去讀本機真相來源的那一段。少了它，電視只剩 snapshot
#    那一層（而且是一個沒人在寫的檔）——`bridge.js` 的來源鏈是
#    store → snapshot → cloud，第一層在網址裡，不在程式裡。
[ -n "$STORE_URL" ] && TV_URL="$TV_URL&twin=$STORE_URL"
PHONE_URL="http://$HOST:$TWIN_PORT/phone.html"
[ -n "$TOKEN" ] && PHONE_URL="$PHONE_URL?t=$TOKEN"

echo
echo "───────────────────────────────────────────────"
echo " 電視 　$TV_URL"
echo " 手機 　$PHONE_URL   ← QR 編的就是這一行"
echo " 收據 　http://$HOST:$TWIN_PORT/viewer.html"
if [ "${#RECORDINGS[@]}" -gt 0 ]; then
  echo " 重播 　${RECORDINGS[*]}（mode=replay：畫面上要標「重播」）"
else
  echo " 重播 　ops/exhibit/twin/recordings/*.jsonl（mode=replay：畫面上要標「重播」）"
fi
if [ -n "$LIVE_SRC" ]; then
  echo " 真跑 　${LIVE_SRC}（mode=live：有真跑就先播，閒下來回到重播）"
  if [ -n "$LIVE_RUNS" ]; then
    echo " 　　　 收據：${LIVE_RUNS}（每一格跑完即時打包，/v/live.html）"
  else
    echo " 　　　 ⚠ 沒有 --live-runs：真跑那幾格沒有收據頁，/r/<cell> 會照實 404"
  fi
fi
echo " QR   　http://$HOST:$TWIN_PORT/qr.png（執行期畫的）"
if [ -n "$STORE_URL" ]; then
  echo " 分身 　${STORE_URL}（唯讀；電視的 &twin= 指這裡）"
else
  echo " 分身 　⚠ --no-twin：電視網址沒有 &twin=，分身那一條線整條沒接"
fi
echo "───────────────────────────────────────────────"
case "$LOOP_WHY" in
  on) echo " ✓ twinlink loop 在跑（快照寫 ${TWIN_OUT}）" ;;
  no-token)
    echo " ⚠⚠ twinlink loop **沒有起來**：沒有 VACANT_TWIN_CLOUD_TOKEN。"
    echo "    ⇒ 公網那個郵箱抄不進來，**觀眾用手機投的卡不會變成分身**。"
    echo "    ⇒ ${TWIN_OUT} 停在上一次寫的樣子（可能是空的佔位檔）。"
    echo "    這不是「0 個觀眾」，是這條線沒接。展件其他部分照跑。" ;;
  off-explicit) echo " ⚠ --no-twin-loop：庫是唯讀的，不會有新的人進來（明講的決定）" ;;
esac
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
