#!/usr/bin/env bash
# 一格 = 一次 `vacant run`。agent 降到 uid 1001，proxy 留在 user1。
set -uo pipefail
R=/var/tmp/v3egress
NAME="$1"; INNER="$2"
BANK=$R/repo/ops/gain/r535/bank/s1_01_addmul
ws=$R/ws_$NAME; rd=$R/rd_$NAME
rm -rf "$ws" "$rd"; mkdir -p "$ws"; chmod 777 "$ws"
cp "$BANK/TASK_explicit.md" "$ws/TASK.md"; chmod 666 "$ws/TASK.md"
export VACANT_RUN_UPSTREAM_OPENAI=http://100.86.226.21:1234/v1
export VACANT_AGENT_MODEL=gemma-4-12b-it-qat
cd "$R/repo"
timeout 420 python3 -m vacant.vrun.launcher \
    --workspace "$ws" --run-dir "$rd" --suite "$BANK/tests_visible" \
    --task-id "$NAME" --sandbox none --test-timeout 30 --timeout 330 --json \
    -- "$R/bin/outer.sh" "$R/bin/$INNER" \
       "Read TASK.md and do what it says. Use your tools to write the file." \
    > "$R/logs/$NAME.stdout" 2> "$R/logs/$NAME.stderr"
echo "launcher exit=$?"
python3 - "$rd" "$NAME" <<'PY'
import json,sys,pathlib
p=pathlib.Path(sys.argv[1])/"run_RUN-ON.json"
if not p.exists(): print("  <沒有 run_RUN-ON.json>"); sys.exit()
d=json.loads(p.read_text())
for k in ("accepted","stop_reason","requests_seen","wire_by_protocol","agent_rc",
          "agent_wall_s","wire_errors","upstreams_defaulted","verdict_sha256"):
    print(f"  {k:20}= {d.get(k)}")
PY
echo "  --- agent stdout 尾 ---"; tail -4 "$R/logs/$NAME.stdout" | head -4
echo "  --- agent stderr 尾 ---"; tail -6 "$R/logs/$NAME.stderr"
