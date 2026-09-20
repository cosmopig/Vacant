#!/usr/bin/env bash
# e2e_twinchain.sh — 「手機 → 公網 → 資料庫 → 1003 → 螢幕」整條鏈一鍵實跑。
#
# 為什麼要一鍵：這條鏈跨三個 repo、兩台機器、四個行程。手動跑一次要打二十幾道
# 指令，而**沒有人會在開展前一天手動跑二十幾道指令**。
#
# 紀律（違反就不要看結果）：
#   * **先跑負控制**。第 0 步故意用錯 token、故意打不存在的埠，證明量具會紅。
#     沒有負控制的綠燈不算數。
#   * **不吞退出碼**。每一步自己判、自己記，不用 `| tail` 之類把 rc 吃掉。
#   * 「沒量到」寫 `null` 不寫 0。
#
# 用法：
#   bash ops/exhibit/twin/e2e_twinchain.sh                   # 本機雲端替身，全程離線可跑
#   REMOTE_1003=1 bash ops/exhibit/twin/e2e_twinchain.sh     # 加跑 1003 那一段
set -u

WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CLOUD_REPO="${CLOUD_REPO:-/Users/cosmopig/Documents/GitHub/vacant-world-cloud}"
PY="${PY:-/Users/cosmopig/Documents/GitHub/Vacant/.venv/bin/python}"
OUT="${OUT:-$WT/ops/exhibit/twin/evidence_twinchain_20260920}"
PORT="${PORT:-3399}"
TOKEN="${TOKEN:-e2e-local-token}"
MAC_TS_IP="${MAC_TS_IP:-100.66.177.25}"
GPU_1003="${GPU_1003:-100.119.113.56}"
SSH_1003="${SSH_1003:-w401@100.119.113.56}"
LMS="${LMS:-http://100.119.113.56:1234/v1}"
MODEL="${MODEL:-gemma-4-12b-it-qat}"
#: ⚠ 90 秒不夠。實測（2026-09-20）三張卡裡有一張在 1003 上 `TimeoutError`——
#: thinking 模式的一發要一萬多個 reasoning token，加上「被擠掉就升額重試」
#: 會讓最壞情況乘以 (1+ESCALATE_FACTOR)。1003 同時在跑別的東西時更慢。
GEN_TIMEOUT="${GEN_TIMEOUT:-300}"

# 整個證據目錄每一輪重生。**不可以只清一部分**：舊檔留著時，
# 下面那些 `json.load(開啟舊檔)` 會讀到上一輪的東西，或讀到兩份 JSON 疊在一起
# 而解析成空字串——比較的兩邊就都在說謊（實測踩過）。
rm -rf "$OUT"
mkdir -p "$OUT"
DATA="$OUT/clouddata"
DB="$OUT/twinstore.sqlite3"
mkdir -p "$DATA"

PASS=0; FAIL=0
step() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
ok()   { PASS=$((PASS+1)); echo "  [OK] $*"; }
bad()  { FAIL=$((FAIL+1)); echo "  [紅] $*"; }
chk()  { if [ "$1" = "$2" ]; then ok "$3（得 $1）"; else bad "$3（期望 $2，實得 $1）"; fi; }

# 每一步的原始輸出都落盤，報告裡引用的每個數字都指得回一個檔案。
#
# 🔴 **不可以寫成 `cmd | tee file` 然後 `chk "$?"`。** 管線的 `$?` 是 **tee** 的
#    退出碼，而 tee 幾乎永遠回 0——那個檢查會對任何失敗都說「通過」。
#    實測踩過兩次：一次是 generate 崩掉還印 `[OK] generate 退出碼（得 0）`，
#    一次是「雜湊鏈驗證通過」其實根本沒在看 verify 的退出碼。
#    所以改成先重導向落盤、取 `$?`、再 `cat`，退出碼由 `run` 原樣回傳。
# ⚠ 覆寫不是追加：追加會讓同一個檔裡疊兩份 JSON，解析出來是空的。
run() {
  local f="$1"; shift
  "$@" > "$OUT/$f" 2>&1
  local rc=$?
  cat "$OUT/$f"
  return $rc
}

echo "證據目錄：$OUT"
date -u +"UTC %Y-%m-%dT%H:%M:%SZ" | tee "$OUT/00_started.txt"

