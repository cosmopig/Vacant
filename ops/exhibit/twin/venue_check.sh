#!/usr/bin/env bash
# 布展當天的一行自驗：這台機器**現在**能不能撐住展期。
#
# 為什麼要這一支（DECISION_20260919_EXHIBIT_LINUX.md）：
# `exhibit_boot.sh` 在埠被佔用的時候，serve_twin 會炸掉，但腳本**仍然把三個
# 網址的漂亮橫幅印出來**——traceback 在上面捲掉了，操作員由下往上讀，看到的是
# 一切正常。exit code 是 1（fail-closed 沒壞），可是沒有人在看 exit code。
# 所以起完之後要有人真的去敲那幾個端點。這一支就是那個人。
#
# 它**只讀不寫**：不改展件任何一個檔、不動 events.jsonl、一通模型都不打。
#
#   ./venue_check.sh                  檢查預設的 8420 / 8899 / 8901
#   ./venue_check.sh --twin-port 8899 --tv-port 8420
#   ./venue_check.sh --skip-tv        只檢查展件伺服器
#   ./venue_check.sh --only-twin      只跑第八節（數位分身那一條線）
#   ./venue_check.sh --skip-twin      不檢查數位分身（明講的決定）
#
# ⚠ **第八節是 2026-09-21 補的，而它補的是一個很難看的洞**：在那之前
#   這一支對 `twinlink`／`twinstore`／`visitors.json`／`&twin=` 的 grep 命中
#   **是 0**（正控制：同一個 grep 打在 `twinlink.py` 上 16 命中）。
#   也就是布展當天這一支會印綠，而整條數位分身線一個字都沒被量。
#
# 離開碼：0＝可以開展；1＝有硬傷（下面會逐條講是哪一條）。
set -uo pipefail

TV_PORT=8420
TWIN_PORT=8899
STORE_PORT=8901
HOST=127.0.0.1
SKIP_TV=0
SKIP_TWIN=0
ONLY_TWIN=0
# 快照多久沒被寫就算「靜默降級」。loop 預設 15 秒一輪，10 分鐘＝連錯 40 輪。
TWIN_MAX_AGE_MIN=10
FAIL=0
WARN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --tv-port)   TV_PORT="$2"; shift ;;
    --twin-port) TWIN_PORT="$2"; shift ;;
    --store-port) STORE_PORT="$2"; shift ;;
    --twin-max-age-min) TWIN_MAX_AGE_MIN="$2"; shift ;;
    --host)      HOST="$2"; shift ;;
    --skip-tv)   SKIP_TV=1 ;;
    --skip-twin) SKIP_TWIN=1 ;;
    --only-twin) ONLY_TWIN=1 ;;
    *) echo "不認得的參數：$1" >&2; exit 2 ;;
  esac
  shift
done

B="http://$HOST:$TWIN_PORT"
ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; }
bad()  { printf "  \033[31m✗\033[0m %s\n" "$1"; FAIL=$((FAIL+1)); }
warn() { printf "  \033[33m!\033[0m %s\n" "$1"; WARN=$((WARN+1)); }
head_() { printf "\n\033[1m%s\033[0m\n" "$1"; }

# curl 連不上的時候自己就會印 000，**不要再補一個 `|| echo 000`**：
# 兩邊都印就變成 `000000`，看起來像一個沒人看過的怪狀態碼。
code() { c=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 8 "$1" 2>/dev/null); echo "${c:-000}"; }

if [ "$ONLY_TWIN" = "0" ]; then
head_ "一、展件伺服器活著嗎"
for p in / /state /live/events.jsonl /phone.html /viewer.html; do
  c=$(code "$B$p")
  [ "$c" = "200" ] && ok "$p → 200" || bad "$p → ${c}（展件伺服器沒起來或壞了）"
done

head_ "二、電視那一頁拿得到嗎"
if [ "$SKIP_TV" = "1" ]; then
  warn "--skip-tv：沒檢查電視（＝沒量到，不是量到沒問題）"
