#!/usr/bin/env bash
# probe_fallback_1003.sh — 缺口 F：`fallback_deterministic` 從來沒有在 1003 上實跑過。
#
# 這一支只做一件事：**在 1003 上真的把模型端點指到一個不通的位址，
# 逼 `twinlink.generate` 走 `fallback_deterministic`，量它，並用負控制
# 證明「模型通的時候不會走這條路」**。
#
# 🔴 不動 1003 的 LM Studio（127.0.0.1:1234，別人在用）——「不通的位址」
#    指的是 1003 本機一個沒人聽的埠（127.0.0.1:19191），不是關掉 1234。
# 🔴 不動既有真相來源 `store/twinstore.sqlite3`——這一支開一個新的
#    `store_fallback_test/` 目錄，用完不刪（「資料不要刪除」）。
# ⚠ 1003 三種路徑方言：CLI 參數（MSYS 會轉）用 `/c/...`；
#    inline python 字面值（MSYS 不轉裸字串內部）用 `C:/...`。
set -u

WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PY="${PY:-/Users/cosmopig/Documents/GitHub/Vacant/.venv/bin/python}"
OUT="${OUT:-$WT/ops/exhibit/twin/evidence_1003_fallback_20260920}"
R="${R:-w401@100.119.113.56}"
RDIR="${RDIR:-/c/Users/w401/vacant_twin}"           # ssh／CLI 參數用（MSYS 會轉）
RDIR_SCP="${RDIR_SCP:-C:/Users/w401/vacant_twin}"    # inline python 字面值用
RPY="${RPY:-python}"

# 新開一個 store 目錄，**不動**既有的 store/twinstore.sqlite3
FDIR="${FDIR:-$RDIR/store_fallback_test}"
FDIR_SCP="${FDIR_SCP:-$RDIR_SCP/store_fallback_test}"
FDB="$FDIR/twinstore.sqlite3"
FDB_SCP="$FDIR_SCP/twinstore.sqlite3"

# 「不通的位址」：1003 本機一個沒人聽的埠。不是關掉 1234。
DEAD_ENDPOINT="${DEAD_ENDPOINT:-http://127.0.0.1:19191/v1}"
REAL_ENDPOINT="${REAL_ENDPOINT:-http://127.0.0.1:1234/v1}"
MODEL="${MODEL:-gemma-4-12b-it-qat}"

mkdir -p "$OUT"
PASS=0; FAIL=0
step() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
ok()   { PASS=$((PASS+1)); echo "  [OK] $*"; }
bad()  { FAIL=$((FAIL+1)); echo "  [紅] $*"; }
chk()  { if [ "$1" = "$2" ]; then ok "$3（得 $1）"; else bad "$3（期望 $2，實得 $1）"; fi; }
# rr：跑遠端指令，**先落盤再取退出碼**（不透過 tee，tee 的 $? 會說謊）
rr() {
  local f="$1"; shift
  ssh -o BatchMode=yes -o ConnectTimeout=25 "$R" "export PYTHONIOENCODING=utf-8; $*" \
      > "$OUT/$f" 2>&1
  echo $?
}

echo "證據目錄：$OUT"
date -u +"UTC %Y-%m-%dT%H:%M:%SZ" | tee "$OUT/00_started.txt"

# ---------------------------------------------------------------------------
step "0. 量具先證明量得動（必中的輸入）＋確認沒有動到 1003 的 LM Studio"
# ---------------------------------------------------------------------------
HN=$(ssh -o BatchMode=yes -o ConnectTimeout=15 "$R" 'hostname' 2>/dev/null | tr -d '\r')
chk "$HN" "w401c-16" "SSH 到 1003 通"

RC=$(rr "01_remote_python.txt" "$RPY -c \"import sys,sqlite3;print(sys.version.split()[0],sqlite3.sqlite_version)\"")
chk "$RC" "0" "1003 python／sqlite3 探測"
grep -qE '^3\.' "$OUT/01_remote_python.txt" && ok "版本字串看起來對" || bad "版本字串怪"

RC=$(rr "02_remote_lms_before.json" "curl -sS --max-time 15 $REAL_ENDPOINT/models")
if grep -q "$MODEL" "$OUT/02_remote_lms_before.json"; then
  ok "測試開始前：1003 的 127.0.0.1:1234 上模型還在（沒被我動過）"
else
  bad "測試開始前就讀不到 1003 的 LM Studio——不應該發生，中止"
  echo "通過 $PASS 項，失敗 $FAIL 項"; exit 2
