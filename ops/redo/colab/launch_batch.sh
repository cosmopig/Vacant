#!/usr/bin/env bash
# Local launcher for preregistered redo-harness batches on a Google Colab GPU VM.
#
# Usage:
#   ops/redo/colab/launch_batch.sh <plan.json> <bank-dir> [options]
#
# Safety & provenance:
# - Enforces that <plan.json> is committed at --commit (default HEAD) unless
#   --allow-uncommitted-plan is passed explicitly (for smoke tests only).
# - Packages the repo snapshot with `git archive <commit>` (frozen by commit SHA).
# - Packages <bank-dir>, uploads repo + bank + plan + vLLM config + bootstrap script.
# - Records GPU type, commit SHA, plan SHA-256, and session name into a local state file.
# - Never runs `colab pay`.
# - Supports --dry-run (prints exact colab commands; executes nothing remote).
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)

usage() {
  cat <<'EOF'
Usage: launch_batch.sh <plan.json> <bank-dir> [options]

Positional arguments:
  <plan.json>                Redo plan JSON (schema: vacant.redo.plan/1)
  <bank-dir>                 Local task bank directory (<bank>/<task>/workspace/)

Options:
  --gpu <GPU>                Colab GPU type: G4, A100, L4, T4, H100 (default: G4)
  --high-mem                 Pass --high-mem to `colab new`
  --session <name>           Colab session name (default: redo-<plan_id>-<UTC>)
  --commit <sha>             Git commit SHA to archive & freeze (default: HEAD)
  --vllm-config <path>       vLLM config JSON (default: ops/redo/colab/vllm_gemma4_12b.json)
  --batch-name <name>        Batch folder name (default: <plan_id>_<UTC>)
  --out-dir <dir>            Local output root (default: ~/dev/ops/redo_runs_colab/<batch>)
  --transport <ssh|exec>     Remote execution transport (default: ssh)
  --colab-bin <path>         Path to colab CLI binary (default: colab)
  --colab-config <path>      Optional `colab --config <path>` for session isolation
  --colab-auth <adc|oauth2>  Optional `colab --auth=<mode>` flag
  --allow-uncommitted-plan   Allow uncommitted plan.json (smoke tests ONLY)
  --extra-wheel <path>       Upload a product wheel and install it into /opt/redo/rc_venv on the VM
                             (plans reference /opt/redo/rc_venv/bin/vacant); its sha256 goes into launch metadata
  --dry-run                  Print exact colab commands; run nothing remote
  -h, --help                 Show this help
EOF
}

GPU="G4"
HIGH_MEM=0
SESSION=""
COMMIT_REF="HEAD"
VLLM_CONFIG="${SCRIPT_DIR}/vllm_gemma4_12b.json"
BATCH_NAME=""
OUT_DIR=""
TRANSPORT="ssh"
COLAB_BIN="${COLAB_BIN:-colab}"
COLAB_CONFIG=""
COLAB_AUTH=""
ALLOW_UNCOMMITTED=0
DRY_RUN=0
EXTRA_WHEEL=""
POSITIONAL=()

while [ $# -gt 0 ]; do
  case "$1" in
    --gpu) GPU="$2"; shift 2 ;;
    --high-mem) HIGH_MEM=1; shift ;;
    --session) SESSION="$2"; shift 2 ;;
    --commit) COMMIT_REF="$2"; shift 2 ;;
    --vllm-config) VLLM_CONFIG="$2"; shift 2 ;;
    --batch-name) BATCH_NAME="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --transport) TRANSPORT="$2"; shift 2 ;;
    --colab-bin) COLAB_BIN="$2"; shift 2 ;;
    --colab-config) COLAB_CONFIG="$2"; shift 2 ;;
    --colab-auth) COLAB_AUTH="$2"; shift 2 ;;
    --allow-uncommitted-plan) ALLOW_UNCOMMITTED=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --extra-wheel) EXTRA_WHEEL="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    *) POSITIONAL+=("$1"); shift ;;
  esac
