#!/usr/bin/env bash
# 兩個**零網路**的負控制：證明「退出碼 ＋ stop_reason」單獨不足以證明中介發生。
#   ctl_norequest_refuse  ：agent 位置放 /bin/true（一通模型都不打）
#   ctl_norequest_deliver ：agent 位置放一行 cp（把參考解放進去，一通模型都不打）
# 兩個都不出網、都不碰任何 agent 的設定或憑證。
set -u
ROOT=/var/tmp/vacant_v1matrix
REPO=$ROOT/repo
BANK=$REPO/ops/gain/r535/bank/s1_01_addmul
PY=/usr/bin/python3
export VACANT_RUN_UPSTREAM_OPENAI=http://100.86.226.21:1234/v1
export VACANT_RUN_UPSTREAM_ANTHROPIC=http://100.86.226.21:1234

ctl () {
  name="$1"; task="$2"; shift 2
  ws=$ROOT/wsctl_$name; rd=$ROOT/rdctl_$name
  rm -rf "$ws" "$rd"; mkdir -p "$ws"
  cp "$BANK/$task" "$ws/TASK.md"
  cd "$REPO" || return 2
  echo "=== BEGIN $name $(date -u +%FT%TZ) ==="
  timeout 300 $PY -m vacant.vrun.launcher \
      --workspace "$ws" --run-dir "$rd" --suite "$BANK/tests_visible" \
      --task-id "$name" --sandbox none --test-timeout 30 --timeout 120 --json \
      -- "$@" > "$ROOT/logs/$name.stdout" 2> "$ROOT/logs/$name.stderr"
  rc=$?
  echo "exit_code=$rc"; echo "$rc" > "$rd/_launcher_exit_code.txt"
  $PY - "$rd" <<'PY'
import json,sys,pathlib
d=json.loads((pathlib.Path(sys.argv[1])/"run_RUN-ON.json").read_text())
for k in ("task_id","accepted","stop_reason","requests_seen","wire_by_protocol",
          "agent_rc","visible_passed","visible_total","ws_end_sha256","verdict_hash"):
    print(f"  {k:18}= {d.get(k)}")
PY
  echo "=== END $name $(date -u +%FT%TZ) ==="; echo
}

# 參考解：bank 自帶的那一份（不是我們現寫的）
REF=$BANK/reference
ls "$REF"

ctl ctl_norequest_refuse  TASK.md          /bin/true
ctl ctl_norequest_deliver TASK_explicit.md /bin/sh -c "cp $REF/solution.py ./solution.py"

cd "$REPO"
$PY -m vacant.vrun.verify_receipts --glob "$ROOT/rdctl_*"
