#!/usr/bin/env bash
# VM-side batch orchestrator invoked under setsid/nohup by launch_batch.sh
# (and directly exercised by test_local_e2e.py).
#
# Steps:
#   1. Unpack repo tarball (if --repo-tar) and bank tarball (if --bank-tar).
#   2. Run vm_setup.sh to install tools, render models.json, start vLLM, write VM_READY.json.
#   3. Start a background status-file writer so host polling works via `colab download` alone.
#   4. Run `python3 ops/redo/redo.py run --plan ... --bank ... --root ... --allow-uncommitted-plan`.
#      (--allow-uncommitted-plan is passed ONLY because git archive has no .git/;
#       local launch_batch.sh enforces the committed-plan check before archiving.)
#   5. Write final STATUS.txt, archive run root to tarball + .sha256, write BATCH_DONE.json.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_DIR=""
REPO_TAR=""
BANK_DIR=""
BANK_TAR=""
PLAN=""
VLLM_CONFIG=""
LAUNCH_META=""
WORK_DIR="/srv/redo"
RUN_ROOT=""
PI_DIR="${HOME}/.pi/agent"
TAR_OUT=""
STATUS_INTERVAL_S=60
SKIP_INSTALL=0
SKIP_VLLM=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: vm_run_batch.sh --plan <plan.json> --vllm-config <cfg.json> [options]

Options:
  --repo-dir <dir>         Unpacked repo directory (default: <work-dir>/repo)
  --repo-tar <tar.gz>      Optional repo tarball to unpack into --repo-dir
  --bank-dir <dir>         Unpacked bank directory (default: <work-dir>/bank)
  --bank-tar <tar.gz>      Optional bank tarball to unpack into --bank-dir
  --plan <path>            Plan JSON file (required)
  --vllm-config <path>     vLLM config JSON (required)
  --launch-meta <path>     Optional launch_meta.json uploaded from local side
  --work-dir <dir>         Working directory (default: /srv/redo)
  --root <dir>             redo.py run root (default: <work-dir>/run)
  --pi-dir <dir>           pi agent config dir for models.json (default: ~/.pi/agent)
  --tar-out <path>         Path to write final results tarball (default: <work-dir>/results.tar.gz)
  --status-interval <sec>  Interval for writing STATUS.txt snapshots (default: 60)
  --skip-install           Pass --skip-install to vm_setup.sh
  --skip-vllm              Pass --skip-vllm to vm_setup.sh
  --dry-run                Print exact commands without executing
  -h, --help               Show this help
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --repo-dir) REPO_DIR="$2"; shift 2 ;;
    --repo-tar) REPO_TAR="$2"; shift 2 ;;
    --bank-dir) BANK_DIR="$2"; shift 2 ;;
    --bank-tar) BANK_TAR="$2"; shift 2 ;;
    --plan) PLAN="$2"; shift 2 ;;
    --vllm-config) VLLM_CONFIG="$2"; shift 2 ;;
    --launch-meta) LAUNCH_META="$2"; shift 2 ;;
    --work-dir) WORK_DIR="$2"; shift 2 ;;
    --root) RUN_ROOT="$2"; shift 2 ;;
    --pi-dir) PI_DIR="$2"; shift 2 ;;
    --tar-out) TAR_OUT="$2"; shift 2 ;;
    --status-interval) STATUS_INTERVAL_S="$2"; shift 2 ;;
    --skip-install) SKIP_INSTALL=1; shift ;;
    --skip-vllm) SKIP_VLLM=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$PLAN" ] || [ -z "$VLLM_CONFIG" ]; then
  echo "error: --plan and --vllm-config are required" >&2
  exit 2
fi

REPO_DIR="${REPO_DIR:-${WORK_DIR}/repo}"
BANK_DIR="${BANK_DIR:-${WORK_DIR}/bank}"
RUN_ROOT="${RUN_ROOT:-${WORK_DIR}/run}"
TAR_OUT="${TAR_OUT:-${WORK_DIR}/results.tar.gz}"
READY_FILE="${WORK_DIR}/VM_READY.json"

