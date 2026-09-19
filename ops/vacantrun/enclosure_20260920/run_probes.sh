#!/bin/bash
# enclosure 圍牆 ＋ 門的**一鍵重跑**：負控制與 enclosure 兩組都跑，缺一不可。
#
#   bash ops/vacantrun/enclosure_20260920/run_probes.sh
#
# 為什麼負控制一定要一起跑：只跑 enclosure 那一組，讀的人沒辦法分辨
# 「圍牆擋住了」與「那些目標本來就沒開」。**兩組跑在同一台機器、同一分鐘、
# 同一支探針**，差別只有「有沒有套 enc.sh」——這樣 6 擋 1 通才是證據。
#
# 環境變數（都有預設）：
#   ENC_BASE      工作根目錄（預設 /var/tmp/vacant-enclosure-20260920）
#   ENC_REPO      含 `vacant_network/` 的 repo 根（預設：本檔往上四層）
#   ENC_UPSTREAM  真上游（預設 http://100.86.226.21:1234 ＝ 1004）
#   ENC_PY        python3 路徑（預設 /usr/bin/python3）
#   ENC_CLEAN=1   跑完把 ENC_BASE 刪掉（**只刪自己建的**，靠標記檔認）
#
# 產出：$ENC_BASE/out/*.json 與 *.log；收尾印 `RUN_PROBES_DONE ... fail=<n>`。
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HERE/bin"
BASE="${ENC_BASE:-/var/tmp/vacant-enclosure-20260920}"
REPO="${ENC_REPO:-$(cd "$HERE/../../.." && pwd)}"
UPSTREAM="${ENC_UPSTREAM:-http://100.86.226.21:1234}"
PY="${ENC_PY:-/usr/bin/python3}"
OUT="$BASE/out"
DOOR="$BASE/door"
MARK="$BASE/.created_by_vacant_enclosure"

FAIL=0
PIDS=()
note() { echo "[$(date -u +%H:%M:%S)] $*"; }
bad()  { echo "‼ FAIL: $*"; FAIL=$((FAIL+1)); }

# ── 0. 量具先確認活著 ──────────────────────────────────────────────────
command -v bwrap >/dev/null || { echo "沒有 bwrap，停。"; exit 2; }
[ -x "$PY" ] || { echo "沒有 $PY，停。"; exit 2; }
"$PY" -c "import sys; sys.path.insert(0,'$REPO'); import vacant_network.vrun.proxyd" \
  || { echo "從 $REPO 匯入不了 vacant_network.vrun.proxyd，停。"; exit 2; }
bwrap --unshare-all --die-with-parent --ro-bind /usr /usr \
      --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib64 /lib64 \
      --proc /proc --dev /dev --tmpfs /tmp /bin/true \
  || { echo "裸 bwrap 起不來（AppArmor profile 裝了嗎？）停。"; exit 2; }
note "量具檢查通過：bwrap rc=0、proxyd 匯入得到"

