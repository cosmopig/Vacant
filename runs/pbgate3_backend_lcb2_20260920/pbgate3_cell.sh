#!/usr/bin/env bash
# 一格 ＝ 一個公開題庫題目 × 一個 agent × 一次 `vacant run`。
#
# 與 `runs/pbgate2_agents_lcb2_20260920/pbgate2_cell.sh` 的差別只有兩處，其餘逐字沿用：
#   1. ROOT（/var/tmp/vacant_pbgate2 → /var/tmp/vacant_pbgate3）
#   2. **後端 1003（thinking）→ 1004（非 thinking）** ←── 這一輪唯一被變的東西
# 題目／臂／agent／旗標／prompt／wrap_agent.sh 的 16384 全部一個字沒動。
set -u
ROOT=${PB_ROOT:-/var/tmp/vacant_pbgate3}
REPO=$ROOT/repo
TPL=$REPO/ops/gain/r534/templates
PY=/usr/bin/python3
export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:/home/user1/.local/bin:$PATH
export VACANT_RUN_UPSTREAM_OPENAI=${PB_UPSTREAM_OPENAI:-http://100.86.226.21:1234/v1}
export VACANT_RUN_UPSTREAM_ANTHROPIC=${PB_UPSTREAM_ANTHROPIC:-http://100.86.226.21:1234}
export VACANT_AGENT_MODEL=${PB_MODEL:-gemma-4-12b-it-qat}
AGENT=${PB_AGENT:-pi}
TEST_TIMEOUT=${PB_TEST_TIMEOUT:-120}
AGENT_TIMEOUT=${PB_AGENT_TIMEOUT:-900}
PROMPT='Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file.'
mkdir -p "$ROOT/logs" "$ROOT/argv"

tid="$1"; arm="${2:-V}"
name="${tid}_${AGENT}"
ws=$ROOT/ws_$name; rd=$ROOT/rd_$name
rm -rf "$ws" "$rd"; mkdir -p "$ws"
cp "$TPL/$tid/goal.md" "$TPL/$tid/contract.md" "$TPL/$tid/run_tests.sh" "$ws/"
if [ "$arm" = "V" ]; then cp -r "$TPL/$tid/tests_visible" "$ws/"; fi
# 工作區純度擋門（fail-closed），沿用前兩輪
want_V="./contract.md ./goal.md ./run_tests.sh ./tests_visible/test_visible.py"
want_N="./contract.md ./goal.md ./run_tests.sh"
got="$(cd "$ws" && find . -type f | sort | tr '\n' ' ' | sed 's/ $//')"
if [ "$arm" = "V" ]; then want="$want_V"; else want="$want_N"; fi
if [ "$got" != "$want" ]; then
  echo "工作區不乾淨，停。arm=$arm" >&2
  echo "  want: $want" >&2
  echo "  got : $got" >&2
  exit 3
fi
cd "$REPO" || exit 2
echo "=== BEGIN $name $(date -u +%FT%T.%NZ) ==="
{
  echo "cwd=$REPO"
  echo "$PY -m vacant_network.vrun.launcher \\"
  echo "  --workspace $ws \\"
  echo "  --run-dir $rd \\"
  echo "  --suite $TPL/$tid/tests_visible \\"
  echo "  --task-id pbgate3_$name \\"
  echo "  --sandbox none \\"
  echo "  --test-timeout $TEST_TIMEOUT \\"
  echo "  --timeout $AGENT_TIMEOUT \\"
  echo "  --retry none \\"
  echo "  --json \\"
  echo "  -- $REPO/ops/vacantrun/wrap_agent.sh $AGENT '$PROMPT'"
  echo "wrapper=timeout 1200"
  echo "agent=$AGENT  arm=$arm  workspace_files=$(cd "$ws" && find . -type f | sort | tr '\n' ' ')"
  echo "ENV VACANT_RUN_UPSTREAM_OPENAI=$VACANT_RUN_UPSTREAM_OPENAI"
  echo "ENV VACANT_RUN_UPSTREAM_ANTHROPIC=$VACANT_RUN_UPSTREAM_ANTHROPIC"
  echo "ENV VACANT_AGENT_MODEL=$VACANT_AGENT_MODEL"
  echo "ENV VACANT=(unset, launcher 預設 1)"
  echo "ENV CLAUDE_CODE_MAX_CONTEXT_TOKENS=(unset, 刻意——保住 Claude Code 那一格的零接線)"
} > "$ROOT/argv/$name.argv.txt"
t0=$(date +%s.%N)
timeout 1200 $PY -m vacant_network.vrun.launcher \
    --workspace "$ws" --run-dir "$rd" --suite "$TPL/$tid/tests_visible" \
    --task-id "pbgate3_$name" --sandbox none \
    --test-timeout "$TEST_TIMEOUT" --timeout "$AGENT_TIMEOUT" --retry none --json \
    -- "$REPO/ops/vacantrun/wrap_agent.sh" "$AGENT" "$PROMPT" \
    > "$ROOT/logs/$name.stdout" 2> "$ROOT/logs/$name.stderr"
rc=$?
t1=$(date +%s.%N)
echo "exit_code=$rc"
echo "$rc" > "$rd/_launcher_exit_code.txt" 2>/dev/null || true
awk -v a="$t0" -v b="$t1" 'BEGIN{printf "cell_wall_s=%.2f\n", b-a}' | tee "$rd/_cell_wall_s.txt"
$PY - "$rd" <<'PYEOF'
import json,sys,pathlib,collections
rd=pathlib.Path(sys.argv[1]); f=rd/"run_RUN-ON.json"
if not f.exists():
    print("  (no run_RUN-ON.json)", sorted(p.name for p in rd.glob('*'))); raise SystemExit
d=json.loads(f.read_text())
for k in ("task_id","accepted","refused","stop_reason","requests_seen","wire_by_protocol",
          "wire_errors","agent_rc","agent_timed_out","agent_wall_s","run_wall_s",
          "visible_passed","visible_total","ws_start_sha256","ws_end_sha256","wire_digest",
          "verdict_sha256","verdict_hash","upstreams_defaulted","attempts_used","retry"):
    if k in d: print(f"  {k:20}= {d[k]}")
idx=rd/"wire_RUN-ON"/"index.jsonl"
if idx.exists():
    c=collections.Counter(); ups=set()
    for line in idx.read_text().splitlines():
        if not line.strip(): continue
        r=json.loads(line)
        c[f"{r.get('method')} {r.get('path')} -> {r.get('status')} [{r.get('wire') or r.get('protocol')}]"]+=1
        if r.get("upstream"): ups.add(r["upstream"])
    print("  proxy_paths         =",dict(c)); print("  upstreams_seen      =",sorted(ups))
PYEOF
echo "--- solution.py exists? ---"; [ -f "$ws/solution.py" ] && wc -c < "$ws/solution.py" || echo "(none)"
echo "=== END $name $(date -u +%FT%T.%NZ) ==="
echo