done

if [ "${#POSITIONAL[@]}" -ne 2 ]; then
  echo "error: expected <plan.json> and <bank-dir>" >&2
  usage >&2
  exit 2
fi
PLAN_ARG="${POSITIONAL[0]}"
BANK_ARG="${POSITIONAL[1]}"

case "$GPU" in
  T4|L4|G4|A100|H100) ;;
  *) echo "error: unsupported --gpu '$GPU' (must be one of T4, L4, G4, A100, H100; colab CLI silently falls back to A100 on unknown names)" >&2; exit 2 ;;
esac

case "$TRANSPORT" in
  ssh|exec) ;;
  *) echo "error: --transport must be 'ssh' or 'exec'" >&2; exit 2 ;;
esac

if [ ! -f "$PLAN_ARG" ]; then
  echo "error: plan file not found: $PLAN_ARG" >&2
  exit 2
fi
if [ ! -d "$BANK_ARG" ]; then
  echo "error: bank directory not found: $BANK_ARG" >&2
  exit 2
fi
if [ ! -f "$VLLM_CONFIG" ]; then
  echo "error: vLLM config not found: $VLLM_CONFIG" >&2
  exit 2
fi

PLAN_ABS=$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$PLAN_ARG")
BANK_ABS=$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$BANK_ARG")
VLLM_CFG_ABS=$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$VLLM_CONFIG")

COMMIT_SHA=$(git -C "$REPO_ROOT" rev-parse --verify "${COMMIT_REF}^{commit}")
SHORT_SHA="${COMMIT_SHA:0:12}"

# Validate plan JSON, bank task coverage, and provider/model compatibility with vLLM config.
eval "$(python3 - "$PLAN_ABS" "$BANK_ABS" "$VLLM_CFG_ABS" <<'PY'
import hashlib, json, pathlib, shlex, sys

plan_p, bank_p, cfg_p = map(pathlib.Path, sys.argv[1:])
plan = json.loads(plan_p.read_text(encoding="utf-8"))
cfg = json.loads(cfg_p.read_text(encoding="utf-8"))

if plan.get("schema") != "vacant.redo.plan/1":
    sys.exit(f"error: unexpected plan schema {plan.get('schema')!r}")
for k in ("id", "tasks", "reps", "arms", "pair", "agent", "providers", "attempt_timeout_s"):
    if k not in plan:
        sys.exit(f"error: plan missing required key {k!r}")

missing = [t for t in plan["tasks"] if not (bank_p / t / "workspace").is_dir()]
if missing:
    sys.exit(f"error: bank {bank_p} missing {len(missing)} tasks (first: {missing[0]})")

served = cfg.get("served_model_name", "")
known_providers = {"colab-vllm", "colab-vllm-nothink", "colab-vllm-think"}
if cfg.get("provider_name"):
    known_providers.add(cfg["provider_name"])

warnings = []
for p in plan["providers"]:
    if p.get("provider") and p["provider"] not in known_providers:
        warnings.append(f"plan provider {p['provider']!r} not in rendered models.json providers {sorted(known_providers)}")
    if p.get("model") and served and p["model"] != served:
        warnings.append(f"plan model {p['model']!r} != vLLM served_model_name {served!r}")

canon = json.dumps({k: v for k, v in plan.items() if not k.startswith("_")},
                   ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
plan_sha = hashlib.sha256(canon).hexdigest()

print(f"PLAN_ID={shlex.quote(str(plan['id']))}")
print(f"PLAN_SHA256={shlex.quote(plan_sha)}")
print(f"N_TASKS={len(plan['tasks'])}")
print(f"REPS={int(plan['reps'])}")
print(f"PLAN_WARNINGS={shlex.quote('; '.join(warnings))}")
PY
)"

if [ -n "$PLAN_WARNINGS" ]; then
  echo "WARNING: $PLAN_WARNINGS" >&2
fi