# ---------------------------------------------------------------------------
step "0. 起本機雲端替身（跟 Zeabur 上跑的是同一份 server.js）"
# ---------------------------------------------------------------------------
CLOUD="http://127.0.0.1:$PORT"

# 🔴 fail-closed：埠被佔就**拒絕啟動**，不要安靜地跑在別人的伺服器上。
#    實測踩過：第一輪的 node 變成孤兒還聽著 3399，第二輪起不來卻繼續往下跑，
#    整份結果都是對著**上一輪的殘留狀態**量的（submitted 從 3 變 6、
#    「斷網演練」curl 回 200）。安靜跑錯比拒絕啟動危險得多。
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "拒絕啟動：埠 $PORT 已經有人在聽。先確認那是什麼："
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN
  echo "（若是上一輪的殘留，確認 PID 後自己 kill；本腳本不替你殺不是自己起的行程）"
  exit 2
fi

# ⚠ **不要**寫成 `( cd X && node server.js & echo $! )`：那樣 `$!` 拿到的是
#   subshell 的 PID，不是 node 的。第一版就是這樣寫的，結果「斷網演練」那一步
#   把 subshell 殺掉、node 還活著，curl 照樣回 200——**演練是假的**。
#   （是第 8 步的檢查把它抓出來的；沒有那個檢查我就會寫一份說謊的報告。）
cd "$CLOUD_REPO" || exit 1
PORT="$PORT" VENUE_TOKEN="$TOKEN" DATA_DIR="$DATA" \
    node server.js > "$OUT/01_cloud_boot.log" 2>&1 &
CLOUD_PID=$!
cd "$WT" || exit 1
sleep 2
cat "$OUT/01_cloud_boot.log"
if grep -q "backend=" "$OUT/01_cloud_boot.log"; then
  ok "雲端起來了，事件流 backend 有印出來（不用猜）"
else
  bad "雲端沒起來或沒印 backend"
fi

# 「連得上」的判準：curl 的 http_code。連線被拒時是 000，401 也算連得上。
cloud_up() {
  local c
  c=$(curl -sS --max-time 3 -o /dev/null -w '%{http_code}' \
      "$CLOUD/api/all" 2>/dev/null)
  [ "$c" != "000" ] && [ -n "$c" ]
}