else
  c=$(code "http://$HOST:$TV_PORT/world3/index.html")
  [ "$c" = "200" ] && ok "world3/index.html → 200" \
    || bad "world3/index.html → ${c}（靜態站沒起來 ⇒ 電視會是白畫面）"
  c=$(code "http://$HOST:$TV_PORT/world3/scenes/index.json")
  [ "$c" = "200" ] && ok "scenes/index.json → 200（場景資料在）" \
    || bad "scenes/index.json → ${c}（電視會沒有場景）"
fi

head_ "三、無人值守：沒人按的時候它自己會不會動"
S1=$(curl -sS --max-time 8 "$B/state" 2>/dev/null)
if [ -z "$S1" ]; then
  bad "/state 拿不到，下面沒得驗"
else
  N1=$(printf '%s' "$S1" | python3 -c 'import json,sys;print(json.load(sys.stdin)["emitted"])' 2>/dev/null || echo x)
  DW=$(printf '%s' "$S1" | python3 -c 'import json,sys;print(json.load(sys.stdin)["dwell_s"])' 2>/dev/null || echo 30)
  SLEEP=$(python3 -c "print(min(40, float($DW)+4))" 2>/dev/null || echo 34)
  echo "     （等 ${SLEEP}s 看它自己有沒有往前走，dwell=${DW}s）"
  sleep "$SLEEP"
  N2=$(curl -sS --max-time 8 "$B/state" | python3 -c 'import json,sys;print(json.load(sys.stdin)["emitted"])' 2>/dev/null || echo x)
  if [ "$N1" != "x" ] && [ "$N2" != "x" ] && [ "$N2" -gt "$N1" ]; then
    ok "輪播在動：emitted $N1 → ${N2}（沒有人碰它）"
  else
    bad "輪播沒動：emitted $N1 → ${N2}（無人值守會停在同一格）"
  fi
fi

head_ "四、有沒有格子被擋下來（D2：一格壞掉不准卡死整批）"
if [ -n "${S1:-}" ]; then
  curl -sS --max-time 8 "$B/state" | python3 -c '
import json,sys
s=json.load(sys.stdin)
sk=s.get("skipped") or []
seen=sorted({r["cell_id"] for r in sk})
if not seen:
    print("  \033[32m✓\033[0m 沒有格子被擋（skipped 是空的）")
else:
    print("  \033[33m!\033[0m 有 %d 格被擋下來、輪播仍在繼續（這是設計行為，不是當機）：" % len(seen))
    for c in seen[:5]:
        r=next(x for x in sk if x["cell_id"]==c)
        print("      %s：%s" % (c, (r["reason"] or ["?"])[0]))
    print("      ⚠ 這幾格觀眾看不到。要不要現在修，是人的決定。")
print("  總計 emitted=%s laps=%s pairs=%s cells=%s" % (
    s["emitted"], s["laps"], s["pair"]["of"], len(s["cells"])))
' 2>/dev/null || warn "skipped 解不開"
fi

head_ "五、中文字型（乾淨的 Linux 會是滿畫面豆腐字）"
if ! command -v fc-list >/dev/null 2>&1; then
  warn "這台沒有 fc-list，量不到字型（＝沒量到，不是量到 0）：sudo apt install fontconfig"
else
  N=$(fc-list :lang=zh 2>/dev/null | wc -l)
  if [ "$N" -eq 0 ]; then
    bad "一個中文字型都沒有 ⇒ 電視與手機會整頁豆腐字：sudo apt install fonts-noto-cjk"
  else
    ok "中文字型 $N 個"
    for f in "Noto Serif CJK TC" "Noto Sans CJK TC"; do
      fc-list | grep -qi "${f#Noto }" || warn "找不到 ${f}（電視的字型堆疊點名要 serif 那一支）"
    done
    fc-list :lang=zh | grep -qi "bold" \
      || warn "只有 Regular 沒有 Bold：大標會是合成粗體（能看，但不是設計的樣子）"
  fi