# Enforce preregistration freeze locally before archiving (since git archive omits .git/).
if [ "$ALLOW_UNCOMMITTED" = "0" ]; then
  case "$PLAN_ABS" in
    "${REPO_ROOT}/"*)
      PLAN_REL="${PLAN_ABS#"${REPO_ROOT}/"}"
      COMMITTED_SHA=$(git -C "$REPO_ROOT" show "${COMMIT_SHA}:${PLAN_REL}" 2>/dev/null | sha256sum | cut -d' ' -f1 || true)
      LOCAL_FILE_SHA=$(sha256sum "$PLAN_ABS" | cut -d' ' -f1)
      if [ -z "$COMMITTED_SHA" ] || [ "$COMMITTED_SHA" != "$LOCAL_FILE_SHA" ]; then
        echo "error: plan ${PLAN_REL} does not match committed version at ${COMMIT_SHA} (preregistration must be committed first; use --allow-uncommitted-plan for smoke tests only)" >&2
        exit 2
      fi
      ;;
    *)
      echo "error: plan ${PLAN_ABS} is outside repo ${REPO_ROOT}; commit it inside the repo or pass --allow-uncommitted-plan for smoke tests" >&2
      exit 2
      ;;
  esac
fi

TS=$(date -u +%Y%m%dT%H%M%SZ)
SAFE_PLAN_ID=$(python3 -c 'import re,sys; print(re.sub(r"[^a-zA-Z0-9_-]+", "-", sys.argv[1]).strip("-")[:32])' "$PLAN_ID")
BATCH_NAME="${BATCH_NAME:-${SAFE_PLAN_ID}_${TS}}"
SESSION="${SESSION:-redo-${SAFE_PLAN_ID:0:18}-${TS:9:6}}"
OUT_DIR="${OUT_DIR:-${HOME}/dev/ops/redo_runs_colab/${BATCH_NAME}}"
STAGING_DIR="${OUT_DIR}/staging"
STATE_FILE="${OUT_DIR}/state.json"

REMOTE_WORK="/srv/redo"
REMOTE_RUN_ROOT="${REMOTE_WORK}/run"
REMOTE_REPO_TAR="/content/redo_repo_${SHORT_SHA}.tar.gz"
REMOTE_BANK_TAR="/content/redo_bank_${BATCH_NAME}.tar.gz"
REMOTE_PLAN="/content/redo_plan_${BATCH_NAME}.json"
REMOTE_VLLM_CFG="/content/redo_vllm_config_${BATCH_NAME}.json"
REMOTE_LAUNCH_META="/content/redo_launch_meta_${BATCH_NAME}.json"
REMOTE_BOOTSTRAP="/content/redo_bootstrap_${BATCH_NAME}.sh"
EXTRA_WHEEL_SHA=""
REMOTE_WHEEL=""
if [ -n "$EXTRA_WHEEL" ]; then
  [ -f "$EXTRA_WHEEL" ] || { echo "ERROR: --extra-wheel not found: $EXTRA_WHEEL" >&2; exit 2; }
  EXTRA_WHEEL_SHA=$(sha256sum "$EXTRA_WHEEL" | cut -d' ' -f1)
  REMOTE_WHEEL="/content/$(basename "$EXTRA_WHEEL")"
fi
REMOTE_RESULTS_TAR="/content/redo_results_${BATCH_NAME}.tar.gz"

# Build colab CLI prefix (global flags MUST precede subcommand).
COLAB_CMD=("$COLAB_BIN")
[ -n "$COLAB_AUTH" ] && COLAB_CMD+=("--auth=${COLAB_AUTH}")
[ -n "$COLAB_CONFIG" ] && COLAB_CMD+=(--config "$COLAB_CONFIG")

NEW_CMD=("${COLAB_CMD[@]}" new -s "$SESSION" --gpu "$GPU")
[ "$HIGH_MEM" = "1" ] && NEW_CMD+=(--high-mem)

fmt_cmd() {
  local out="" a
  for a in "$@"; do
    out+="$(printf '%q ' "$a")"
  done
  printf '%s\n' "${out% }"
}

