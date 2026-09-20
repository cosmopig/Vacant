#!/usr/bin/env bash
# e2e_1003.sh — 「1003 去存取他」那一段的實跑（人類 2026-09-20 原話）。
#
# 跟 `e2e_twinchain.sh` 的差別：那一支全部跑在 Mac 上，只有模型呼叫打到 1003。
# 這一支**把真相來源本身放到 1003 上**，由 1003 自己 ingest、自己 generate
# （打它自己的 `127.0.0.1:1234`，不經過網路）、自己驗鏈、自己 export。
#
# 為什麼這才是人類要的：展場那台如果就是算力那台，整條鏈**只剩一個外部相依**
# ——觀眾手機投稿那一段。其他全部在機殼裡面，拔網路線照跑。
#
# ⚠ `ssh 1003` 這個別名會解析到假位址 0.0.3.235（量具說謊紀錄），**一律用 IP**。
set -u

WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CLOUD_REPO="${CLOUD_REPO:-/Users/cosmopig/Documents/GitHub/vacant-world-cloud}"
PY="${PY:-/Users/cosmopig/Documents/GitHub/Vacant/.venv/bin/python}"
OUT="${OUT:-$WT/ops/exhibit/twin/evidence_1003_20260920}"
PORT="${PORT:-3398}"
TOKEN="${TOKEN:-e2e-1003-token}"
MAC_TS_IP="${MAC_TS_IP:-100.66.177.25}"
R="${R:-w401@100.119.113.56}"
#: ⚠ **1003 有兩套路徑，不可以混用。**
#:   `ssh` 進去是 MSYS bash ⇒ `/c/Users/...`；
#:   `scp` 走的是 **Windows 的 SFTP 子系統** ⇒ 要 `C:/Users/...`。
#:   混用的症狀是 `scp: remote mkdir ...: No such file or directory`，
#:   而 `ssh mkdir` 明明成功——看起來像權限問題，其實是路徑方言問題。
RDIR="${RDIR:-/c/Users/w401/vacant_twin}"
RDIR_SCP="${RDIR_SCP:-C:/Users/w401/vacant_twin}"
RPY="${RPY:-python}"

rm -rf "$OUT"; mkdir -p "$OUT"
DATA="$OUT/clouddata"; mkdir -p "$DATA"
CLOUD="http://$MAC_TS_IP:$PORT"

PASS=0; FAIL=0
step() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
ok()   { PASS=$((PASS+1)); echo "  [OK] $*"; }
bad()  { FAIL=$((FAIL+1)); echo "  [紅] $*"; }
chk()  { if [ "$1" = "$2" ]; then ok "$3（得 $1）"; else bad "$3（期望 $2，實得 $1）"; fi; }
# PYTHONIOENCODING：Windows console 預設是 cp950，中文輸出會變亂碼，
# 證據檔看不懂就等於沒有證據。
# ⚠ 要 `export ...;` 不能寫 `PYTHONIOENCODING=utf-8 $*`：後者只套用到
#   `$*` 的**第一個**指令，而我們常常送 `cd X && python ...`——
#   結果變數餵給了 `cd`，python 還是 cp950，中文照樣亂碼。
rr()   { ssh -o BatchMode=yes -o ConnectTimeout=25 "$R" "export PYTHONIOENCODING=utf-8; $*"; }
rraw() { ssh -o BatchMode=yes -o ConnectTimeout=25 "$R" "$@"; }

echo "證據目錄：$OUT"
date -u +"UTC %Y-%m-%dT%H:%M:%SZ" | tee "$OUT/00_started.txt"

# ---------------------------------------------------------------------------
step "0. 量具先證明量得動（必中的輸入）"
# ---------------------------------------------------------------------------
HN=$(rr 'hostname' 2>/dev/null | tr -d '\r')
chk "$HN" "w401c-16" "SSH 到 1003 通"
rr "$RPY -c \"import sqlite3,sys;print(sys.version.split()[0],sqlite3.sqlite_version)\"" \
   > "$OUT/01_remote_python.txt" 2>&1
cat "$OUT/01_remote_python.txt"
if grep -qE '^3\.' "$OUT/01_remote_python.txt"; then ok "1003 有 python3 ＋ sqlite3"; else bad "1003 python 探測失敗"; fi