cleanup() {
  # 只殺我自己起的那一個 PID。
  if [ -n "${CLOUD_PID:-}" ]; then
    kill "$CLOUD_PID" 2>/dev/null
    wait "$CLOUD_PID" 2>/dev/null
    CLOUD_PID=""
  fi
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
step "0b. 🔴 負控制先跑：量具必須會紅"
# ---------------------------------------------------------------------------
RC=$(curl -sS -o "$OUT/02_neg_badtoken.json" -w '%{http_code}' \
     "$CLOUD/api/all?token=definitely-wrong" 2>/dev/null)
chk "$RC" "401" "錯 token 打 /api/all 被擋"

RC=$(curl -sS -o "$OUT/02_neg_notoken.json" -w '%{http_code}' \
     "$CLOUD/api/all" 2>/dev/null)
chk "$RC" "401" "沒帶 token 打 /api/all 被擋"

RC=$(curl -sS -o "$OUT/02_neg_pii.json" -w '%{http_code}' -X POST \
     "$CLOUD/api/submit" -H 'Content-Type: application/json' \
     -d '{"card_text":"需求：找我 a@b.com"}' 2>/dev/null)
chk "$RC" "422" "含 email 的卡被擋（個資不上牆）"

"$PY" "$WT/ops/exhibit/twin/twinlink.py" --db "$DB" ingest \
    --cloud "http://127.0.0.1:1" --token x --timeout 3 \
    > "$OUT/02_neg_offline_ingest.json" 2>&1
if grep -q '"pulled": null' "$OUT/02_neg_offline_ingest.json"; then
  ok "雲端不通時 ingest 回 pulled=null（不是 0）"
else
  bad "斷線 ingest 沒回 null"; cat "$OUT/02_neg_offline_ingest.json"
fi
rm -f "$DB" "$DB-wal" "$DB-shm"   # 負控制弄髒的庫不要帶進正式跑

# ---------------------------------------------------------------------------
step "1. 觀眾手機投卡（三張，模擬三位觀眾）"
# ---------------------------------------------------------------------------
: > "$OUT/03_submitted_ids.txt"
submit() {
  local body="$1"
  local r
  r=$(curl -sS -X POST "$CLOUD/api/submit" -H 'Content-Type: application/json' \
      --data-binary "$body" 2>&1)
  echo "$r" >> "$OUT/03_submit_raw.jsonl"
  echo "$r" | "$PY" -c 'import sys,json; print(json.load(sys.stdin)["id"])' \
      >> "$OUT/03_submitted_ids.txt"
}
submit '{"card_text":"需求：把散在桌上的收據整理成一份清單\n形狀：圓潤　質感：指紋　色系：暖土\n氣質：慢、固執、愛乾淨\n第一句話：這裡的光有點暖。"}'
sleep 11   # 同 IP 10 秒 1 筆的頻率限制是真的，不繞過
submit '{"card_text":"需求：幫我把一週的開銷加總起來\n形狀：方正　質感：光滑　色系：灰藍\n氣質：精準、安靜、不多話\n第一句話：數字不會騙人。"}'
sleep 11
submit '{"card_text":"需求：找出清單裡重複的名字\n形狀：小巧　質感：絨面　色系：苔綠\n氣質：好奇、跳躍、愛問為什麼\n第一句話：咦，這個我剛剛看過。"}'

N=$(wc -l < "$OUT/03_submitted_ids.txt" | tr -d ' ')
chk "$N" "3" "三張卡都收下了"
cat "$OUT/03_submitted_ids.txt"

# ---------------------------------------------------------------------------
step "2. 雲端 append-only 事件流有沒有真的在記"
# ---------------------------------------------------------------------------
curl -sS "$CLOUD/api/all?token=$TOKEN" -o "$OUT/04_api_all.json"
"$PY" -c "
import json,sys
d=json.load(open('$OUT/04_api_all.json'))
print(json.dumps({'total':d['total'],'eventlog':d['eventlog'],
                  'first_card':d['items'][0]['card']},ensure_ascii=False,indent=2))
"
EV=$("$PY" -c "import json;print(json.load(open('$OUT/04_api_all.json'))['eventlog']['events'])")
chk "$EV" "3" "雲端事件流有 3 列"
BK=$("$PY" -c "import json;print(json.load(open('$OUT/04_api_all.json'))['eventlog']['backend'])")
echo "  雲端事件流 backend＝$BK"
cp "$DATA/events.jsonl" "$OUT/04_cloud_events.jsonl" 2>/dev/null

# 🔴 負控制：雲端的 SQLite 也要擋得住 UPDATE
if [ "$BK" = "sqlite" ]; then
  sqlite3 "$DATA/cloud.sqlite3" "UPDATE cloud_event SET kind='駭' WHERE seq=1;" \
      > "$OUT/04_neg_cloud_update.txt" 2>&1
  if grep -q "append-only" "$OUT/04_neg_cloud_update.txt"; then
    ok "雲端 cloud_event 的 UPDATE 被 trigger 擋下"
  else
    bad "雲端 UPDATE 沒被擋"; cat "$OUT/04_neg_cloud_update.txt"
  fi
else
  echo "  （backend 不是 sqlite，跳過這個負控制——不是通過，是沒跑）"
fi

# ---------------------------------------------------------------------------
step "3. ingest：雲端 → 本機 append-only 真相來源"
# ---------------------------------------------------------------------------
run 05_ingest.json "$PY" "$WT/ops/exhibit/twin/twinlink.py" --db "$DB" ingest \
    --cloud "$CLOUD" --token "$TOKEN"
P=$("$PY" -c "import json;print(json.load(open('$OUT/05_ingest.json'))['pulled'])")
chk "$P" "3" "抄進本機 3 筆"
M=$("$PY" -c "import json;print(json.load(open('$OUT/05_ingest.json'))['mode'])")
chk "$M" "all" "走的是唯讀不漏件的 /api/all（不是會漏的 queue）"

# 冪等：再抄一次不該多出東西
run 05b_ingest_again.json "$PY" "$WT/ops/exhibit/twin/twinlink.py" --db "$DB" ingest \
    --cloud "$CLOUD" --token "$TOKEN"
P2=$("$PY" -c "import json;print(json.load(open('$OUT/05b_ingest_again.json'))['pulled'])")
chk "$P2" "0" "重跑 ingest 不會重覆抄（0 是真的量到零，不是沒量）"

# ---------------------------------------------------------------------------
step "4. generate：1003 的真模型生分身（不准偷偷退化）"
# ---------------------------------------------------------------------------
echo "  端點 $LMS  模型 $MODEL"
curl -sS --max-time 20 "$LMS/models" -o "$OUT/06_lms_models.json" 2>&1
if grep -q "$MODEL" "$OUT/06_lms_models.json"; then
  ok "1003 的 LM Studio 活著而且載著 $MODEL"
else
  bad "1003 的模型清單裡找不到 $MODEL"; cat "$OUT/06_lms_models.json"
fi

T0=$(date +%s)
# ⚠ `X | log f` 之後的 `$?` 是 **tee** 的退出碼，不是 python 的——tee 幾乎永遠回 0。
#   實測踩過：python 以 TimeoutError 崩掉，這一行還是印 `[OK] generate 退出碼（得 0）`。
#   要用 `${PIPESTATUS[0]}`，而且要在**下一道指令之前**取。
run 07_generate.json "$PY" "$WT/ops/exhibit/twin/twinlink.py" --db "$DB" generate \
    --endpoint "$LMS" --model "$MODEL" --timeout "$GEN_TIMEOUT" --no-fallback
GRC=$?
T1=$(date +%s)
echo "  三隻分身共花 $((T1-T0)) 秒"
chk "$GRC" "0" "generate 退出碼"
G=$("$PY" -c "import json;print(json.load(open('$OUT/07_generate.json'))['generated'])")
chk "$G" "3" "生了 3 隻分身"
D=$("$PY" -c "import json;print(json.load(open('$OUT/07_generate.json'))['degraded'])")
chk "$D" "0" "0 隻是退化的（--no-fallback 之下退化會直接炸）"

# ---------------------------------------------------------------------------
step "5. publish：回寫雲端，觀眾手機看得到"
# ---------------------------------------------------------------------------
run 08_publish.json "$PY" "$WT/ops/exhibit/twin/twinlink.py" --db "$DB" publish \
    --cloud "$CLOUD" --token "$TOKEN"
PB=$("$PY" -c "import json;print(json.load(open('$OUT/08_publish.json'))['published'])")
chk "$PB" "3" "3 筆回寫成功"

FIRST=$(head -1 "$OUT/03_submitted_ids.txt")
curl -sS "$CLOUD/api/status/$FIRST" -o "$OUT/09_visitor_status.json"
echo "  觀眾手機輪詢自己那一筆："
cat "$OUT/09_visitor_status.json"; echo
S=$("$PY" -c "import json;print(json.load(open('$OUT/09_visitor_status.json'))['status'])")
chk "$S" "done" "觀眾那一端看到 done"

# ---------------------------------------------------------------------------
step "6. export：現場螢幕讀得到的本機 JSON"
# ---------------------------------------------------------------------------
run 10_export.json "$PY" "$WT/ops/exhibit/twin/twinlink.py" --db "$DB" export \
    --out "$OUT/10_visitors.json"
"$PY" -c "
import json
v=json.load(open('$OUT/10_visitors.json'))
print(json.dumps({'chain':v['chain'],'counts':v['counts']},ensure_ascii=False,indent=2))
for p in v['people']:
    print(f\"  · {p['card'].get('need','?')[:22]:24} engine={p['engine']}\")
    print(f\"      抵達：{p['arrival']}\")
    print(f\"      動手：{p['working']}\")
    print(f\"      交付：{p['handover']}\")
"
ENG=$("$PY" -c "
import json;v=json.load(open('$OUT/10_visitors.json'))
print(sum(1 for p in v['people'] if str(p['engine']).startswith('lmstudio:')))")
chk "$ENG" "3" "三隻分身的 engine 都是真模型（不是 fallback）"

# ---------------------------------------------------------------------------
step "7. 真相來源驗鏈＋append-only 負控制"
# ---------------------------------------------------------------------------
run 11_verify.json "$PY" "$WT/ops/exhibit/twin/twinstore.py" --db "$DB" verify
chk "$?" "0" "雜湊鏈驗證通過（這次真的在看 verify 的退出碼）"
run 11b_stats.json "$PY" "$WT/ops/exhibit/twin/twinstore.py" --db "$DB" stats

# 事件流本體倒成人讀的 JSON。**進版控的是這一份**，不是二進位 sqlite 檔——
# 別人要稽核「到底追加了哪幾列」，讀得懂才算證據。
"$PY" "$WT/ops/exhibit/twin/twinstore.py" --db "$DB" dump \
    > "$OUT/11c_event_stream.json" 2>&1
echo "  事件流已倒出：11c_event_stream.json（$(grep -c '"seq"' "$OUT/11c_event_stream.json") 列）"

sqlite3 "$DB" "DELETE FROM twin_event WHERE seq=1;" > "$OUT/12_neg_delete.txt" 2>&1
if grep -q "append-only" "$OUT/12_neg_delete.txt"; then
  ok "本機真相來源的 DELETE 被擋（資料不要刪除＝可執行的，不是慣例）"
else
  bad "DELETE 沒被擋"; cat "$OUT/12_neg_delete.txt"
fi

# 竄改負控制在副本上做，不要弄髒證據本體
cp "$DB" "$OUT/tamper_copy.sqlite3"
sqlite3 "$OUT/tamper_copy.sqlite3" \
  "PRAGMA writable_schema=ON; DELETE FROM sqlite_master WHERE type='trigger'; PRAGMA writable_schema=OFF;" \
  >/dev/null 2>&1
sqlite3 "$OUT/tamper_copy.sqlite3" \
  "UPDATE twin_event SET payload_json='{\"x\":1}' WHERE seq=2;" >/dev/null 2>&1
"$PY" "$WT/ops/exhibit/twin/twinstore.py" --db "$OUT/tamper_copy.sqlite3" verify \
    > "$OUT/12_neg_tamper_verify.json" 2>&1
chk "$?" "1" "竄改過的副本 verify 變紅（退出碼 1）"

# ---------------------------------------------------------------------------
step "8. 斷網演練：拔掉雲端，現場還能不能跑"
# ---------------------------------------------------------------------------
cleanup   # 把雲端殺掉（這是我自己起的行程）
# 🔴 **要確認它真的死了才能宣稱斷網。** 「我送了 SIGTERM」不等於「它下線了」。
DOWN=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if cloud_up; then sleep 1; else DOWN=1; break; fi
done
curl -sS --max-time 5 -o /dev/null -w '%{http_code}' "$CLOUD/api/all?token=$TOKEN" \
    > "$OUT/13_cloud_down.txt" 2>&1
chk "$DOWN" "1" "雲端真的下線了（curl http_code=$(cat "$OUT/13_cloud_down.txt")，000＝連不上）"

"$PY" "$WT/ops/exhibit/twin/twinlink.py" --db "$DB" ingest \
    --cloud "$CLOUD" --token "$TOKEN" --timeout 5 > "$OUT/14_offline_ingest.json" 2>&1
if grep -q '"pulled": null' "$OUT/14_offline_ingest.json"; then
  ok "斷網 ingest 回 null 並記了一列 ingest_gap"
else
  bad "斷網 ingest 行為不對"; cat "$OUT/14_offline_ingest.json"
fi

"$PY" "$WT/ops/exhibit/twin/twinlink.py" --db "$DB" export \
    --out "$OUT/15_visitors_offline.json" > "$OUT/15_export_offline.json" 2>&1
OFFN=$("$PY" -c "import json;print(len(json.load(open('$OUT/15_visitors_offline.json'))['people']))")
chk "$OFFN" "3" "🔴 雲端掛掉，現場螢幕那份 JSON 還是三個人（離線紅線）"

GAPS=$("$PY" -c "import json;print(json.load(open('$OUT/15_visitors_offline.json'))['counts']['gaps'])")
# ⚠ 一定要 `${GAPS}` 不能 `$GAPS`：後面接的全形「（」會被 bash 當成變數名的一部分，
#   `set -u` 之下直接 unbound variable 炸掉。中文註解跟中文輸出都踩得到這個。
echo "  漏收計數 gaps=${GAPS}（斷網留痕，不是靜靜當沒事）"
if [ "${GAPS}" -ge 1 ]; then
  ok "斷網有留痕（ingest_gap ≥ 1）"
else
  bad "斷網竟然沒留痕"
fi

"$PY" "$WT/ops/exhibit/twin/twinstore.py" --db "$DB" verify > "$OUT/16_verify_final.json" 2>&1
chk "$?" "0" "斷網之後鏈還是綠的"

# ---------------------------------------------------------------------------
printf '\n\033[1m===== 總計 =====\033[0m\n'
echo "通過 $PASS 項，失敗 $FAIL 項"
echo "證據：$OUT"
date -u +"UTC %Y-%m-%dT%H:%M:%SZ" | tee "$OUT/99_finished.txt"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