fi

# 確認「不通的位址」真的不通，而且是快速拒絕不是會拖住展場的那種逾時
RC=$(rr "02b_dead_endpoint_confirmed.txt" "$RPY -c \"
import time,urllib.request
t0=time.time()
try:
    urllib.request.urlopen('$DEAD_ENDPOINT/models', timeout=5)
    print('WRONG: 連得到，這個埠不該有人聽')
except Exception as e:
    print(type(e).__name__, 'elapsed_ms=', int((time.time()-t0)*1000))
\"")
cat "$OUT/02b_dead_endpoint_confirmed.txt"
if grep -qE 'Error' "$OUT/02b_dead_endpoint_confirmed.txt"; then
  ok "確認 $DEAD_ENDPOINT 在 1003 上真的連不到（快速拒絕，不是我瞎猜的埠）"
else
  bad "『不通的位址』其實通——換一個埠再測，這一輪的『退化』證據不算數"
  echo "通過 $PASS 項，失敗 $FAIL 項"; exit 2
fi

# ---------------------------------------------------------------------------
step "1. 開一個新 store（不動既有 store/twinstore.sqlite3）＋餵 3 張卡"
# ---------------------------------------------------------------------------
rr "03a_mkdir.txt" "mkdir -p '$FDIR'" >/dev/null
RC=$(rr "03_seed_positive.json" "cd $RDIR && $RPY -c \"
import sys; sys.path.insert(0, '.')
from ops.exhibit.twin.twinstore import TwinStore, KIND_SUBMITTED
st = TwinStore(r'$FDB_SCP')
cards = [
    ('fbA1', {'need': '把桌面的檔案分類', 'shape': '方正', 'texture': '光滑', 'color': '灰藍', 'vibe': '冷靜、有條理', 'first_line': '先看看有什麼。'}),
    ('fbA2', {'need': '寫一封感謝信', 'shape': '圓潤', 'texture': '絨面', 'color': '暖土', 'vibe': '溫柔、慢熱', 'first_line': '想了很久要怎麼開頭。'}),
    ('fbA3', {'need': '整理今天的待辦', 'shape': '小巧', 'texture': '指紋', 'color': '苔綠', 'vibe': '急性子、直接', 'first_line': '先列出來再說。'}),
]
for sid, card in cards:
    st.append(KIND_SUBMITTED, sid, {'card': card, 'card_text': None, 'ts': None, 'cloud_status': 'probe'}, source='probe_fallback_1003')
print({'seeded': [c[0] for c in cards], 'store_id': st.store_id, 'total_events': st.count()})
st.close()
\"")
chk "$RC" "0" "1003 上新開的 store 種下 3 筆待生成"
cat "$OUT/03_seed_positive.json"

# ---------------------------------------------------------------------------
step "2. 🔴 正控制：端點指到不通的位址，逼 generate 走 fallback_deterministic"
# ---------------------------------------------------------------------------
RC=$(rr "04_remote_generate_degraded.json" "cd $RDIR && $RPY ops/exhibit/twin/twinlink.py --db '$FDB' generate --endpoint '$DEAD_ENDPOINT' --model '$MODEL' --timeout 8")
cat "$OUT/04_remote_generate_degraded.json"
chk "$RC" "0" "对不通端點 generate 退出碼（允許退化，不該炸）"

