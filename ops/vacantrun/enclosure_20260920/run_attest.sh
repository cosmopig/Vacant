#!/bin/bash
# 收據的四個欄位與 fail-closed 分級，**在真的圍牆裡量一次，每一格配負控制**。
#
#   bash ops/vacantrun/enclosure_20260920/run_attest.sh
#
# 四組，**跑在同一台機器、同一分鐘、同一支探針**，唯一的差別就是那一個變因：
#
#   1. noenc    不套 enc.sh                       ⇒ enclosure.applied == false
#   2. enc      套 enc.sh ＋ 燒 canary            ⇒ applied == true、canary == true、
#                                                   unexplained == 0 ⇒ **A 級**
#   3. nohook   套 enc.sh、**不燒 canary**        ⇒ canary == false ⇒ **降到 B**
#   4. rogue    套 enc.sh ＋ canary ＋ 多一通沒有
#               工具事件的呼叫                    ⇒ unexplained > 0 ⇒ **降到 B**
#
# ⚠ 這支證明的是「**契約與兩個探針在真的圍牆裡會動**」。
#   它**不**證明「某個 agent 框架的掛鉤會燒」——那要那個 agent 真的跑一趟。
#   兩件事在報告裡不可以混講成一句。
#
# 收尾印 `RUN_ATTEST_DONE fail=<n>`，**fail=0 才算過**。
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HERE/bin"
REPO="${ENC_REPO:-$(cd "$HERE/../../.." && pwd)}"
BASE="${ENC_BASE:-/var/tmp/vacant-attest-20260920}"
UPSTREAM="${ENC_UPSTREAM:-http://100.119.113.56:1234}"
PY="${ENC_PY:-/usr/bin/python3}"
OUT="$BASE/out"; DOOR="$BASE/door"; STATE="$BASE/state"
JOURNAL="$STATE/relay/proxyd/wire/index.jsonl"
mkdir -p "$OUT" "$DOOR" "$STATE"
[ -f "$BASE/.created_by_vacant_enclosure" ] || date > "$BASE/.created_by_vacant_enclosure"
FAIL=0
ck() {  # ck <標籤> <條件字串（真＝過）> <附註>
  if [ "$2" = "1" ]; then echo "✓ $1  $3"; else echo "✗ $1  $3"; FAIL=$((FAIL+1)); fi
}

# ── 門：**真的連一次**才算活著（`[ -S socket ]` ≠ 門活著）─────────────
door_alive() {
  "$PY" - "$DOOR/relay.sock" <<'PYEOF'
import socket, sys
try:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(2)
    s.connect(sys.argv[1]); s.close(); sys.exit(0)
except Exception:
    sys.exit(1)
PYEOF
}
OWNED=""
if ! door_alive; then
  rm -f "$DOOR/relay.sock"
  PYTHONPATH="$REPO" "$PY" -m vacant_network.vrun.proxyd \
      --unix "$DOOR/relay.sock" --path-policy model --state "$STATE/relay" \
      --upstream "openai=$UPSTREAM" --upstream "anthropic=$UPSTREAM" \
      > "$OUT/door.log" 2>&1 &
  OWNED=$!
  for _ in $(seq 1 250); do door_alive && break; sleep 0.1; done
fi
trap 'if [ -n "$OWNED" ]; then kill "$OWNED" 2>/dev/null; wait "$OWNED" 2>/dev/null; fi' EXIT
door_alive || { echo "門起不來（看 $OUT/door.log），停。"; exit 2; }
echo "門活著（真的連過一次）"

jlines() { if [ -f "$JOURNAL" ]; then wc -l < "$JOURNAL" | tr -d ' '; else echo 0; fi; }

run_enc() {   # run_enc <名字> <ENC_FIRE_CANARY> <ENC_ROGUE_CALL>
  local name="$1" canary="$2" rogue="$3"
  local ws="$BASE/ws_$name"
  rm -rf "$ws"; mkdir -p "$ws"
  local before; before=$(jlines)
  echo "### $name  journal_before=$before"
  ENC_WS="$ws" ENC_RO="$REPO/vacant_network:$BIN" ENC_DOOR="$DOOR" ENC_PY="$PY" \
  ENC_SETENV="PYTHONPATH=$REPO VACANT_RUN_ID=$name ENC_FIRE_CANARY=$canary ENC_ROGUE_CALL=$rogue" \
    "$BIN/enc.sh" /bin/bash "$BIN/attest_inner.sh" "$BIN" "$REPO" "$ws" \
    > "$OUT/inner_$name.log" 2>&1
  local rc=$?
  local after; after=$(jlines)
  echo "### $name  rc=$rc journal_after=$after delta=$((after-before))"
  PYTHONPATH="$REPO" "$PY" -m vacant_network.vrun.attest --assemble \
      --probe-json "$ws/probe_enc.json" --hook-log "$ws/hooks.jsonl" \
      --relay-index "$JOURNAL" --relay-since "$before" \
      --run-id "$name" --agent probe --install-attempted yes \
      --out "$OUT/attest_$name.json" > /dev/null
  echo "$after" > "$OUT/.journal_after_$name"
  # ⚠ **這一跑的政策雜湊要當場抓**：`enc.sh` 每跑一格就重寫一次 policy.json
  #   （bwrap 參數含工作區路徑，每格不同）⇒ 收工再去 hash 抓到的是最後那一格的。
  #   2026-09-20 實測踩到：`2-policy-sha-matches` 假性紅燈。
  "$PY" -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" \
      "$DOOR/policy.json" > "$OUT/.policy_sha_$name"
}