SETUP_FLAGS=(--config "$VLLM_CONFIG" --work-dir "$WORK_DIR" --pi-dir "$PI_DIR" --ready-file "$READY_FILE")
[ "$SKIP_INSTALL" = "1" ] && SETUP_FLAGS+=(--skip-install)
[ "$SKIP_VLLM" = "1" ] && SETUP_FLAGS+=(--skip-vllm)

if [ "$DRY_RUN" = "1" ]; then
  echo "[dry-run] vm_run_batch.sh work_dir=${WORK_DIR} run_root=${RUN_ROOT}"
  [ -n "$REPO_TAR" ] && echo "[dry-run] mkdir -p ${REPO_DIR} && tar -xzf ${REPO_TAR} -C ${REPO_DIR} --strip-components=1"
  [ -n "$BANK_TAR" ] && echo "[dry-run] mkdir -p ${BANK_DIR} && tar -xzf ${BANK_TAR} -C ${BANK_DIR}"
  echo "[dry-run] bash ${SCRIPT_DIR}/vm_setup.sh ${SETUP_FLAGS[*]} --dry-run"
  bash "${SCRIPT_DIR}/vm_setup.sh" "${SETUP_FLAGS[@]}" --dry-run
  echo "[dry-run] python3 ${REPO_DIR}/ops/redo/redo.py run --plan ${PLAN} --bank ${BANK_DIR} --root ${RUN_ROOT} --allow-uncommitted-plan"
  echo "[dry-run] python3 ${REPO_DIR}/ops/redo/redo.py status --root ${RUN_ROOT} > ${RUN_ROOT}/STATUS.txt"
  echo "[dry-run] tar -czf ${TAR_OUT} -C ${RUN_ROOT} . && sha256sum ${TAR_OUT} > ${TAR_OUT}.sha256"
  echo "[dry-run] write ${RUN_ROOT}/BATCH_DONE.json"
  exit 0
fi

export PATH="/usr/local/bin:/opt/redo/pi/bin:/opt/redo/node/bin:/opt/redo/opencode/bin:${PATH}"
mkdir -p "$WORK_DIR" "$RUN_ROOT"

log() {
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)  [vm_run_batch] $*"
}

if [ -n "$REPO_TAR" ]; then
  log "Unpacking repo tarball ${REPO_TAR} -> ${REPO_DIR}"
  rm -rf "$REPO_DIR" && mkdir -p "$REPO_DIR"
  tar -xzf "$REPO_TAR" -C "$REPO_DIR" --strip-components=1
fi

if [ -n "$BANK_TAR" ]; then
  log "Unpacking bank tarball ${BANK_TAR} -> ${BANK_DIR}"
  rm -rf "$BANK_DIR" && mkdir -p "$BANK_DIR"
  tar -xzf "$BANK_TAR" -C "$BANK_DIR"
fi

REDO_PY="${REPO_DIR}/ops/redo/redo.py"
VM_SETUP="${REPO_DIR}/ops/redo/colab/vm_setup.sh"
[ -x "$VM_SETUP" ] || VM_SETUP="${SCRIPT_DIR}/vm_setup.sh"

if [ ! -f "$REDO_PY" ]; then
  echo "error: redo.py not found at ${REDO_PY}" >&2
  exit 1
fi

log "Running vm_setup.sh"
bash "$VM_SETUP" "${SETUP_FLAGS[@]}"

# Save provenance snapshot inside run root so it travels inside results.tar.gz.
cp -f "$READY_FILE" "${RUN_ROOT}/VM_READY.json"
cp -f "$VLLM_CONFIG" "${RUN_ROOT}/vllm_config.json"
if [ -n "$LAUNCH_META" ] && [ -f "$LAUNCH_META" ]; then
  cp -f "$LAUNCH_META" "${RUN_ROOT}/launch_meta.json"