REPO_TAR_LOCAL="${STAGING_DIR}/repo_${SHORT_SHA}.tar.gz"
BANK_TAR_LOCAL="${STAGING_DIR}/bank_${BATCH_NAME}.tar.gz"
LAUNCH_META_LOCAL="${STAGING_DIR}/launch_meta.json"
BOOTSTRAP_LOCAL="${STAGING_DIR}/bootstrap.sh"

if [ "$DRY_RUN" = "1" ]; then
  echo "[dry-run] batch=${BATCH_NAME} session=${SESSION} gpu=${GPU} high_mem=${HIGH_MEM} commit=${COMMIT_SHA}"
  echo "[dry-run] plan=${PLAN_ABS} (id=${PLAN_ID}, sha256=${PLAN_SHA256}, tasks=${N_TASKS}, reps=${REPS})"
  echo "[dry-run] bank=${BANK_ABS}"
  echo "[dry-run] vllm_config=${VLLM_CFG_ABS}"
  echo "[dry-run] local_out_dir=${OUT_DIR} state_file=${STATE_FILE}"
  echo "[dry-run] git -C $(printf '%q' "$REPO_ROOT") archive --format=tar.gz --prefix=repo/ -o $(printf '%q' "$REPO_TAR_LOCAL") $(printf '%q' "$COMMIT_SHA") -- ops/redo"
  echo "[dry-run] tar -czf $(printf '%q' "$BANK_TAR_LOCAL") -C $(printf '%q' "$BANK_ABS") ."
  echo "[dry-run] $(fmt_cmd "${NEW_CMD[@]}")"
  echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" upload -s "$SESSION" "$REPO_TAR_LOCAL" "$REMOTE_REPO_TAR")"
  echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" upload -s "$SESSION" "$BANK_TAR_LOCAL" "$REMOTE_BANK_TAR")"
  echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" upload -s "$SESSION" "$PLAN_ABS" "$REMOTE_PLAN")"
  echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" upload -s "$SESSION" "$VLLM_CFG_ABS" "$REMOTE_VLLM_CFG")"
  echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" upload -s "$SESSION" "$LAUNCH_META_LOCAL" "$REMOTE_LAUNCH_META")"
  echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" upload -s "$SESSION" "$BOOTSTRAP_LOCAL" "$REMOTE_BOOTSTRAP")"
  if [ "$TRANSPORT" = "ssh" ]; then
    echo "[dry-run] $(fmt_cmd "${COLAB_CMD[@]}" ssh -s "$SESSION" -- bash "$REMOTE_BOOTSTRAP")"
  else
    echo "[dry-run] printf '!bash %s\\n' $(printf '%q' "$REMOTE_BOOTSTRAP") | $(fmt_cmd "${COLAB_CMD[@]}" exec -s "$SESSION")"
  fi
  echo "[dry-run] write state file -> ${STATE_FILE}"
  exit 0
fi

mkdir -p "$STAGING_DIR"

echo "1/6 Archiving frozen commit ${COMMIT_SHA} -> ${REPO_TAR_LOCAL}"
git -C "$REPO_ROOT" archive --format=tar.gz --prefix=repo/ -o "$REPO_TAR_LOCAL" "$COMMIT_SHA" -- ops/redo
REPO_TAR_SHA=$(sha256sum "$REPO_TAR_LOCAL" | cut -d' ' -f1)

echo "2/6 Archiving task bank ${BANK_ABS} -> ${BANK_TAR_LOCAL}"
tar -czf "$BANK_TAR_LOCAL" -C "$BANK_ABS" .
BANK_TAR_SHA=$(sha256sum "$BANK_TAR_LOCAL" | cut -d' ' -f1)

