#!/usr/bin/env bash
# 5 agent × 2 格 × 2 次 = 20 格，同一台機器（1004）、同一個模型、同一題、同一天。
set -u
ROOT=/var/tmp/vacant_v1matrix
REPO=$ROOT/repo
BANK=$REPO/ops/gain/r535/bank/s1_01_addmul
PY=/usr/bin/python3
export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:/home/user1/.local/bin:$PATH
export VACANT_RUN_UPSTREAM_OPENAI=http://100.86.226.21:1234/v1
export VACANT_RUN_UPSTREAM_ANTHROPIC=http://100.86.226.21:1234
export VACANT_AGENT_MODEL=gemma-4-12b-it-qat
export VACANT_HERMES_BIN=$ROOT/hv/bin/hermes
mkdir -p "$ROOT/logs"

cell () {
  agent="$1"; grid="$2"; rep="$3"
  case "$grid" in
    refuse)  task=TASK.md ;;
    deliver) task=TASK_explicit.md ;;
    *) echo "bad grid $grid"; return 2 ;;
  esac
  name="${agent}_${grid}_r${rep}"
  ws=$ROOT/ws_$name; rd=$ROOT/rd_$name
  rm -rf "$ws" "$rd"; mkdir -p "$ws"
  cp "$BANK/$task" "$ws/TASK.md"
  cd "$REPO" || return 2
  echo "=== BEGIN $name $(date -u +%FT%TZ) ==="
  timeout 1500 $PY -m vacant.vrun.launcher \
      --workspace "$ws" --run-dir "$rd" --suite "$BANK/tests_visible" \
      --task-id "$name" --sandbox none --test-timeout 30 --timeout 1200 --json \
      -- "$REPO/ops/vacantrun/wrap_agent.sh" "$agent" \
         "Read TASK.md and do what it says. Use your tools to write the file." \
      > "$ROOT/logs/$name.stdout" 2> "$ROOT/logs/$name.stderr"
  rc=$?
  echo "exit_code=$rc"
  echo "$rc" > "$rd/_launcher_exit_code.txt" 2>/dev/null || true
  $PY - "$rd" <<'PY'
import json,sys,pathlib,collections
rd=pathlib.Path(sys.argv[1])
f=rd/"run_RUN-ON.json"
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
    print("  proxy_paths         =",dict(c))
    print("  upstreams_seen      =",sorted(ups))
PY
  echo "--- solution.py ---"; cat "$ws/solution.py" 2>/dev/null || echo "(none)"
  echo "=== END $name $(date -u +%FT%TZ) ==="
  echo
}

echo "#### 負控制：收據驗章器 selftest（發射前）"
cd "$REPO" && $PY -m vacant.vrun.verify_receipts --selftest
echo "#### df 派工前"; df -h / | tail -1
echo "#### 版本"
pi --version 2>&1 | head -1
opencode --version 2>&1 | head -1
claude --version 2>&1 | head -1
codex --version 2>&1 | head -1
"$VACANT_HERMES_BIN" --version 2>&1 | head -1
echo

for rep in 1 2; do
  for agent in pi opencode claude codex hermes; do
    for grid in refuse deliver; do
      cell "$agent" "$grid" "$rep"
    done
  done
done

echo "#### df 收工後"; df -h / | tail -1
echo "#### ALL DONE $(date -u +%FT%TZ)"