[ -d "$BASE" ] || { mkdir -p "$BASE"; : > "$MARK"; }
mkdir -p "$OUT" "$DOOR" "$BASE/ws/probe" "$BASE/state"
# ⚠ **殘留檔會讓量具說謊**：第二次跑的時候 `echo_port_*` 還留著上一次的埠號，
#   `waitfor` 當場就「就緒」，於是三扇 echo 門全部指到已經死掉的埠 ⇒ 502。
#   2026-09-20 實際踩到（第一次 fail=0、第二次 fail=4，程式碼一個字沒改）。
#   所以這裡把**這支自己產出的東西**全部清掉，不是只清 *.json／*.log。
rm -f "$DOOR"/*.sock
rm -f "$OUT"/probe_* "$OUT"/door_* "$OUT"/echo_* "$OUT"/write_* \
      "$OUT"/target_* "$OUT"/journal_* "$OUT"/summary.json
# 探針自己的門用 `probe_` 前綴的 state 目錄，跟 run_agent.sh 的 `relay` 分開，
# 免得兩邊的 journal 混在一起（誰打的那一通要看得出來）。
rm -rf "$BASE/state/probe_relay" "$BASE/state/probe_echo" \
       "$BASE/state/probe_echo_any"

cleanup() {
  for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null; done
  sleep 1
  for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill -9 "$p" 2>/dev/null; done
  # 探針目標的 socket 檔開在 /tmp（要在 enclosure 的私有 tmpfs **之外**才
  # 量得到「看不到」）⇒ 收工要自己刪，別在共用的 /tmp 留垃圾。
  [ -n "${UPATH:-}" ] && rm -f "$UPATH"
  # ⚠ 只刪自己建的：沒有標記檔就不碰（今晚有人誤刪掉別人的 cwd）
  if [ "${ENC_CLEAN:-0}" = "1" ]; then
    if [ -f "$MARK" ]; then
      note "ENC_CLEAN=1 且標記檔在 ⇒ 刪 $BASE"
      rm -rf "$BASE"
    else
      note "ENC_CLEAN=1 但 $BASE **不是這支建的**（沒有標記檔）⇒ 不刪"
    fi
  fi
}
trap cleanup EXIT

bg() {   # bg <logfile> <cmd...>
  local log="$1"; shift
  "$@" > "$log" 2>&1 &
  PIDS+=($!)
  echo $!
}

waitfor() {  # waitfor <檔案> <秒>
  local f="$1" n="${2:-20}" i=0
  while [ $i -lt $((n*10)) ]; do [ -e "$f" ] && return 0; sleep 0.1; i=$((i+1)); done
  return 1
}

# ── 1. 主機側的探針目標（負控制要連得到的那些）────────────────────────
TPORT="$("$PY" -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')"
UPATH="/tmp/vacant_enc_target_$$.sock"
ABSNAME="vacant_enc_abstract_$$"
bg "$OUT/target_tcp.log"      "$PY" "$BIN/targets_up.py" x tcp_localhost "$TPORT" >/dev/null
bg "$OUT/target_unix.log"     "$PY" "$BIN/targets_up.py" x unix_path "$UPATH" >/dev/null
bg "$OUT/target_abstract.log" "$PY" "$BIN/targets_up.py" x unix_abstract "$ABSNAME" >/dev/null

# 三台 echo 上游（**每扇 echo 門一台**，否則 hits 分不出是誰打的）
declare -A ECHO_PORT
for tag in model any pipe; do
  bg "$OUT/echo_$tag.log" "$PY" "$BIN/echo_upstream.py" \
      --hits "$OUT/echo_hits_$tag.jsonl" --ready "$OUT/echo_port_$tag" >/dev/null
  waitfor "$OUT/echo_port_$tag" 20 || bad "echo 上游 $tag 沒起來"
  ECHO_PORT[$tag]="$(cat "$OUT/echo_port_$tag" 2>/dev/null || echo 0)"
done
note "目標就緒：tcp=$TPORT unix=$UPATH abstract=@$ABSNAME echo=${ECHO_PORT[model]}/${ECHO_PORT[any]}/${ECHO_PORT[pipe]}"

# ── 2. 四扇門 ─────────────────────────────────────────────────────────
#  relay      真上游 ＋ policy=model  ← agent 走這扇
#  echo       echo   ＋ policy=model  ← /admin 要被擋（上游收不到）
#  echo_any   echo   ＋ policy=any    ← 負控制：同一條 /admin **到得了**上游
#  echo_pipe  echo   ＋ **byte pipe**  ← 負控制：門不終結 HTTP 會怎樣
door() {  # door <名字> <上游 url> <policy>
  local n="$1" up="$2" pol="$3"
  PYTHONPATH="$REPO" bg "$OUT/door_$n.log" "$PY" -m vacant_network.vrun.proxyd \
      --unix "$DOOR/$n.sock" --path-policy "$pol" \
      --state "$BASE/state/probe_$n" \
      --upstream "openai=$up" --upstream "anthropic=$up" >/dev/null
  waitfor "$DOOR/$n.sock" 25 || bad "門 $n 沒起來（看 $OUT/door_$n.log）"
}
door relay    "$UPSTREAM"                          model
door echo     "http://127.0.0.1:${ECHO_PORT[model]}" model
door echo_any "http://127.0.0.1:${ECHO_PORT[any]}"   any
bg "$OUT/door_echo_pipe.log" "$PY" "$BIN/door_host_bytepipe.py" \
   "$DOOR/echo_pipe.sock" 127.0.0.1 "${ECHO_PORT[pipe]}" "$OUT/door_pipe_conn.log" >/dev/null
waitfor "$DOOR/echo_pipe.sock" 25 || bad "byte pipe 門沒起來"
note "四扇門就緒：$(ls "$DOOR" | tr '\n' ' ')"

# ⚠ 真上游先確認活著：它死了的話 relay_models 那一格會是 502，
#   而「門壞了」與「上游沒開」在收據上必須分得出來。
UPRC="$(/usr/bin/curl -s -o /dev/null -m 10 -w '%{http_code}' "$UPSTREAM/v1/models" || echo 000)"
note "真上游 $UPSTREAM/v1/models ⇒ HTTP $UPRC"
[ "$UPRC" = "200" ] || bad "真上游不是 200（$UPRC）——relay_models 那一格會連帶紅"

# 門活著的時候才抄得到 state.json（proxyd 收工會把它刪掉）——那份是
# 「這扇門的政策是什麼、有沒有持有金鑰」的落盤證據。
for n in relay echo echo_any; do
  cp -f "$BASE/state/probe_$n/proxyd/state.json" "$OUT/door_state_$n.json" \
    2>/dev/null || bad "抄不到 $n 的 state.json"
done

# ── 3. 圍牆探針：負控制（不套 enclosure）與 enclosure（套）────────────
export PROBE_TARGETS="$("$PY" - "$TPORT" "$UPATH" "$ABSNAME" "$DOOR" "$UPSTREAM" <<'PYEOF'
import json, sys, urllib.parse
tport, upath, absname, door, upstream = sys.argv[1:6]
u = urllib.parse.urlsplit(upstream)
print(json.dumps({
 "ext_ip_upstream":   {"kind":"http","host":u.hostname,"port":u.port or 80,
                       "path":"/v1/models","want":None},
 "ext_ip_cloudflare": {"kind":"tcp","host":"1.1.1.1","port":443,"want":None},
 "loopback_own":      {"kind":"tcp","host":"127.0.0.1","port":int(tport),"want":None},
 "unix_path_tmp":     {"kind":"unix","path":upath,"want":None},
 "unix_abstract":     {"kind":"abstract","name":absname,"want":None},
 "dns_example":       {"kind":"dns","name":"example.com","want":None},
 "door_relay_sock":   {"kind":"unix","path":door+"/relay.sock","want":None},
}))
PYEOF
)"

# 負控制：全部 want=true
NEG="$("$PY" -c "
import json,os
t=json.loads(os.environ['PROBE_TARGETS'])
for v in t.values(): v['want']=True
print(json.dumps(t))")"
note "── 負控制（不套 enclosure）──"
PROBE_TARGETS="$NEG" PROBE_JSON_OUT="$OUT/probe_negctl.json" \
  "$PY" "$BIN/probe_targets.py" 2>&1 | tee "$OUT/probe_negctl.log"

# enclosure：門 true、其餘 false。⚠ door_relay_sock 在 enclosure 裡的路徑不同
ENCT="$("$PY" -c "
import json,os
t=json.loads(os.environ['PROBE_TARGETS'])
for k,v in t.items(): v['want'] = (k=='door_relay_sock')
t['door_relay_sock']['path']='/run/vacant/relay.sock'
print(json.dumps(t))")"
note "── enclosure（套 enc.sh）──"
ENC_WS="$BASE/ws/probe" ENC_RO="$BIN" ENC_DOOR="$DOOR" \
  "$BIN/enc.sh" /bin/true          # 先確認 enc.sh 這一組參數起得來
ENCRC=$?
[ $ENCRC -eq 0 ] || bad "enc.sh 起不來 rc=$ENCRC"
# ⚠ `ENC_SETENV` 是空白分隔的、JSON 裡有空白 ⇒ 走不通。改成把 JSON 寫進
#   工作區的檔案，enclosure 內用 shell 讀回環境變數。
printf '%s' "$ENCT" > "$BASE/ws/probe/targets.json"
ENC_WS="$BASE/ws/probe" ENC_RO="$BIN" ENC_DOOR="$DOOR" \
  "$BIN/enc.sh" /bin/bash -c \
  'PROBE_TARGETS="$(cat targets.json)" PROBE_JSON_OUT=probe_enclosure.json \
     /usr/bin/python3 '"$BIN"'/probe_targets.py' 2>&1 \
  | tee "$OUT/probe_enclosure.log"
cp -f "$BASE/ws/probe/probe_enclosure.json" "$OUT/probe_enclosure.json" 2>/dev/null \
  || bad "enclosure 探針沒吐 JSON"

for f in probe_negctl probe_enclosure; do
  m="$("$PY" -c "
import json,sys
rows=json.load(open('$OUT/$f.json'))
print(sum(1 for r in rows if r['want'] is not None and r['reachable']!=r['want']))" 2>/dev/null || echo 99)"
  note "$f mismatched=$m"
  [ "$m" = "0" ] || bad "$f mismatched=$m（不是 0）"
done

# ── 4. 門的 HTTP 探針（在 enclosure 裡跑）─────────────────────────────
DC="$("$PY" - <<'PYEOF'
import json
D="/run/vacant"
print(json.dumps({
 "relay_models":    {"sock":f"{D}/relay.sock","method":"GET",
                     "path":"/v1/models","want_status":200},
 "relay_admin":     {"sock":f"{D}/relay.sock","method":"GET",
                     "path":"/admin","want_status":403},
 "echo_admin":      {"sock":f"{D}/echo.sock","method":"GET",
                     "path":"/admin","want_status":403},
 "echo_chat":       {"sock":f"{D}/echo.sock","method":"POST",
                     "path":"/v1/chat/completions","body":"{}",
                     "header_auth":"Bearer ENCLOSURE-CALLER-KEY",
                     "want_status":200},
 "echo_any_admin":  {"sock":f"{D}/echo_any.sock","method":"GET",
                     "path":"/admin","want_status":200},
 "echo_pipe_admin": {"sock":f"{D}/echo_pipe.sock","method":"GET",
                     "path":"/admin","want_status":200},
 "echo_lookalike":  {"sock":f"{D}/echo.sock","method":"GET",
                     "path":"/v1/modelsX","want_status":403},
}))
PYEOF
)"
printf '%s' "$DC" > "$BASE/ws/probe/door_checks.json"
note "── 門的 HTTP 探針（enclosure 內）──"
ENC_WS="$BASE/ws/probe" ENC_RO="$BIN" ENC_DOOR="$DOOR" \
  "$BIN/enc.sh" /bin/bash -c \
  'DOOR_CHECKS="$(cat door_checks.json)" DOOR_JSON_OUT=door_probe.json \
     /usr/bin/python3 '"$BIN"'/door_http_probe.py' 2>&1 \
  | tee "$OUT/door_probe.log"
cp -f "$BASE/ws/probe/door_probe.json" "$OUT/door_probe.json" 2>/dev/null \
  || bad "門的探針沒吐 JSON"
DM="$("$PY" -c "
import json
rows=json.load(open('$OUT/door_probe.json'))
print(sum(1 for r in rows if not r['match']))" 2>/dev/null || echo 99)"
note "door_probe mismatched=$DM"
[ "$DM" = "0" ] || bad "door_probe mismatched=$DM"

# ── 5. 上游到底收到了什麼（**這一節才是「沒隧道過去」的證據**）────────
sleep 1
# ⚠ **不要寫 `$(grep -c ... || echo 0)`**：`grep -c` 沒命中時**印 0 又回 1**
#   ⇒ 那個 `|| echo 0` 會把輸出變成 "0\n0"，比較就永遠不相等。
#   今晚第 15 個量具說謊的候選，先擋下來。
count_admin() {
  local f="$1" n
  n="$(grep -c '"path": "/admin"' "$f" 2>/dev/null)"
  echo "${n:-0}"
}
for tag in model any pipe; do
  note "echo[$tag] 收到 /admin 的次數 = $(count_admin "$OUT/echo_hits_$tag.jsonl")"
done
A_MODEL="$(count_admin "$OUT/echo_hits_model.jsonl")"
A_ANY="$(count_admin "$OUT/echo_hits_any.jsonl")"
A_PIPE="$(count_admin "$OUT/echo_hits_pipe.jsonl")"
[ "$A_MODEL" = "0" ] || bad "policy=model 的門竟然把 /admin 送到上游了（$A_MODEL 次）"
[ "$A_ANY"  = "1" ] || bad "負控制沒成立：policy=any 的門應該送 1 次，實得 $A_ANY"
[ "$A_PIPE" = "1" ] || bad "負控制沒成立：byte pipe 門應該送 1 次，實得 $A_PIPE"
# 金鑰穿透：門不持有金鑰 ⇒ 上游要看得到呼叫端自己帶的那一串
grep -q 'ENCLOSURE-CALLER-KEY' "$OUT/echo_hits_model.jsonl" \
  || bad "Authorization 沒有穿透到上游（sentinel=\"\" 的性質破了）"
# 反面：門自己的落盤裡**不准**出現那一串（header 不上碟）
# ⚠ 先跑**正控制**：同一支 grep 在同一個目錄要找得到一個一定存在的字串，
#   否則「掃不到金鑰」可能只是 grep 根本沒讀到那些檔案。
if ! grep -rq 'chat/completions' "$BASE/state/probe_echo" 2>/dev/null; then
  bad "grep 的正控制沒過 ⇒ 下面那格「金鑰沒上碟」不算量到"
fi
if grep -rq 'ENCLOSURE-CALLER-KEY' "$BASE/state/probe_echo" 2>/dev/null; then
  bad "金鑰上碟了：$BASE/state/probe_echo 裡掃得到 ENCLOSURE-CALLER-KEY"
fi

# ── 6. 門目錄唯讀（正面驗，不是假設）＋ 負控制 ────────────────────────
note "── 寫入探針：門目錄唯讀 ──"
ENC_WS="$BASE/ws/probe" ENC_RO="$BIN" ENC_DOOR="$DOOR" \
  "$BIN/enc.sh" /usr/bin/python3 "$BIN/write_probe.py" \
  /run/vacant /tmp "$BASE/ws/probe" /usr --json write_ro.json 2>&1 \
  | tee "$OUT/write_ro.log"
cp -f "$BASE/ws/probe/write_ro.json" "$OUT/write_ro.json" 2>/dev/null || true
note "── 寫入探針的**負控制**：ENC_DOOR_RW=1（舊的 --bind）──"
ENC_DOOR_RW=1 ENC_WS="$BASE/ws/probe" ENC_RO="$BIN" ENC_DOOR="$DOOR" \
  "$BIN/enc.sh" /usr/bin/python3 "$BIN/write_probe.py" \
  /run/vacant --json write_rw.json 2>&1 | tee "$OUT/write_rw.log"
cp -f "$BASE/ws/probe/write_rw.json" "$OUT/write_rw.json" 2>/dev/null || true
"$PY" - "$OUT" <<'PYEOF' || FAIL=$((FAIL+1))
import json, sys
out = sys.argv[1]
ro = {r["path"]: r for r in json.load(open(f"{out}/write_ro.json"))}
rw = {r["path"]: r for r in json.load(open(f"{out}/write_rw.json"))}
ok = True
d = ro["/run/vacant"]
if d["writable"] or d["errno"] != "EROFS":
    print(f"‼ FAIL: --ro-bind 之下 /run/vacant 應該是 EROFS，實得 {d}"); ok = False
if not rw["/run/vacant"]["writable"]:
    print(f"‼ FAIL: 負控制沒成立——ENC_DOOR_RW=1 之下應該寫得進去，"
          f"實得 {rw['/run/vacant']}"); ok = False
if not ro["/tmp"]["writable"]:
    print("‼ FAIL: 私有 /tmp 應該寫得進去（量具活著的正控制）"); ok = False
if ro["/usr"]["writable"]:
    print("‼ FAIL: /usr 竟然寫得進去"); ok = False
print("WRITE_CHECK ok" if ok else "WRITE_CHECK failed")
sys.exit(0 if ok else 1)
PYEOF

# ── 7. 收尾 ───────────────────────────────────────────────────────────
# 門的 journal **只抄索引**（`index.jsonl`），body 不進 repo。
for n in relay echo echo_any; do
  cp -f "$BASE/state/probe_$n/proxyd/wire/index.jsonl" \
     "$OUT/journal_$n.jsonl" 2>/dev/null || true
done
"$PY" - "$OUT" "$FAIL" <<'PYEOF'
import json, pathlib, sys
out, fail = pathlib.Path(sys.argv[1]), int(sys.argv[2])
s = {"fail": fail}
for n in ("probe_negctl", "probe_enclosure", "door_probe",
          "write_ro", "write_rw"):
    p = out / f"{n}.json"
    s[n] = json.loads(p.read_text()) if p.is_file() else None
(out / "summary.json").write_text(json.dumps(s, ensure_ascii=False, indent=2))
PYEOF
echo "RUN_PROBES_DONE out=$OUT fail=$FAIL"
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