# Write launch metadata JSON (uploaded to VM & stored inside run root).
EXTRA_WHEEL_SHA="$EXTRA_WHEEL_SHA" EXTRA_WHEEL_NAME="$(basename "${EXTRA_WHEEL:-}")" python3 - "$LAUNCH_META_LOCAL" "$BATCH_NAME" "$SESSION" "$GPU" "$HIGH_MEM" "$COMMIT_SHA" \
  "$PLAN_ID" "$PLAN_SHA256" "$REPO_TAR_SHA" "$BANK_TAR_SHA" "$VLLM_CFG_ABS" "$ALLOW_UNCOMMITTED" <<'PY'
import json, pathlib, sys, time
(out_p, batch, session, gpu, hm, commit, plan_id, plan_sha,
 repo_sha, bank_sha, cfg_p, allow_unc) = sys.argv[1:]
doc = {
    "schema": "vacant.redo.colab.launch/1",
    "launched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "batch_name": batch,
    "session": session,
    "gpu_requested": gpu,
    "high_mem_requested": hm == "1",
    "git_commit": commit,
    "plan_id": plan_id,
    "plan_sha256": plan_sha,
    "repo_tar_sha256": repo_sha,
    "bank_tar_sha256": bank_sha,
    "allow_uncommitted_plan": allow_unc == "1",
    "vllm_config": json.loads(pathlib.Path(cfg_p).read_text(encoding="utf-8")),
}
import os as _os
if _os.environ.get("EXTRA_WHEEL_SHA"):
    doc["extra_wheel"] = {"name": _os.environ.get("EXTRA_WHEEL_NAME"), "sha256": _os.environ["EXTRA_WHEEL_SHA"],
                          "venv": "/opt/redo/rc_venv"}
pathlib.Path(out_p).write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