fi

head_ "六、零外網（展場不能假設有網路）"
if command -v ss >/dev/null 2>&1; then
  OUT=$(ss -tanp 2>/dev/null | awk 'NR>1 && $5 !~ /127\.0\.0\.1|\[::1\]/ && $1=="ESTAB"' | wc -l)
  [ "$OUT" -eq 0 ] && ok "現在沒有任何非 loopback 的連線" \
    || warn "有 $OUT 條對外連線（可能是瀏覽器自己在連，不一定是展件）"
else
  warn "沒有 ss，數不到連線"
fi
grep -rlE "^\s*(import|from)\s+(urllib|requests|httpx)" \
  "$(dirname "$0")"/serve_twin.py "$(dirname "$0")"/to_events.py 2>/dev/null \
  | grep -q . && bad "serve_twin/to_events 匯入了對外連線的模組" \
  || ok "serve_twin／to_events 沒有匯入 urllib／requests／httpx"

head_ "七、/control 的門檻（--lan 的時候這是展場現實）"
# ⚠ 這一節在 2026-09-19 從「warn」升成「硬傷」：`--lan` 現在**一定**會有 token
#   （自動生），所以綁在 0.0.0.0 卻按得動＝有人明講了 `--no-token`，
#   那是一個決定，不是一個預設，要在布展當天被擋下來重新確認。
LISTEN=$(ss -ltn 2>/dev/null | grep ":$TWIN_PORT" | awk '{print $4}' | head -1)
case "$LISTEN" in
  0.0.0.0*|\[::\]*|\*:*)
    R=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 8 -X POST \
        -H 'content-type: application/json' -d '{"action":"next"}' "$B/control" 2>/dev/null)
    if [ "$R" = "403" ]; then
      ok "綁在 ${LISTEN}，沒帶 token → 403（門檻在）"
    else
      bad "綁在 $LISTEN 而且**按得動**（回 ${R}）：同一個區網上任何人都按得動這台電視"
      bad "  ⇒ 去掉 --no-token，或改用只有展場手機連得到的獨立熱點"
    fi
    # 電視拿不拿得到 token（拿不到＝QR 沒有 token＝全場一顆鍵都按不動）。
    # 電視在這台機器上，所以從這裡打就是電視的視角——這一條量得到。
    MINE=$(curl -sS --max-time 8 "$B/state" 2>/dev/null \
           | python3 -c 'import json,sys;print(json.load(sys.stdin).get("phone_url",""))' \
             2>/dev/null || echo "?")
    case "$MINE" in
      *"t="*) ok "電視這一端的 phone_url 帶著 token（QR 掃進去按得動）" ;;
      "?"|"") warn "讀不到 /state 的 phone_url，沒量到電視拿不拿得到 token" ;;
      *)      bad "有 token 但電視這一端的 phone_url **沒有帶**（${MINE}）"
              bad "  ⇒ QR 掃進去是沒有 token 的網址，全場三顆鍵都按不動" ;;
    esac
    # ⚠ 「token 會不會外流給區網上的其他人」**這台機器量不到**。
    #   判準是「對端位址＝本端位址」（serve_twin docstring §4），而從這台機器
    #   打自己的區網位址，對端就是本端 ⇒ 一定拿得到 token。
    #   要量得換一台裝置。**沒量到不是量到 0**（鐵律 3）。
    warn "「token 會不會外流給區網上的其他人」沒量到：這台機器量不到（對端＝本端）"
    warn "  要量：拿另一台連同一個網路的裝置跑"
    warn "  curl -s http://$HOST:$TWIN_PORT/state | grep -o 'phone_url[^,]*'"
    warn "  看得到 t= 就是外流了（那代表 token 只是一個 GET 的距離）" ;;
  *) ok "只綁 ${LISTEN}（手機連不到；展場要手機互動才需要 --lan）" ;;
esac
fi   # ONLY_TWIN