DEG=$("$PY" -c "
import json,re
t=open('$OUT/04_remote_generate_degraded.json',encoding='utf-8',errors='replace').read()
m=re.search(r'\{.*\}',t,re.S)
print(json.loads(m.group(0))['degraded'] if m else 'PARSE_FAIL')" 2>&1)
chk "$DEG" "3" "3 筆全部退化（engine 應該變成 fallback_deterministic）"

RC=$(rr "05_remote_roster_degraded.json" "cd $RDIR && $RPY ops/exhibit/twin/twinstore.py --db '$FDB' roster")
"$PY" -c "
import json,re
t=open('$OUT/05_remote_roster_degraded.json',encoding='utf-8',errors='replace').read()
m=re.search(r'\[.*\]',t,re.S)
roster=json.loads(m.group(0)) if m else []
for c in roster:
    twin=c.get('twin') or {}
    print(f\"  {c['sub_id']}: engine={twin.get('engine')!r} degraded_from={twin.get('degraded_from')!r} degrade_reason={str(twin.get('degrade_reason'))[:70]!r}\")
n_fb = sum(1 for c in roster if ((c.get('twin') or {}).get('engine')) == 'fallback_deterministic')
print('FALLBACK_ENGINE_COUNT', n_fb)
"
FB_COUNT=$("$PY" -c "
import json,re
t=open('$OUT/05_remote_roster_degraded.json',encoding='utf-8',errors='replace').read()
m=re.search(r'\[.*\]',t,re.S)
roster=json.loads(m.group(0)) if m else []
print(sum(1 for c in roster if ((c.get('twin') or {}).get('engine')) == 'fallback_deterministic'))
" 2>&1)
chk "$FB_COUNT" "3" "roster 摺疊出來的 engine 全是 fallback_deterministic（不是猜的，是讀鏈折出來的）"

RC=$(rr "06_remote_verify_after_degrade.json" "cd $RDIR && $RPY ops/exhibit/twin/twinstore.py --db '$FDB' verify")
chk "$RC" "0" "退化寫進鏈之後，1003 上這條鏈驗證仍然綠"
cat "$OUT/06_remote_verify_after_degrade.json"

# ---------------------------------------------------------------------------
step "3. 🔴 負控制：同一條指令、端點指回真的 1234，不准退化"
# ---------------------------------------------------------------------------
RC=$(rr "07_seed_negative.json" "cd $RDIR && $RPY -c \"
import sys; sys.path.insert(0, '.')
from ops.exhibit.twin.twinstore import TwinStore, KIND_SUBMITTED
st = TwinStore(r'$FDB_SCP')
cards = [
    ('fbB1', {'need': '把書按高度排好', 'shape': '厚實', 'texture': '斑駁', 'color': '沙金', 'vibe': '耐心、龜毛', 'first_line': '一本一本來。'}),
    ('fbB2', {'need': '把備忘錄按日期排序', 'shape': '修長', 'texture': '光滑', 'color': '奶油', 'vibe': '謹慎、愛乾淨', 'first_line': '先看最舊的那一筆。'}),
]
for sid, card in cards:
    st.append(KIND_SUBMITTED, sid, {'card': card, 'card_text': None, 'ts': None, 'cloud_status': 'probe'}, source='probe_fallback_1003')
print({'seeded': [c[0] for c in cards], 'total_events': st.count()})
st.close()
\"")
chk "$RC" "0" "負控制種下 2 筆"
cat "$OUT/07_seed_negative.json"

T0=$(date +%s)
RC=$(rr "08_remote_generate_negative.json" "cd $RDIR && $RPY ops/exhibit/twin/twinlink.py --db '$FDB' generate --endpoint '$REAL_ENDPOINT' --model '$MODEL' --timeout 300 --no-fallback")
T1=$(date +%s)
cat "$OUT/08_remote_generate_negative.json"
echo "  兩隻分身共 $((T1-T0)) 秒（--no-fallback：一旦退化就會直接炸，退出碼非 0）"
chk "$RC" "0" "端點通的時候 generate 正常結束（--no-fallback 沒有炸＝沒有退化）"

DEG2=$("$PY" -c "
import json,re
t=open('$OUT/08_remote_generate_negative.json',encoding='utf-8',errors='replace').read()
m=re.search(r'\{.*\}',t,re.S)
print(json.loads(m.group(0))['degraded'] if m else 'PARSE_FAIL')" 2>&1)
chk "$DEG2" "0" "模型通的時候 degraded=0（『退化路徑可用』這句話因此才算數）"

RC=$(rr "09_remote_roster_negative.json" "cd $RDIR && $RPY ops/exhibit/twin/twinstore.py --db '$FDB' roster")
LM_COUNT=$("$PY" -c "
import json,re
t=open('$OUT/09_remote_roster_negative.json',encoding='utf-8',errors='replace').read()
m=re.search(r'\[.*\]',t,re.S)
roster=json.loads(m.group(0)) if m else []
print(sum(1 for c in roster if str((c.get('twin') or {}).get('engine') or '').startswith('lmstudio:')))
" 2>&1)
chk "$LM_COUNT" "2" "累積 roster 裡（3 隻退化 + 2 隻真模型）：engine 開頭是 lmstudio: 的剛好 2 隻——不多不少"
"$PY" -c "
import json,re
t=open('$OUT/09_remote_roster_negative.json',encoding='utf-8',errors='replace').read()
m=re.search(r'\[.*\]',t,re.S)
roster=json.loads(m.group(0)) if m else []
for c in roster:
    twin=c.get('twin') or {}
    print(f\"  {c['sub_id']}: engine={twin.get('engine')!r} latency_ms={twin.get('latency_ms')!r}\")
"

RC=$(rr "10_remote_verify_after_negative.json" "cd $RDIR && $RPY ops/exhibit/twin/twinstore.py --db '$FDB' verify")
chk "$RC" "0" "負控制寫進去之後，鏈仍然綠"
cat "$OUT/10_remote_verify_after_negative.json"

# ---------------------------------------------------------------------------
step "4. 量 1003 上 fallback_deterministic 的延遲"
# ---------------------------------------------------------------------------
# 4a. 純函式（查表本身，零網路）——這是文件裡宣稱「微秒級」的那個東西
RC=$(rr "11_remote_fallback_pure_latency.json" "cd $RDIR && $RPY -c \"
import sys, time, statistics
sys.path.insert(0, '.')
from ops.exhibit.twin.twinlink import fallback_twin
card = {'need': '整理桌面', 'shape': '圓潤', 'color': '暖土', 'vibe': '冷靜', 'first_line': None}
N = 20000
t0 = time.perf_counter()
for _ in range(N):
    fallback_twin(card)
total = time.perf_counter() - t0
# 也拿逐次的分布，不要只信平均
samples = []
for _ in range(200):
    t = time.perf_counter()
    fallback_twin(card)
    samples.append((time.perf_counter() - t) * 1e6)
print({
    'iterations': N,
    'total_seconds': total,
    'avg_us_per_call': (total / N) * 1e6,
    'sample_median_us': statistics.median(samples),
    'sample_p95_us': sorted(samples)[int(len(samples)*0.95)],
    'sample_max_us': max(samples),
    'note': '純 fallback_twin()，零網路、零 I/O——這是「站著等」那條線的底線保證',
})
\"")
chk "$RC" "0" "純函式延遲量測跑完"
cat "$OUT/11_remote_fallback_pure_latency.json"

# 4b. 全路徑（含對不通端點的連線嘗試，這是展場實際會走到的時間）
RC=$(rr "12_remote_degrade_path_latency.json" "cd $RDIR && $RPY -c \"
import sys, time
sys.path.insert(0, '.')
from ops.exhibit.twin.twinlink import generate_one
card = {'need': '整理桌面', 'shape': '圓潤', 'color': '暖土', 'vibe': '冷靜', 'first_line': None}
lat = []
for i in range(5):
    r = generate_one(card, None, endpoint='$DEAD_ENDPOINT', model='$MODEL', timeout=8.0, allow_fallback=True)
    lat.append(r['latency_ms'])
    assert r['engine'] == 'fallback_deterministic', r
print({
    'runs': 5,
    'latency_ms_each': lat,
    'note': '含一次對不通端點的連線嘗試（本機閉埠拒絕）再退化；不是純函式時間',
})
\"")
chk "$RC" "0" "全路徑（連線嘗試＋退化）延遲量測跑完"
cat "$OUT/12_remote_degrade_path_latency.json"

# ---------------------------------------------------------------------------
step "5. 收尾：確認 1003 的 LM Studio 全程沒被動過"
# ---------------------------------------------------------------------------
RC=$(rr "13_remote_lms_after.json" "curl -sS --max-time 15 $REAL_ENDPOINT/models")
if grep -q "$MODEL" "$OUT/13_remote_lms_after.json"; then
  ok "測試結束後：1003 的 127.0.0.1:1234 上模型還在（全程沒動過它）"
else
  bad "測試結束後讀不到 1003 的 LM Studio——需要人工確認"
fi

RC=$(rr "14_remote_dump_events.json" "cd $RDIR && $RPY ops/exhibit/twin/twinstore.py --db '$FDB' dump")
echo "  事件流已倒出：14_remote_dump_events.json"

RC=$(rr "15_remote_stats.json" "cd $RDIR && $RPY ops/exhibit/twin/twinstore.py --db '$FDB' stats")
cat "$OUT/15_remote_stats.json"

printf '\n\033[1m===== 總計 =====\033[0m\n'
echo "通過 $PASS 項，失敗 $FAIL 項"
echo "證據：$OUT"
echo "1003 上的測試 store（新開的，刻意留著不刪）：${R}:${FDB}"
echo "1003 上的既有真相來源（本次完全沒有動）：${R}:${RDIR}/store/twinstore.sqlite3"
date -u +"UTC %Y-%m-%dT%H:%M:%SZ" | tee "$OUT/99_finished.txt"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