# ── 1. 負控制：不套 enc.sh（同一支探針、同一分鐘）─────────────────────
before=$(jlines)
PYTHONPATH="$REPO" "$PY" -m vacant_network.vrun.attest --probe \
    --policy "$DOOR/policy.json" --door-sock "$DOOR/relay.sock" \
    --out "$OUT/probe_noenc.json" > /dev/null
PYTHONPATH="$REPO" "$PY" -m vacant_network.vrun.attest --assemble \
    --probe-json "$OUT/probe_noenc.json" --hook-log "$BASE/nohooklog.jsonl" \
    --relay-index "$JOURNAL" --relay-since "$before" \
    --run-id noenc --agent probe --install-attempted no \
    --out "$OUT/attest_noenc.json" > /dev/null

# ── 2/3/4. 圍牆裡的三格 ───────────────────────────────────────────────
run_enc enc    1 0
run_enc nohook 0 0
run_enc rogue  1 1

# ── 判準（全部從落盤的 JSON 讀，不看畫面上印了什麼）───────────────────
read_json() { PYTHONPATH="$REPO" "$PY" - "$1" "$2" <<'PYEOF'
import json, pathlib, sys
d = json.loads(pathlib.Path(sys.argv[1]).read_text("utf-8"))
for k in sys.argv[2].split("."):
    d = (d or {}).get(k) if isinstance(d, dict) else None
print(json.dumps(d, ensure_ascii=False))
PYEOF
}
eq() { [ "$(read_json "$1" "$2")" = "$3" ] && echo 1 || echo 0; }

echo "── 判準 ──────────────────────────────────────────────────────────"
ck "1-negctl-applied-false" \
   "$(eq "$OUT/attest_noenc.json" enclosure.applied false)" \
   "不套 enclosure ⇒ applied == false（不是 0、不是缺欄位）"
ck "1-negctl-tier-C" "$(eq "$OUT/attest_noenc.json" tier '"C"')" \
   "沒圍牆沒掛鉤 ⇒ C 級"
ck "2-applied-true"  "$(eq "$OUT/attest_enc.json" enclosure.applied true)" \
   "套了 enclosure ⇒ applied == true"
ck "2-ns-differs"    "$(eq "$OUT/attest_enc.json" enclosure.probe.ns_differs_from_outer true)" \
   "圍牆裡的 netns 跟外面**不是**同一個（硬證據）"
ck "2-canary-true"   "$(eq "$OUT/attest_enc.json" framework_hook.canary_fired true)" \
   "掛鉤 canary 燒到了"
ck "2-unexplained-0" "$(eq "$OUT/attest_enc.json" reconciled.unexplained 0)" \
   "每一通都對得上一個工具事件"
ck "2-tier-A"        "$(eq "$OUT/attest_enc.json" tier '"A"')" "⇒ A 級"
ck "3-nohook-canary-false" \
   "$(eq "$OUT/attest_nohook.json" framework_hook.canary_fired false)" \
   "負控制：掛鉤拆掉 ⇒ canary_fired == false"
ck "3-nohook-downgraded" "$(eq "$OUT/attest_nohook.json" tier '"B"')" \
   "⇒ **自動降級**到 B（不是還留在 A）"
ck "4-rogue-unexplained>0" \
   "$([ "$(read_json "$OUT/attest_rogue.json" reconciled.unexplained)" -gt 0 ] && echo 1 || echo 0)" \
   "負控制：多一通沒有工具事件的 ⇒ unexplained > 0"
ck "4-rogue-downgraded" "$(eq "$OUT/attest_rogue.json" tier '"B"')" \
   "⇒ **自動降級**到 B"

# policy_sha256 對得上**那一跑當下**主機這一側實際用的那一份
HOSTSHA=$(cat "$OUT/.policy_sha_enc")
ck "2-policy-sha-matches" \
   "$([ "$(read_json "$OUT/attest_enc.json" enclosure.policy_sha256)" = "\"$HOSTSHA\"" ] && echo 1 || echo 0)" \
   "圍牆裡讀到的政策雜湊 == 主機上那一份（${HOSTSHA:0:16}…）"
# 負控制：**換一份政策就換一個雜湊**（不然「對得上」可能只是常數對常數）
ck "2-policy-sha-is-not-constant" \
   "$([ "$(cat "$OUT/.policy_sha_enc")" != "$(cat "$OUT/.policy_sha_nohook")" ] && echo 1 || echo 0)" \
   "不同工作區 ⇒ 不同政策 ⇒ 不同雜湊（證明這一欄真的在動）"

echo "── 摘要 ──────────────────────────────────────────────────────────"
for n in noenc enc nohook rogue; do
  echo -n "$n: "
  PYTHONPATH="$REPO" "$PY" - "$OUT/attest_$n.json" <<'PYEOF'
import json, pathlib, sys
d = json.loads(pathlib.Path(sys.argv[1]).read_text("utf-8"))
print(json.dumps({"tier": d.get("tier"),
                  "applied": d["enclosure"]["applied"],
                  "ns_id": d["enclosure"]["ns_id"],
                  "policy_sha256": (d["enclosure"]["policy_sha256"] or "")[:16],
                  "canary": d["framework_hook"]["canary_fired"],
                  "relay": d["reconciled"]["relay_calls"],
                  "hook_events": d["reconciled"]["hook_events"],
                  "unexplained": d["reconciled"]["unexplained"]},
                 ensure_ascii=False))
PYEOF
done
echo "RUN_ATTEST_DONE out=$OUT fail=$FAIL"
[ "$FAIL" -eq 0 ]
