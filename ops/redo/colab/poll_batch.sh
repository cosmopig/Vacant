#!/usr/bin/env bash
# Poll a running Colab redo-harness batch using file downloads (`colab download`),
# printing `redo.py status` from the VM and fetching `runner.log`.
#
# Lesson from ops/colab_campaign_20260927 & ops/colab_dabstep_v37_20261002:
# - Status polling defaults strictly to files + `colab download` (avoids hanging
#   on wedged Jupyter kernels or SSH 429 limits).
# - Pass --live-status to also run `redo.py status` live via ssh/exec.
# - Supports --dry-run (prints exact colab commands; runs nothing remote).
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: poll_batch.sh <state.json> [options]

Options:
  --tail <N>                Number of trailing runner.log lines to show (default: 30)
  --live-status             Also invoke `redo.py status` live on the VM via ssh/exec
  --transport <ssh|exec>    Override transport for --live-status
  --dry-run                 Print exact colab commands; run nothing remote
  -h, --help                Show this help
EOF
}

if [ $# -lt 1 ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
  usage
  exit 0
fi

STATE_FILE="$1"
shift

TAIL_N=30
LIVE_STATUS=0
TRANSPORT_OVERRIDE=""
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --tail) TAIL_N="$2"; shift 2 ;;
    --live-status) LIVE_STATUS=1; shift ;;
    --transport) TRANSPORT_OVERRIDE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ ! -f "$STATE_FILE" ]; then
  echo "error: state file not found: $STATE_FILE" >&2
  exit 2
fi

eval "$(python3 - "$STATE_FILE" <<'PY'
import json, shlex, sys
s = json.loads(open(sys.argv[1], encoding="utf-8").read())
for k, v in (
    ("SESSION", s["session"]),
    ("BATCH_NAME", s.get("batch_name", "")),
    ("GPU", s.get("gpu", "")),
    ("PLAN_ID", s.get("plan_id", "")),
    ("LOCAL_OUT_DIR", s["local_out_dir"]),
    ("REMOTE_WORK_DIR", s.get("remote_work_dir", "/srv/redo")),
    ("REMOTE_RUN_ROOT", s.get("remote_run_root", "/srv/redo/run")),
    ("TRANSPORT", s.get("transport", "ssh")),
    ("COLAB_BIN", s.get("colab_bin", "colab")),
    ("COLAB_CONFIG", s.get("colab_config") or ""),
    ("COLAB_AUTH", s.get("colab_auth") or ""),
):
    print(f"{k}={shlex.quote(str(v))}")
PY
)"

[ -n "$TRANSPORT_OVERRIDE" ] && TRANSPORT="$TRANSPORT_OVERRIDE"

POLL_DIR="${LOCAL_OUT_DIR}/poll"
COLAB_CMD=("$COLAB_BIN")
[ -n "$COLAB_AUTH" ] && COLAB_CMD+=("--auth=${COLAB_AUTH}")
[ -n "$COLAB_CONFIG" ] && COLAB_CMD+=(--config "$COLAB_CONFIG")

fmt_cmd() {
  local out="" a
  for a in "$@"; do
    out+="$(printf '%q ' "$a")"
  done
  printf '%s\n' "${out% }"
}

if [ "$DRY_RUN" = "1" ]; then
  echo "[dry-run] poll_batch.sh state=${STATE_FILE} session=${SESSION} batch=${BATCH_NAME} gpu=${GPU}"
  echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" download -s "$SESSION" "${REMOTE_WORK_DIR}/VM_READY.json" "${POLL_DIR}/VM_READY.json")"
  echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" download -s "$SESSION" "${REMOTE_RUN_ROOT}/STATUS.txt" "${POLL_DIR}/STATUS.txt")"
  echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" download -s "$SESSION" "${REMOTE_RUN_ROOT}/BATCH_DONE.json" "${POLL_DIR}/BATCH_DONE.json")"
  echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" download -s "$SESSION" "${REMOTE_RUN_ROOT}/runner.log" "${POLL_DIR}/runner.log")"
  echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" download -s "$SESSION" "${REMOTE_WORK_DIR}/bootstrap.log" "${POLL_DIR}/bootstrap.log")"
  if [ "$LIVE_STATUS" = "1" ]; then
    if [ "$TRANSPORT" = "ssh" ]; then
      echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" ssh -s "$SESSION" -- python3 "${REMOTE_WORK_DIR}/repo/ops/redo/redo.py" status --root "$REMOTE_RUN_ROOT")"
    else
      echo "[dry-run] printf '!python3 %s status --root %s\\n' $(printf '%q' "${REMOTE_WORK_DIR}/repo/ops/redo/redo.py") $(printf '%q' "$REMOTE_RUN_ROOT") | $(fmt_cmd "${COLAB_CMD[@]}" exec -s "$SESSION")"
    fi
  fi
  exit 0
