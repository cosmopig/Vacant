#!/usr/bin/env bash
# Fetch and verify the results tarball from a Colab redo-harness batch, then stop the VM.
#
# Lessons carried over from ops/colab_campaign_20260927 & ops/colab_dabstep_v37_20261002:
# - Completion check & retrieval use `colab download` (no brittle console scraping).
# - Verifies SHA-256 and tarball contents BEFORE calling `colab stop`.
# - If verification fails, does NOT stop the VM so data is never lost.
# - Always stops the VM once verified (unless --no-stop) so idle GPUs never burn CU.
# - Never calls `colab pay`.
# - Supports --dry-run (prints exact colab commands; runs nothing remote).
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || cd "${SCRIPT_DIR}/../../.." && pwd)

usage() {
  cat <<'EOF'
Usage: fetch_batch.sh <state.json> [options]

Options:
  --no-stop                 Keep the Colab session running after verified download
  --force                   Allow fetching an in-progress run (creates tarball via ssh/exec)
  --transport <ssh|exec>    Override transport when --force must tar on the VM
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

NO_STOP=0
FORCE=0
TRANSPORT_OVERRIDE=""
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --no-stop) NO_STOP=1; shift ;;
    --force) FORCE=1; shift ;;
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
    ("LOCAL_OUT_DIR", s["local_out_dir"]),
    ("REMOTE_WORK_DIR", s.get("remote_work_dir", "/srv/redo")),
    ("REMOTE_RUN_ROOT", s.get("remote_run_root", "/srv/redo/run")),
    ("REMOTE_RESULTS_TAR", s.get("remote_results_tar", "/content/redo_results.tar.gz")),
    ("TRANSPORT", s.get("transport", "ssh")),
    ("COLAB_BIN", s.get("colab_bin", "colab")),
    ("COLAB_CONFIG", s.get("colab_config") or ""),
    ("COLAB_AUTH", s.get("colab_auth") or ""),
):
    print(f"{k}={shlex.quote(str(v))}")
PY
)"

[ -n "$TRANSPORT_OVERRIDE" ] && TRANSPORT="$TRANSPORT_OVERRIDE"

COLAB_CMD=("$COLAB_BIN")
[ -n "$COLAB_AUTH" ] && COLAB_CMD+=("--auth=${COLAB_AUTH}")
[ -n "$COLAB_CONFIG" ] && COLAB_CMD+=(--config "$COLAB_CONFIG")

LOCAL_TAR="${LOCAL_OUT_DIR}/results.tar.gz"
LOCAL_SHA="${LOCAL_OUT_DIR}/results.tar.gz.sha256"
LOCAL_DONE="${LOCAL_OUT_DIR}/BATCH_DONE.json"
LOCAL_EXTRACT="${LOCAL_OUT_DIR}/run"
REMOTE_TAR_SHA="${REMOTE_RESULTS_TAR}.sha256"

fmt_cmd() {
  local out="" a
  for a in "$@"; do
    out+="$(printf '%q ' "$a")"
  done
  printf '%s\n' "${out% }"
}

TAR_REMOTE_CMD="tar -czf ${REMOTE_RESULTS_TAR}.tmp -C ${REMOTE_RUN_ROOT} . && mv -f ${REMOTE_RESULTS_TAR}.tmp ${REMOTE_RESULTS_TAR} && sha256sum ${REMOTE_RESULTS_TAR} > ${REMOTE_TAR_SHA}"

if [ "$DRY_RUN" = "1" ]; then
  echo "[dry-run] fetch_batch.sh state=${STATE_FILE} session=${SESSION} batch=${BATCH_NAME} force=${FORCE} no_stop=${NO_STOP}"
  echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" download -s "$SESSION" "${REMOTE_RUN_ROOT}/BATCH_DONE.json" "$LOCAL_DONE")"
  if [ "$FORCE" = "1" ]; then
    if [ "$TRANSPORT" = "ssh" ]; then
      echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" ssh -s "$SESSION" -- bash -lc "$TAR_REMOTE_CMD")"
    else
      echo "[dry-run] printf '!%s\\n' $(printf '%q' "$TAR_REMOTE_CMD") | $(fmt_cmd "${COLAB_CMD[@]}" exec -s "$SESSION")"
    fi
  fi
  echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" download -s "$SESSION" "$REMOTE_RESULTS_TAR" "$LOCAL_TAR")"
  echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" download -s "$SESSION" "$REMOTE_TAR_SHA" "$LOCAL_SHA")"
  echo "[dry-run] verify sha256sum of ${LOCAL_TAR} against ${LOCAL_SHA} and tar -tzf contains RUN.json"
  echo "[dry-run] extract ${LOCAL_TAR} -> ${LOCAL_EXTRACT}"
  if [ "$NO_STOP" = "0" ]; then
    echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" stop -s "$SESSION")"
  else
    echo "[dry-run] --no-stop set: skipping colab stop"
  fi
  exit 0
fi

mkdir -p "$LOCAL_OUT_DIR"

HAVE_DONE=0
rm -f "$LOCAL_DONE"
if "${COLAB_CMD[@]}" download -s "$SESSION" "${REMOTE_RUN_ROOT}/BATCH_DONE.json" "$LOCAL_DONE" </dev/null >/dev/null 2>&1; then
  HAVE_DONE=1