# 1003 自己看得到自己的 LM Studio 嗎（這一段不經過網路）
rr 'curl -sS --max-time 15 http://127.0.0.1:1234/v1/models' \
   > "$OUT/02_remote_lms.json" 2>&1
if grep -q "gemma" "$OUT/02_remote_lms.json"; then
  ok "1003 從自己的 127.0.0.1:1234 讀得到模型（機殼內，不經網路）"
else
  bad "1003 本機 LM Studio 探測失敗"; cat "$OUT/02_remote_lms.json"
fi

# ---------------------------------------------------------------------------
step "1. 佈到 1003"
# ---------------------------------------------------------------------------
rr "mkdir -p $RDIR/ops/exhibit/twin $RDIR/store" 2>&1
scp -q -o BatchMode=yes "$WT/ops/exhibit/twin/twinstore.py" \
    "$R:$RDIR_SCP/ops/exhibit/twin/twinstore.py" 2>&1
S1=$?
scp -q -o BatchMode=yes "$WT/ops/exhibit/twin/twinlink.py" \
    "$R:$RDIR_SCP/ops/exhibit/twin/twinlink.py" 2>&1
S2=$?
chk "$((S1+S2))" "0" "兩支 .py 傳過去了"
rr "ls -la $RDIR/ops/exhibit/twin/" > "$OUT/03b_remote_ls.txt" 2>&1
grep -c "\.py" "$OUT/03b_remote_ls.txt" | xargs -I{} echo "  1003 上有 {} 個 .py"
rr "cd $RDIR && $RPY ops/exhibit/twin/twinlink.py selftest" \
   > "$OUT/03_remote_selftest.txt" 2>&1
RC=$?
tail -3 "$OUT/03_remote_selftest.txt"
chk "$RC" "0" "1003 上的 selftest 全綠（含 5 個負控制）"

# ---------------------------------------------------------------------------
step "2. 起 Mac 上的雲端替身（Tailscale 上，讓 1003 連得到）"
# ---------------------------------------------------------------------------
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "拒絕啟動：埠 $PORT 已經有人在聽"; lsof -nP -iTCP:"$PORT" -sTCP:LISTEN; exit 2
fi
cd "$CLOUD_REPO" || exit 1
PORT="$PORT" VENUE_TOKEN="$TOKEN" DATA_DIR="$DATA" \
    node server.js > "$OUT/04_cloud_boot.log" 2>&1 &
CLOUD_PID=$!
cd "$WT" || exit 1
sleep 2
cleanup() { [ -n "${CLOUD_PID:-}" ] && { kill "$CLOUD_PID" 2>/dev/null; wait "$CLOUD_PID" 2>/dev/null; CLOUD_PID=""; }; }
trap cleanup EXIT
cat "$OUT/04_cloud_boot.log"

# 🔴 負控制：1003 用錯 token 必須被擋
RC=$(rr "curl -sS -o /dev/null -w '%{http_code}' --max-time 15 '$CLOUD/api/all?token=WRONG'" 2>/dev/null | tr -d '\r')
chk "$RC" "401" "1003 用錯 token 打 /api/all 被擋"

# ---------------------------------------------------------------------------
step "3. 觀眾投卡（從 Mac 打，模擬手機）"
# ---------------------------------------------------------------------------
: > "$OUT/05_ids.txt"
sub() {
  curl -sS -X POST "http://127.0.0.1:$PORT/api/submit" \
       -H 'Content-Type: application/json' --data-binary "$1" 2>&1 \
  | "$PY" -c 'import sys,json;print(json.load(sys.stdin)["id"])' >> "$OUT/05_ids.txt"
}
sub '{"card_text":"需求：把家裡的書按顏色排一次\n形狀：厚實　質感：斑駁　色系：赭紅\n氣質：懶散、固執、有點浪漫\n第一句話：排完應該會很好看吧。"}'
sleep 11
sub '{"card_text":"需求：幫我想一句可以貼在冰箱上的話\n形狀：修長　質感：光滑　色系：奶油\n氣質：溫柔、慢熱、愛觀察\n第一句話：我今天想說點好聽的。"}'
chk "$(wc -l < "$OUT/05_ids.txt" | tr -d ' ')" "2" "兩張卡收下了"