fi

# Background status snapshot loop so host can inspect progress purely via `colab download`.
STATUS_PID=""
cleanup_status() {
  if [ -n "$STATUS_PID" ] && kill -0 "$STATUS_PID" 2>/dev/null; then
    kill "$STATUS_PID" 2>/dev/null || true
    wait "$STATUS_PID" 2>/dev/null || true
  fi
}
trap cleanup_status EXIT

(
  while true; do
    sleep "$STATUS_INTERVAL_S"
    if [ -f "${RUN_ROOT}/RUN.json" ]; then
      if out=$(python3 "$REDO_PY" status --root "$RUN_ROOT" 2>&1); then
        printf '%s  %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$out" > "${RUN_ROOT}/STATUS.txt.tmp"
        mv -f "${RUN_ROOT}/STATUS.txt.tmp" "${RUN_ROOT}/STATUS.txt"
      fi
    fi
  done
) </dev/null >/dev/null 2>&1 &
STATUS_PID=$!

log "Starting redo.py run (plan=${PLAN}, bank=${BANK_DIR}, root=${RUN_ROOT})"
set +e
python3 "$REDO_PY" run \
  --plan "$PLAN" \
  --bank "$BANK_DIR" \
  --root "$RUN_ROOT" \
  --allow-uncommitted-plan
REDO_RC=$?
set -e

cleanup_status
STATUS_PID=""

STATUS_LINE=""
if [ -f "${RUN_ROOT}/RUN.json" ]; then
  STATUS_LINE=$(python3 "$REDO_PY" status --root "$RUN_ROOT" 2>&1 || true)
  printf '%s  %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$STATUS_LINE" > "${RUN_ROOT}/STATUS.txt"
fi
log "redo.py exited rc=${REDO_RC} status=${STATUS_LINE}"

# Archive run root + write sha256 + write BATCH_DONE.json atomically.
mkdir -p "$(dirname "$TAR_OUT")"
TMP_TAR="${TAR_OUT}.tmp.$$"
# 11/24（W3-5 JS 重跑 VOID 的根因 1）：不打包工作區副本——rc5 起每次嘗試都有自己的 node_modules 副本，JS 批次的整包會到數 GB；
# 結論只用得到 cell.json、result.json、日誌與 REPORT。排除清單與 fetch_batch.sh／colab_snapshot2.sh 共用同一份。
tar -czf "$TMP_TAR" -C "$RUN_ROOT" --exclude=node_modules --exclude='attempt_*/w' --exclude='snap-*' \
    --exclude='start-copy-*' --exclude='start-snap-*' --exclude='bkp-*' --exclude=__pycache__ . || [ $? -eq 1 ]
mv -f "$TMP_TAR" "$TAR_OUT"
TAR_SHA=$(sha256sum "$TAR_OUT" | cut -d' ' -f1)
printf '%s  %s\n' "$TAR_SHA" "$(basename "$TAR_OUT")" > "${TAR_OUT}.sha256"

python3 - "${RUN_ROOT}/BATCH_DONE.json" "$REDO_RC" "$STATUS_LINE" "$TAR_OUT" "$TAR_SHA" <<'PY'
import json, os, pathlib, sys, time
out_p, rc_s, status_line, tar_out, tar_sha = sys.argv[1:]
doc = {
    "schema": "vacant.redo.colab.done/1",
    "ended_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "redo_rc": int(rc_s),
    "status": status_line,
    "tarball_path": tar_out,
    "tarball_sha256": tar_sha,
}
p = pathlib.Path(out_p)
tmp = p.with_name(p.name + f".tmp.{os.getpid()}")
tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, p)
PY

log "Batch finished: tar=${TAR_OUT} sha256=${TAR_SHA}"
exit "$REDO_RC"