# ── 八、數位分身那一條線（手機 → 公網 → twinstore → 1003 → 螢幕）──────
#
# 🔴 這一節量的是**兩件不同的事**，不可以混成一件：
#
#   (A) `twinlink serve` 的唯讀端點活著嗎（電視 `&twin=` 指的那一台）。
#   (B) `twinlink loop` 還在寫快照嗎（`world3/live/visitors.json`）。
#
# ⚠ **(A) 量不到 (B)。** serve 的 `/visitors.json` 每次都是現算的，
#   它的 `generated_at` 永遠是**這一次請求的時間** ⇒ 拿它判新鮮度會永遠是綠的。
#   loop 死掉的「靜默降級」只有從那個**落盤快照**看得出來，因為那個欄位
#   記的是 `export` 跑的時刻。這一段以前零觀測。
#
# ⚠ **`generated_at: null` 不是「0 分鐘前」**，是「沒有東西寫過它」
#   （commit 進 vacant_hm 的佔位檔就長這樣）。兩者不可以同形。
if [ "$SKIP_TWIN" = "1" ]; then
  head_ "八、數位分身"
  warn "--skip-twin：整條分身線沒量（＝沒量到，不是量到沒問題）"
else
  head_ "八、數位分身：唯讀端點（電視 &twin= 指的那一台）"
  SB="http://$HOST:$STORE_PORT"
  c=$(code "$SB/visitors.json")
  if [ "$c" = "200" ]; then
    ok "/visitors.json → 200"
  else
    bad "/visitors.json → ${c}（twinlink serve 沒起來 ⇒ 電視的 &twin= 是死的）"
    bad "  ⇒ 開機腳本要帶 --store-port ${STORE_PORT}；手動起：twinlink.py serve --port ${STORE_PORT}"
  fi

  # 🔴 負控制：一個「什麼都回 200」的東西跟一個真的 twinlink serve，
  #    在上面那一條裡長得一模一樣。這一條逼它證明自己會說不。
  cn=$(code "$SB/definitely-not-a-route")
  if [ "$c" = "200" ]; then
    [ "$cn" = "404" ] && ok "負控制：/definitely-not-a-route → 404（它真的在路由，不是什麼都回 200）" \
      || bad "負控制壞了：不存在的路徑回 ${cn} 不是 404 ⇒ 上面那個 200 不算數"
  fi

  # counts.visitors 讀得到嗎（200 不等於形狀對）
  if [ "$c" = "200" ]; then
    NV=$(curl -sS --max-time 8 "$SB/visitors.json" 2>/dev/null | python3 -c '
import json,sys
d=json.load(sys.stdin)
n=(d.get("counts") or {}).get("visitors")
print(n if isinstance(n,int) and not isinstance(n,bool) else "x")' 2>/dev/null || echo x)
    # ⚠ `${NV}` 的大括號不是風格。bash 3.2（macOS 的 /bin/bash）在 `$NV（`
    #   這種寫法下會把全形括號的第一個 byte 吃進變數名 ⇒ `set -u` 當場
    #   `unbound variable` 把整支打死。這支腳本別的地方早就都寫 `${c}`。
    [ "$NV" != "x" ] && ok "counts.visitors 讀得到：${NV}（庫裡目前幾個人）" \
      || bad "counts.visitors 讀不到 ⇒ 回的東西形狀不對，電視會把這一層判成失敗"
  fi

  head_ "八之二、快照還在被寫嗎（loop 活著沒有？靜默降級就是在這裡看）"
  # 這個判準自己要先被驗過。`age_verdict` 吃一段 JSON，吐 `狀態 分鐘數`：
  #   fresh／stale／null（沒有東西寫過）／unparsable。
  age_verdict() {   # stdin = JSON
    python3 -c '
import json,sys
from datetime import datetime, timezone
lim=float(sys.argv[1])
try: d=json.load(sys.stdin)
except Exception: print("unparsable null"); raise SystemExit(0)
g=d.get("generated_at")
if g is None: print("null null"); raise SystemExit(0)
try:
    t=datetime.fromisoformat(str(g).replace("Z","+00:00"))
    if t.tzinfo is None: t=t.replace(tzinfo=timezone.utc)
except Exception: print("unparsable null"); raise SystemExit(0)
age=(datetime.now(timezone.utc)-t).total_seconds()/60.0
print(("fresh" if age<=lim else "stale"), round(age,1))
' "$1"
  }
  # 🔴 量具自己的負控制。三個必中的輸入；有一個不對就整節作廢——
  #    「判成 0 之前先證明量得動」。
  NC_OK=1
  [ "$(printf '{"generated_at":"1970-01-01T00:00:00Z"}' | age_verdict "$TWIN_MAX_AGE_MIN" | awk '{print $1}')" = "stale" ] || NC_OK=0
  [ "$(printf '{"generated_at":null}'                   | age_verdict "$TWIN_MAX_AGE_MIN" | awk '{print $1}')" = "null" ]  || NC_OK=0
  [ "$(printf 'not json'                                | age_verdict "$TWIN_MAX_AGE_MIN" | awk '{print $1}')" = "unparsable" ] || NC_OK=0
  if [ "$NC_OK" = "1" ]; then
    ok "負控制：假的舊時間判 stale、null 判 null、壞 JSON 判 unparsable（尺量得動）"
  else
    bad "新鮮度這把尺自己壞了（負控制沒過）⇒ 下面那一條**不算數**"
  fi

  if [ "$SKIP_TV" = "1" ]; then
    warn "--skip-tv：拿不到 world3/live/visitors.json，快照新鮮度沒量到（不是量到 0）"
  elif [ "$NC_OK" = "1" ]; then
    SNAP_URL="http://$HOST:$TV_PORT/world3/live/visitors.json"
    SNAP=$(curl -sS --max-time 8 "$SNAP_URL" 2>/dev/null)
    if [ -z "$SNAP" ]; then
      bad "拿不到 $SNAP_URL ⇒ 電視 snapshot 那一層是死的（檔不在？靜態站沒起來？）"
    else
      V=$(printf '%s' "$SNAP" | age_verdict "$TWIN_MAX_AGE_MIN")
      case "${V%% *}" in
        fresh) ok "快照 ${V##* } 分鐘前寫的（loop 活著）" ;;
        stale) bad "快照 ${V##* } 分鐘前就停了（上限 ${TWIN_MAX_AGE_MIN} 分）⇒ loop 死了或打不到公網"
               bad "  ⇒ systemctl status vacant-twin-loop.service；journalctl -u vacant-twin-loop -n 40" ;;
        null)  bad "快照的 generated_at 是 **null** ⇒ 從來沒有東西寫過它"
               bad "  那是 commit 進 vacant_hm 的空佔位檔。**不是「0 個觀眾」，是這條線沒接上**。"
               bad "  ⇒ 起 vacant-twin-loop.service（要 VACANT_TWIN_CLOUD_TOKEN），或明講 --skip-twin" ;;
        *)     bad "快照的 generated_at 解不開 ⇒ 形狀不對，電視會讀到一份自己看不懂的東西" ;;
      esac
    fi
  fi
fi

head_ "結果"
if [ "$FAIL" -gt 0 ]; then
  printf "  \033[31m%d 條硬傷、%d 條要注意 ⇒ 還不能開展\033[0m\n" "$FAIL" "$WARN"
  exit 1
fi
printf "  \033[32m硬傷 0 條、%d 條要注意\033[0m\n" "$WARN"
echo "  ⚠ 這一支證明的是「端點活著、輪播在動、字型在、分身快照還在被寫」。"
echo "    它**沒有**驗簽章，也沒有看畫面長什麼樣——那要人真的站到電視前面看一眼。"
echo "    它也**沒有**證明電視真的去讀了 &twin=（那要開瀏覽器）；"
echo "    它證明的是那個端點在、快照是新的。兩件事不要混講。"
exit 0