# Generate VM bootstrap script (unpacks repo, launches vm_run_batch.sh under setsid nohup).
cat > "$BOOTSTRAP_LOCAL" <<EOF
#!/usr/bin/env bash
set -euo pipefail
mkdir -p ${REMOTE_WORK}/repo ${REMOTE_RUN_ROOT}
tar -xzf ${REMOTE_REPO_TAR} -C ${REMOTE_WORK}/repo --strip-components=1
chmod +x ${REMOTE_WORK}/repo/ops/redo/colab/*.sh ${REMOTE_WORK}/repo/ops/redo/colab/*.py
if [ -n "${REMOTE_WHEEL}" ]; then
  echo "${EXTRA_WHEEL_SHA}  ${REMOTE_WHEEL}" | sha256sum -c -
  # Colab 的 python3 沒有 ensurepip（python3 -m venv 會失敗）：用 uv 建 venv、裝 wheel
  python3 -m pip install -q uv
  python3 -m uv venv -q -p python3 /opt/redo/rc_venv
  python3 -m uv pip install -q -p /opt/redo/rc_venv/bin/python "${REMOTE_WHEEL}"
  /opt/redo/rc_venv/bin/vacant do --help >/dev/null
  echo "EXTRA_WHEEL_OK /opt/redo/rc_venv/bin/vacant"
fi
setsid nohup bash ${REMOTE_WORK}/repo/ops/redo/colab/vm_run_batch.sh \\
  --repo-dir ${REMOTE_WORK}/repo \\
  --bank-tar ${REMOTE_BANK_TAR} \\
  --plan ${REMOTE_PLAN} \\
  --vllm-config ${REMOTE_VLLM_CFG} \\
  --launch-meta ${REMOTE_LAUNCH_META} \\
  --work-dir ${REMOTE_WORK} \\
  --root ${REMOTE_RUN_ROOT} \\
  --tar-out ${REMOTE_RESULTS_TAR} \\
  </dev/null >> ${REMOTE_WORK}/bootstrap.log 2>&1 &
PID=\$!
echo "\$PID" > ${REMOTE_WORK}/batch.pid
echo "BATCH_STARTED pid=\$PID log=${REMOTE_WORK}/bootstrap.log"
EOF
chmod +x "$BOOTSTRAP_LOCAL"

echo "3/6 Provisioning Colab VM: $(fmt_cmd "${NEW_CMD[@]}")"
"${NEW_CMD[@]}"

echo "4/6 Uploading repo snapshot, bank tarball, plan, config, metadata, and bootstrap script"
"${COLAB_CMD[@]}" upload -s "$SESSION" "$REPO_TAR_LOCAL" "$REMOTE_REPO_TAR"
"${COLAB_CMD[@]}" upload -s "$SESSION" "$BANK_TAR_LOCAL" "$REMOTE_BANK_TAR"
"${COLAB_CMD[@]}" upload -s "$SESSION" "$PLAN_ABS" "$REMOTE_PLAN"
"${COLAB_CMD[@]}" upload -s "$SESSION" "$VLLM_CFG_ABS" "$REMOTE_VLLM_CFG"
"${COLAB_CMD[@]}" upload -s "$SESSION" "$LAUNCH_META_LOCAL" "$REMOTE_LAUNCH_META"
"${COLAB_CMD[@]}" upload -s "$SESSION" "$BOOTSTRAP_LOCAL" "$REMOTE_BOOTSTRAP"
if [ -n "$EXTRA_WHEEL" ]; then
  "${COLAB_CMD[@]}" upload -s "$SESSION" "$EXTRA_WHEEL" "$REMOTE_WHEEL"
fi

echo "5/6 Starting VM setup + redo.py batch under setsid/nohup (transport=${TRANSPORT})"
if [ "$TRANSPORT" = "ssh" ]; then
  "${COLAB_CMD[@]}" ssh -s "$SESSION" -- bash "$REMOTE_BOOTSTRAP" </dev/null
else
  printf '!bash %s\n' "$REMOTE_BOOTSTRAP" | "${COLAB_CMD[@]}" exec -s "$SESSION"
fi

echo "6/6 Writing local state file -> ${STATE_FILE}"
python3 - "$STATE_FILE" "$BATCH_NAME" "$SESSION" "$GPU" "$HIGH_MEM" "$COMMIT_SHA" \
  "$PLAN_ID" "$PLAN_SHA256" "$PLAN_ABS" "$BANK_ABS" "$VLLM_CFG_ABS" "$OUT_DIR" \
  "$REMOTE_WORK" "$REMOTE_RUN_ROOT" "$REMOTE_RESULTS_TAR" "$TRANSPORT" "$COLAB_BIN" "$COLAB_CONFIG" "$COLAB_AUTH" <<'PY'
import json, os, pathlib, sys, time
(state_p, batch, session, gpu, hm, commit, plan_id, plan_sha, plan_abs, bank_abs,
 cfg_abs, out_dir, rwork, rroot, rtar, transport, cbin, ccfg, cauth) = sys.argv[1:]
doc = {
    "schema": "vacant.redo.colab.state/1",
    "launched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "batch_name": batch,
    "session": session,
    "gpu": gpu,
    "high_mem": hm == "1",
    "git_commit": commit,
    "plan_id": plan_id,
    "plan_sha256": plan_sha,
    "plan_local": plan_abs,
    "bank_local": bank_abs,
    "vllm_config_local": cfg_abs,
    "local_out_dir": out_dir,
    "remote_work_dir": rwork,
    "remote_run_root": rroot,
    "remote_results_tar": rtar,
    "transport": transport,
    "colab_bin": cbin,
    "colab_config": ccfg or None,
    "colab_auth": cauth or None,
    "fetched_utc": None,
    "stopped_utc": None,
}
p = pathlib.Path(state_p)
tmp = p.with_name(p.name + f".tmp.{os.getpid()}")
tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, p)
PY

echo ""
echo "LAUNCH_OK"
echo "  State file : ${STATE_FILE}"
echo "  Session    : ${SESSION} (GPU=${GPU})"
echo "  Poll       : bash ops/redo/colab/poll_batch.sh ${STATE_FILE}"
echo "  Fetch+Stop : bash ops/redo/colab/fetch_batch.sh ${STATE_FILE}"
echo "  Manual stop: $(fmt_cmd "${COLAB_CMD[@]}" stop -s "$SESSION")"