fi

if [ "$HAVE_DONE" = "0" ]; then
  if [ "$FORCE" = "0" ]; then
    echo "error: ${REMOTE_RUN_ROOT}/BATCH_DONE.json not found on session ${SESSION}." >&2
    echo "       The batch may still be running (check with poll_batch.sh), or pass --force to tar & fetch a partial snapshot." >&2
    exit 3
  fi
  echo "1/4 Batch not finished (--force): creating partial snapshot tarball on VM (${TRANSPORT})"
  if [ "$TRANSPORT" = "ssh" ]; then
    "${COLAB_CMD[@]}" ssh -s "$SESSION" -- bash -lc "$TAR_REMOTE_CMD" </dev/null
  else
    printf '!%s\n' "$TAR_REMOTE_CMD" | "${COLAB_CMD[@]}" exec -s "$SESSION"
  fi
else
  # Read tarball path recorded in BATCH_DONE.json if present.
  REMOTE_RESULTS_TAR=$(python3 -c 'import json,sys; d=json.loads(open(sys.argv[1]).read()); print(d.get("tarball_path") or sys.argv[2])' "$LOCAL_DONE" "$REMOTE_RESULTS_TAR")
  REMOTE_TAR_SHA="${REMOTE_RESULTS_TAR}.sha256"
  echo "1/4 BATCH_DONE.json confirmed on VM (tarball: ${REMOTE_RESULTS_TAR})"
fi

echo "2/4 Downloading tarball and sha256 via colab download"
rm -f "$LOCAL_TAR" "$LOCAL_SHA"
"${COLAB_CMD[@]}" download -s "$SESSION" "$REMOTE_RESULTS_TAR" "$LOCAL_TAR" </dev/null
"${COLAB_CMD[@]}" download -s "$SESSION" "$REMOTE_TAR_SHA" "$LOCAL_SHA" </dev/null

echo "3/4 Verifying tarball integrity (SHA-256 + archive listing)"
WANT_SHA=$(awk '{print $1}' "$LOCAL_SHA" | head -1)
GOT_SHA=$(sha256sum "$LOCAL_TAR" | awk '{print $1}')
if [ -z "$WANT_SHA" ] || [ "$GOT_SHA" != "$WANT_SHA" ]; then
  echo "ERROR: tarball SHA-256 mismatch! got=${GOT_SHA} expected=${WANT_SHA}" >&2
  echo "       VM session ${SESSION} was NOT stopped so you can retry download." >&2
  exit 1
fi
if [ "$HAVE_DONE" = "1" ]; then
  DONE_SHA=$(python3 -c 'import json,sys; print(json.loads(open(sys.argv[1]).read()).get("tarball_sha256",""))' "$LOCAL_DONE")
  if [ -n "$DONE_SHA" ] && [ "$GOT_SHA" != "$DONE_SHA" ]; then
    echo "ERROR: tarball SHA-256 (${GOT_SHA}) != BATCH_DONE.json (${DONE_SHA})" >&2
    echo "       VM session ${SESSION} was NOT stopped." >&2
    exit 1
  fi
fi

# Verify tar structure and presence of RUN.json.
LISTING=$(tar -tzf "$LOCAL_TAR")
if ! grep -qE '(^\./)?RUN\.json$' <<<"$LISTING"; then
  echo "ERROR: tarball ${LOCAL_TAR} does not contain RUN.json; VM session ${SESSION} was NOT stopped." >&2
  exit 1
fi
if [ "$HAVE_DONE" = "1" ] && ! grep -qE '(^\./)?REPORT\.json$' <<<"$LISTING"; then
  echo "WARNING: completed tarball does not contain REPORT.json" >&2
fi

rm -rf "$LOCAL_EXTRACT" && mkdir -p "$LOCAL_EXTRACT"
tar -xzf "$LOCAL_TAR" -C "$LOCAL_EXTRACT"
echo "    Verified & extracted -> ${LOCAL_EXTRACT} (sha256=${GOT_SHA})"

if [ -f "${REPO_ROOT}/ops/redo/redo.py" ]; then
  python3 "${REPO_ROOT}/ops/redo/redo.py" status --root "$LOCAL_EXTRACT" || true
fi

STOPPED_UTC=""
if [ "$NO_STOP" = "0" ]; then
  echo "4/4 Stopping Colab session ${SESSION}"
  "${COLAB_CMD[@]}" stop -s "$SESSION"
  STOPPED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
else
  echo "4/4 --no-stop set: leaving session ${SESSION} running (remember to stop it manually!)"
fi

# Update state file atomically.
python3 - "$STATE_FILE" "$GOT_SHA" "$STOPPED_UTC" <<'PY'
import json, os, pathlib, sys, time
state_p, tar_sha, stopped_utc = sys.argv[1:]
p = pathlib.Path(state_p)
doc = json.loads(p.read_text(encoding="utf-8"))
doc["fetched_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
doc["tarball_sha256"] = tar_sha
if stopped_utc:
    doc["stopped_utc"] = stopped_utc
tmp = p.with_name(p.name + f".tmp.{os.getpid()}")
tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, p)
PY

echo "FETCH_OK ${LOCAL_EXTRACT}"
