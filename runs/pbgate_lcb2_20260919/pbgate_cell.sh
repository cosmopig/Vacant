#!/usr/bin/env bash
# 一格 ＝ 一個公開題庫題目 × 一個臂 × 一次 `vacant run`。
#
# 兩個臂只差**工作區裡有沒有 tests_visible/**：
#   V ── templates/<tid>/ 的完整副本（goal.md／contract.md／run_tests.sh／tests_visible/）
#        ＝ R534 題庫本來的工作區形狀，agent 跑得到那份可見檢查
#   N ── 同樣三個檔，但**不放 tests_visible/**，agent 沒有自檢的路
# 兩個臂的 `--suite` 都指到工作區**外**那一份權威副本（同一個路徑、同一批位元組）。
# hidden/ 兩個臂都一個位元組都不進工作區（V/GT 紅線）。
set -u
ROOT=/var/tmp/vacant_pbgate
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
name="${tid}_${arm}"
ws=$ROOT/ws_$name; rd=$ROOT/rd_$name
rm -rf "$ws" "$rd"; mkdir -p "$ws"
cp "$TPL/$tid/goal.md" "$TPL/$tid/contract.md" "$TPL/$tid/run_tests.sh" "$ws/"
if [ "$arm" = "V" ]; then cp -r "$TPL/$tid/tests_visible" "$ws/"; fi
# 工作區純度擋門（fail-closed）：工作區只准有這個臂該有的那幾個檔，
# 一個位元組的雜質都不行——2026-09-19 第一次發射就是被 macOS 的 `._*`
# AppleDouble 殘留污染（tar 帶進來的），那會讓 `ws_start_sha256`
# 不再等於「公開題庫渲染出來的樣板」。發現得晚不如擋在發射前。
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
  echo "$PY -m vacant.vrun.launcher \\"
  echo "  --workspace $ws \\"
  echo "  --run-dir $rd \\"
  echo "  --suite $TPL/$tid/tests_visible \\"
  echo "  --task-id pbgate_$name \\"
  echo "  --sandbox none \\"
  echo "  --test-timeout $TEST_TIMEOUT \\"
  echo "  --timeout $AGENT_TIMEOUT \\"
  echo "  --retry none \\"
  echo "  --json \\"
  echo "  -- $REPO/ops/vacantrun/wrap_agent.sh $AGENT '$PROMPT'"
  echo "wrapper=timeout 1200"
  echo "arm=$arm  workspace_files=$(cd "$ws" && find . -type f | sort | tr '\n' ' ')"
  echo "ENV VACANT_RUN_UPSTREAM_OPENAI=$VACANT_RUN_UPSTREAM_OPENAI"
  echo "ENV VACANT_RUN_UPSTREAM_ANTHROPIC=$VACANT_RUN_UPSTREAM_ANTHROPIC"
  echo "ENV VACANT_AGENT_MODEL=$VACANT_AGENT_MODEL"
  echo "ENV VACANT=(unset, launcher 預設 1)"
} > "$ROOT/argv/$name.argv.txt"
t0=$(date +%s.%N)
timeout 1200 $PY -m vacant.vrun.launcher \
    --workspace "$ws" --run-dir "$rd" --suite "$TPL/$tid/tests_visible" \
    --task-id "pbgate_$name" --sandbox none \
    --test-timeout "$TEST_TIMEOUT" --timeout "$AGENT_TIMEOUT" --retry none --json \
    -- "$REPO/ops/vacantrun/wrap_agent.sh" "$AGENT" "$PROMPT" \
    > "$ROOT/logs/$name.stdout" 2> "$ROOT/logs/$name.stderr"
rc=$?
t1=$(date +%s.%N)
echo "exit_code=$rc"
echo "$rc" > "$rd/_launcher_exit_code.txt" 2>/dev/null || true
awk -v a="$t0" -v b="$t1" 'BEGIN{printf "cell_wall_s=%.2f\n", b-a}' | tee "$rd/_cell_wall_s.txt"
$PY - "$rd" <<'PY'
import json,sys,pathlib,collections
rd=pathlib.Path(sys.argv[1]); f=rd/"run_RUN-ON.json"
if not f.exists():
    print("  (no run_RUN-ON.json)", sorted(p.name for p in rd.glob('*'))); raise SystemExit
d=json.loads(f.read_text())
for k in ("task_id","accepted","refused","stop_reason","requests_seen","wire_by_protocol",
          "wire_errors","agent_rc","agent_wall_s","run_wall_s","visible_passed","visible_total",
          "ws_start_sha256","ws_end_sha256","wire_digest","verdict_sha256","verdict_hash",
          "upstreams_defaulted","attempts_used","retry"):
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
PY
echo "--- solution.py exists? ---"; [ -f "$ws/solution.py" ] && wc -c < "$ws/solution.py" || echo "(none)"
echo "=== END $name $(date -u +%FT%T.%NZ) ==="
echo
