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
#   ./venue_check.sh                  檢查預設的 8420 / 8899
#   ./venue_check.sh --twin-port 8899 --tv-port 8420
#   ./venue_check.sh --skip-tv        只檢查展件伺服器
#
# 離開碼：0＝可以開展；1＝有硬傷（下面會逐條講是哪一條）。
set -uo pipefail

TV_PORT=8420
TWIN_PORT=8899
HOST=127.0.0.1
SKIP_TV=0
FAIL=0
WARN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --tv-port)   TV_PORT="$2"; shift ;;
    --twin-port) TWIN_PORT="$2"; shift ;;
    --host)      HOST="$2"; shift ;;
    --skip-tv)   SKIP_TV=1 ;;
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

head_ "結果"
if [ "$FAIL" -gt 0 ]; then
  printf "  \033[31m%d 條硬傷、%d 條要注意 ⇒ 還不能開展\033[0m\n" "$FAIL" "$WARN"
  exit 1
fi
printf "  \033[32m硬傷 0 條、%d 條要注意\033[0m\n" "$WARN"
echo "  ⚠ 這一支證明的是「端點活著、輪播在動、字型在」。"
echo "    它**沒有**驗簽章，也沒有看畫面長什麼樣——那要人真的站到電視前面看一眼。"
exit 0