fi

mkdir -p "$POLL_DIR"

dl_optional() {
  local remote="$1" local_p="$2"
  rm -f "$local_p"
  "${COLAB_CMD[@]}" download -s "$SESSION" "$remote" "$local_p" </dev/null >/dev/null 2>&1 || return 1
  return 0
}

echo "=== Colab Batch Poll: ${BATCH_NAME} (session=${SESSION}, gpu=${GPU}, plan=${PLAN_ID}) ==="

if dl_optional "${REMOTE_WORK_DIR}/VM_READY.json" "${POLL_DIR}/VM_READY.json"; then
  python3 - "${POLL_DIR}/VM_READY.json" <<'PY'
import json, sys
d = json.loads(open(sys.argv[1], encoding="utf-8").read())
print(f"VM_READY : yes ({d.get('ready_utc')})  gpu={d.get('gpu')}  vllm={d.get('vllm_version')}  pi={d.get('pi_version')}  model={d.get('served_model_name')}")
PY
else
  echo "VM_READY : not yet (vm_setup.sh still running or VM unreachable)"
fi

if dl_optional "${REMOTE_RUN_ROOT}/STATUS.txt" "${POLL_DIR}/STATUS.txt"; then
  echo "STATUS   : $(cat "${POLL_DIR}/STATUS.txt")"
else
  echo "STATUS   : no STATUS.txt snapshot yet"
fi

if [ "$LIVE_STATUS" = "1" ]; then
  echo "--- Live redo.py status (${TRANSPORT}) ---"
  if [ "$TRANSPORT" = "ssh" ]; then
    "${COLAB_CMD[@]}" ssh -s "$SESSION" -- python3 "${REMOTE_WORK_DIR}/repo/ops/redo/redo.py" status --root "$REMOTE_RUN_ROOT" </dev/null || true
  else
    printf '!python3 %s status --root %s\n' "${REMOTE_WORK_DIR}/repo/ops/redo/redo.py" "$REMOTE_RUN_ROOT" | "${COLAB_CMD[@]}" exec -s "$SESSION" || true
  fi
fi

if dl_optional "${REMOTE_RUN_ROOT}/BATCH_DONE.json" "${POLL_DIR}/BATCH_DONE.json"; then
  python3 - "${POLL_DIR}/BATCH_DONE.json" <<'PY'
import json, sys
d = json.loads(open(sys.argv[1], encoding="utf-8").read())
print(f"DONE     : YES (ended={d.get('ended_utc')}, redo_rc={d.get('redo_rc')}, tar={d.get('tarball_path')})")
PY
  echo "NEXT     : bash ops/redo/colab/fetch_batch.sh ${STATE_FILE}"
else
  echo "DONE     : in progress"
fi

if dl_optional "${REMOTE_RUN_ROOT}/runner.log" "${POLL_DIR}/runner.log"; then
  echo "--- runner.log (last ${TAIL_N} lines; saved to ${POLL_DIR}/runner.log) ---"
  tail -n "$TAIL_N" "${POLL_DIR}/runner.log"
elif dl_optional "${REMOTE_WORK_DIR}/bootstrap.log" "${POLL_DIR}/bootstrap.log"; then
  echo "--- bootstrap.log (last ${TAIL_N} lines; runner.log not created yet) ---"
  tail -n "$TAIL_N" "${POLL_DIR}/bootstrap.log"
else
  echo "(no runner.log or bootstrap.log downloadable yet; check \`colab sessions\` / \`colab status -s ${SESSION}\`)"
fi