# ---------------------------------------------------------------------------
step "4. 🔴 1003 自己去存取它：ingest → 自己的 SQLite"
# ---------------------------------------------------------------------------
RDB="$RDIR/store/twinstore.sqlite3"
# ⚠ **第三種路徑方言。** MSYS bash 會把「裸的」`/c/...` 參數自動轉成 `C:\...`
#   交給原生 Windows 程式——所以 `--db /c/Users/...` 是通的。
#   但**寫在字串字面值裡面的路徑不會被轉**，於是
#   `python -c "sqlite3.connect('/c/Users/...')"` 會 `unable to open database file`。
#   第一版就是這樣：CLI 那幾步全綠、inline python 那兩步全紅，看起來像權限問題。
RDB_WIN="${RDIR_SCP}/store/twinstore.sqlite3"
rr "rm -f '$RDB' '$RDB-wal' '$RDB-shm'" 2>&1
rr "cd $RDIR && $RPY ops/exhibit/twin/twinlink.py --db '$RDB' ingest --cloud '$CLOUD' --token '$TOKEN'" \
   > "$OUT/06_remote_ingest.json" 2>&1
cat "$OUT/06_remote_ingest.json"
P=$("$PY" -c "
import json,re
t=open('$OUT/06_remote_ingest.json').read()
m=re.search(r'\{.*\}',t,re.S)
print(json.loads(m.group(0))['pulled'] if m else 'PARSE_FAIL')")
chk "$P" "2" "1003 抄進自己的 SQLite 2 筆"

# 資料庫確實在 1003 的磁碟上，不是在 Mac 上
rr "ls -la '$RDB' && $RPY -c \"import sqlite3;c=sqlite3.connect(r'$RDB_WIN');print('rows',c.execute('select count(*) from twin_event').fetchone()[0])\"" \
   > "$OUT/07_remote_db_on_disk.txt" 2>&1
cat "$OUT/07_remote_db_on_disk.txt"
if grep -q "rows 2" "$OUT/07_remote_db_on_disk.txt"; then
  ok "SQLite 檔實體在 1003 的磁碟上，裡面 2 列"
else
  bad "1003 上的 DB 檢查失敗"
fi

# ---------------------------------------------------------------------------
step "5. 🔴 1003 用自己的 GPU 生分身（端點 127.0.0.1，不出機殼）"
# ---------------------------------------------------------------------------
T0=$(date +%s)
# ⚠ `--timeout 300`：90 秒不夠（實測有一發 TimeoutError）。thinking 一發要
#   一萬多個 reasoning token，加上「被擠掉就升額重試」，最壞情況是好幾分鐘。
rr "cd $RDIR && $RPY ops/exhibit/twin/twinlink.py --db '$RDB' generate --endpoint http://127.0.0.1:1234/v1 --model gemma-4-12b-it-qat --timeout 300 --no-fallback" \
   > "$OUT/08_remote_generate.json" 2>&1
GRC=$?
T1=$(date +%s)
cat "$OUT/08_remote_generate.json"
echo "  兩隻分身共 $((T1-T0)) 秒"
chk "$GRC" "0" "1003 generate 退出碼（--no-fallback：退化就炸）"

# ---------------------------------------------------------------------------
step "6. 1003 自己驗鏈、自己 export"
# ---------------------------------------------------------------------------
rr "cd $RDIR && $RPY ops/exhibit/twin/twinstore.py --db '$RDB' verify" \
   > "$OUT/09_remote_verify.json" 2>&1
chk "$?" "0" "1003 上的雜湊鏈驗證通過"
cat "$OUT/09_remote_verify.json"

rr "cd $RDIR && $RPY ops/exhibit/twin/twinstore.py --db '$RDB' stats" \
   > "$OUT/10_remote_stats.json" 2>&1
cat "$OUT/10_remote_stats.json"

rr "cd $RDIR && $RPY ops/exhibit/twin/twinlink.py --db '$RDB' export --out '$RDIR/store/visitors.json'" \
   > "$OUT/11_remote_export.json" 2>&1
scp -q -o BatchMode=yes "$R:$RDIR_SCP/store/visitors.json" "$OUT/12_visitors_from_1003.json" 2>&1
chk "$?" "0" "把 1003 產出的 visitors.json 抓回來了"
"$PY" -c "
import json
v=json.load(open('$OUT/12_visitors_from_1003.json'))
print(json.dumps({'chain':v['chain'],'counts':v['counts']},ensure_ascii=False,indent=2))
for p in v['people']:
    print(f\"  · {(p['card'] or {}).get('need','?')[:20]:22} engine={p['engine']} {p['latency_ms']}ms\")
    print(f\"      抵達：{p['arrival']}\")
    print(f\"      動手：{p['working']}\")
    print(f\"      交付：{p['handover']}\")
"
E=$("$PY" -c "
import json;v=json.load(open('$OUT/12_visitors_from_1003.json'))
print(sum(1 for p in v['people'] if str(p['engine']).startswith('lmstudio:')))")
chk "$E" "2" "兩隻分身都是 1003 的真模型生的"

# ---------------------------------------------------------------------------
step "7. 1003 回寫雲端，觀眾手機看得到"
# ---------------------------------------------------------------------------
rr "cd $RDIR && $RPY ops/exhibit/twin/twinlink.py --db '$RDB' publish --cloud '$CLOUD' --token '$TOKEN'" \
   > "$OUT/13_remote_publish.json" 2>&1
cat "$OUT/13_remote_publish.json"
FIRST=$(head -1 "$OUT/05_ids.txt")
curl -sS "http://127.0.0.1:$PORT/api/status/$FIRST" -o "$OUT/14_visitor_status.json"
cat "$OUT/14_visitor_status.json"; echo
S=$("$PY" -c "import json;print(json.load(open('$OUT/14_visitor_status.json'))['status'])")
chk "$S" "done" "觀眾那一端看到 done（結果是 1003 回寫的）"

# ---------------------------------------------------------------------------
step "8. 🔴 append-only 負控制（在 1003 上跑，不是在 Mac 上）"
# ---------------------------------------------------------------------------
rr "cd $RDIR && $RPY -c \"
import sqlite3
c=sqlite3.connect(r'$RDB_WIN'); c.isolation_level=None
for sql in ('UPDATE twin_event SET source=\\\"hack\\\" WHERE seq=1',
            'DELETE FROM twin_event WHERE seq=1'):
    try:
        c.execute(sql); print('RED', sql.split()[0], 'NOT BLOCKED')
    except Exception as e:
        print('BLOCKED', sql.split()[0], '->', str(e)[:48])
\"" > "$OUT/15_remote_appendonly.txt" 2>&1
cat "$OUT/15_remote_appendonly.txt"
if [ "$(grep -c '^BLOCKED' "$OUT/15_remote_appendonly.txt")" = "2" ]; then
  ok "1003 上 UPDATE 與 DELETE 都被 trigger 擋下"
else
  bad "1003 上的 append-only 守衛沒生效"
fi

# 竄改 → verify 必須紅（在 1003 上的副本做）
# ⚠ 這一步第一版是**假綠**：inline python 因為路徑方言失敗 ⇒ 副本根本沒生成 ⇒
#   verify 對著不存在的檔案回 1 ⇒ `chk $? 1` 通過。**「紅」的原因不對，綠就不算數。**
#   所以現在分成兩段各自判：先確認副本竄改真的做成了，再看 verify 紅不紅。
rr "cd $RDIR && cp '$RDB' '$RDB.tamper' && $RPY -c \"
import sqlite3
c=sqlite3.connect(r'$RDB_WIN.tamper'); c.isolation_level=None
c.execute('PRAGMA writable_schema=ON')
c.execute(\\\"DELETE FROM sqlite_master WHERE type='trigger'\\\")
c.execute('PRAGMA writable_schema=OFF'); c.close()
c=sqlite3.connect(r'$RDB_WIN.tamper'); c.isolation_level=None
c.execute('UPDATE twin_event SET payload_json=\\\"{}\\\" WHERE seq=2'); c.close()
print('TAMPERED_OK')
\"" > "$OUT/16a_remote_tamper_prep.txt" 2>&1
if grep -q "TAMPERED_OK" "$OUT/16a_remote_tamper_prep.txt"; then
  ok "竄改副本真的做成了（不是因為檔案不存在才紅）"
else
  bad "竄改副本沒做成，下面那個紅不算數"; cat "$OUT/16a_remote_tamper_prep.txt"
fi
rr "cd $RDIR && $RPY ops/exhibit/twin/twinstore.py --db '$RDB.tamper' verify" \
   > "$OUT/16_remote_tamper.json" 2>&1
chk "$?" "1" "1003 上竄改後 verify 變紅"
cat "$OUT/16_remote_tamper.json"
if grep -q "broken_at" "$OUT/16_remote_tamper.json"; then
  ok "紅的原因是鏈對不上（有 broken_at），不是檔案打不開"
else
  bad "紅的原因不對"
fi
rr "rm -f '$RDB.tamper' '$RDB.tamper-wal' '$RDB.tamper-shm'" 2>&1

# ---------------------------------------------------------------------------
step "9. 斷網演練：Mac 的雲端關掉，1003 還能不能跑"
# ---------------------------------------------------------------------------
cleanup
DOWN=0
for _ in 1 2 3 4 5; do
  C=$(curl -sS --max-time 3 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/api/all" 2>/dev/null)
  if [ "$C" = "000" ] || [ -z "$C" ]; then DOWN=1; break; fi
  sleep 1
done
chk "$DOWN" "1" "Mac 上的雲端真的關了"

rr "cd $RDIR && $RPY ops/exhibit/twin/twinlink.py --db '$RDB' ingest --cloud '$CLOUD' --token '$TOKEN' --timeout 6" \
   > "$OUT/17_remote_offline_ingest.json" 2>&1
if grep -q '"pulled": null' "$OUT/17_remote_offline_ingest.json"; then
  ok "1003 抄不到時回 pulled=null 並記 ingest_gap"
else
  bad "1003 斷網 ingest 行為不對"; cat "$OUT/17_remote_offline_ingest.json"
fi

# 🔴 這一步是離線紅線的核心：雲端死了，1003 還生得出分身、還 export 得出畫面資料
rr "cd $RDIR && $RPY ops/exhibit/twin/twinlink.py --db '$RDB' export --out '$RDIR/store/visitors_offline.json'" \
   > "$OUT/18_remote_offline_export.json" 2>&1
scp -q -o BatchMode=yes "$R:$RDIR_SCP/store/visitors_offline.json" "$OUT/19_visitors_offline.json" 2>&1
N=$("$PY" -c "import json;print(len(json.load(open('$OUT/19_visitors_offline.json'))['people']))" 2>&1)
chk "$N" "2" "🔴 雲端掛掉，1003 那份現場資料還是兩個人（離線紅線）"

rr "cd $RDIR && $RPY ops/exhibit/twin/twinstore.py --db '$RDB' verify" \
   > "$OUT/20_remote_verify_final.json" 2>&1
chk "$?" "0" "斷網之後 1003 上的鏈還是綠的"

rr "cd $RDIR && $RPY ops/exhibit/twin/twinstore.py --db '$RDB' stats" \
   > "$OUT/21_remote_stats_final.json" 2>&1
cat "$OUT/21_remote_stats_final.json"

# 1003 上那條鏈的事件流本體，倒成人讀的 JSON 抓回來。
# **進版控的是這一份**（二進位 sqlite 留在 1003 上，刻意不刪也不搬）。
rr "cd $RDIR && $RPY ops/exhibit/twin/twinstore.py --db '$RDB' dump" \
   > "$OUT/22_remote_event_stream.json" 2>&1
echo "  1003 事件流已倒出：22_remote_event_stream.json（$(grep -c '"seq"' "$OUT/22_remote_event_stream.json") 列）"

printf '\n\033[1m===== 總計 =====\033[0m\n'
echo "通過 $PASS 項，失敗 $FAIL 項"
echo "證據：$OUT"
# ⚠ `${RDB}` 不能寫 `$RDB`：後面接全形「（」會被 bash 併進變數名，
#   `set -u` 之下直接 unbound variable。中文輸出踩得到這個。
echo "1003 上的真相來源：${R}:${RDB}（**刻意留著不刪**——資料不要刪除）"
date -u +"UTC %Y-%m-%dT%H:%M:%SZ" | tee "$OUT/99_finished.txt"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
