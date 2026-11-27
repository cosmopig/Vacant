#!/usr/bin/env bash
# Hardened Colab GPU VM rent, queue, monitor, registry, and watchdog orchestrator.
#
# Replaces ad-hoc colab_retry_*.sh + colab_monitor_only.sh scripts with:
#   1. Post-launch session registry ($HOME/dev/ops/ctl/colab_registry.jsonl):
#      queries `colab sessions` after EVERY `colab new` attempt (success or failure),
#      records session + endpoint + gpu + batch + state, and ALWAYS stops & verifies
#      assignment drop if launch failed after an assignment was created.
#   2. Account-level usage watchdog (separate background loop, default every 5 min):
#      parses `colab usage` and `colab sessions`; writes ALERT to
#      $HOME/dev/ops/ctl/colab_alerts.log if usage rate > 0 or active assignments > 0
#      without a matching live registered session (NEVER auto-stops unknown sessions).
#   3. Ordered queue mode (colab_queue.json):
#      reuses the same VM via `launch_batch.sh --reuse-session <name>` for subsequent
#      pending batches; stops VM and verifies usage 0 only when the queue is drained.
#   4. Spend cap (default 180 CU from start balance) + balance floor (default 20 CU),
#      checked before every launch and every poll; on breach: partial fetch, stop, alert.
#   5. Periodic partial fetch every 30 min (`fetch_batch.sh --force --no-stop`).
#   6. Rent retries in GPU order A100 -> G4 -> L4 every 20 min up to --deadline,
#      supporting up to 2 concurrent VMs (gracefully falling back to queue reuse on
#      too-many-assignments errors).
#   7. Dry-run mode (`--dry-run`) that never invokes `colab` and mutates no state.
#
# Never runs `colab pay`. Uses $HOME (no hardcoded absolute home paths).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || (cd "${SCRIPT_DIR}/../../.." && pwd))"
LAUNCH_SCRIPT="${SCRIPT_DIR}/launch_batch.sh"
POLL_SCRIPT="${SCRIPT_DIR}/poll_batch.sh"
FETCH_SCRIPT="${SCRIPT_DIR}/fetch_batch.sh"

usage() {
  cat <<'EOF'
Usage: colab_rent_and_run.sh [options]

Queue & Deadline:
  --queue <path>                  Queue JSON file (default: <repo>/ops/redo/colab/colab_queue.json)
  --deadline <ISO8601|epoch>      Stop rent attempts after UTC deadline (default: +24h from start)
  --hard-deadline <ISO8601|epoch> Force partial fetch + stop active VMs after UTC time (default: deadline + 6h)

Budget & Concurrency:
  --max-spend <CU>                Max total spend from start balance across queue (default: 180)
  --balance-floor <CU>            Minimum balance floor in CU (default: 20)
  --max-concurrent-vms <N>        Maximum concurrent Colab VMs (default: 2)
  --gpus <CSV>                    Fallback GPU preference order (default: A100,G4,L4)

Intervals (seconds):
  --rent-interval <sec>           Seconds between rent attempts (default: 1200 = 20 min)
  --poll-interval <sec>           Seconds between batch polls (default: 600 = 10 min)
  --partial-fetch-interval <sec>  Seconds between partial fetches (default: 1800 = 30 min)
  --watchdog-interval <sec>       Seconds between account usage watchdog checks (default: 300 = 5 min)
  --tick-interval <sec>           Main loop sleep cap in seconds (default: 30)
  --stop-retry-delay <sec>        Seconds before retrying stop verification (default: 3)

Paths & Colab CLI:
  --registry <path>               JSONL session registry (default: $HOME/dev/ops/ctl/colab_registry.jsonl)
  --alerts-log <path>             Alerts log path (default: $HOME/dev/ops/ctl/colab_alerts.log)
  --log <path>                    Orchestrator log path (default: $HOME/dev/ops/ctl/colab_rent_and_run.log)
  --out-root <dir>                Local batch output root (default: $HOME/dev/ops/redo_runs_colab)
  --colab-bin <path>              Colab CLI binary (default: colab)
  --colab-config <path>           Optional `colab --config <path>`
  --colab-auth <adc|oauth2>       Optional `colab --auth=<mode>`

Modes:
  --dry-run                       Validate queue & print planned commands; invoke NO colab commands
  --watchdog-once                 Run a single account-level usage watchdog check and exit
  --watchdog-only                 Run only the account-level usage watchdog loop
  --no-watchdog                   Do not start background watchdog loop
  -h, --help                      Show this help

Exit codes:
  0   Queue completed (or dry-run / watchdog-once succeeded)
  2   Invalid CLI arguments or queue configuration
  10  Spend cap or balance floor breached (partial fetch + stop + alert executed)
  11  Deadline or hard deadline reached before queue finished
  12  Startup error (e.g. unable to read initial balance from `colab usage`)
EOF
}

# Defaults (all paths use $HOME; no hardcoded /home/<user> paths).
QUEUE_FILE="${SCRIPT_DIR}/colab_queue.json"
DEADLINE_ARG=""
HARD_DEADLINE_ARG=""
MAX_SPEND=""
BALANCE_FLOOR=""
MAX_CONCURRENT_VMS=""
DEFAULT_GPUS=""
LAUNCH_SEQ=0

RENT_INTERVAL=1200
POLL_INTERVAL=600
PARTIAL_FETCH_INTERVAL=1800
WATCHDOG_INTERVAL=300
TICK_INTERVAL=30
STOP_RETRY_DELAY=3

REGISTRY_FILE="${HOME}/dev/ops/ctl/colab_registry.jsonl"
ALERTS_LOG="${HOME}/dev/ops/ctl/colab_alerts.log"
LOG_FILE="${HOME}/dev/ops/ctl/colab_rent_and_run.log"
OUT_ROOT="${HOME}/dev/ops/redo_runs_colab"
COLAB_BIN="${COLAB_BIN:-colab}"
COLAB_CONFIG=""
COLAB_AUTH=""

DRY_RUN=0
WATCHDOG_ONCE=0
WATCHDOG_ONLY=0
NO_WATCHDOG=0

while [ $# -gt 0 ]; do
  case "$1" in
    --queue) QUEUE_FILE="$2"; shift 2 ;;
    --deadline) DEADLINE_ARG="$2"; shift 2 ;;
    --hard-deadline) HARD_DEADLINE_ARG="$2"; shift 2 ;;
    --max-spend) MAX_SPEND="$2"; shift 2 ;;
    --balance-floor) BALANCE_FLOOR="$2"; shift 2 ;;
    --max-concurrent-vms) MAX_CONCURRENT_VMS="$2"; shift 2 ;;
    --gpus) DEFAULT_GPUS="$2"; shift 2 ;;
    --rent-interval) RENT_INTERVAL="$2"; shift 2 ;;
    --poll-interval) POLL_INTERVAL="$2"; shift 2 ;;
    --partial-fetch-interval) PARTIAL_FETCH_INTERVAL="$2"; shift 2 ;;
    --watchdog-interval) WATCHDOG_INTERVAL="$2"; shift 2 ;;
    --tick-interval) TICK_INTERVAL="$2"; shift 2 ;;
    --stop-retry-delay) STOP_RETRY_DELAY="$2"; shift 2 ;;
    --registry) REGISTRY_FILE="$2"; shift 2 ;;
    --alerts-log) ALERTS_LOG="$2"; shift 2 ;;
    --log) LOG_FILE="$2"; shift 2 ;;
    --out-root) OUT_ROOT="$2"; shift 2 ;;
    --colab-bin) COLAB_BIN="$2"; shift 2 ;;
    --colab-config) COLAB_CONFIG="$2"; shift 2 ;;
    --colab-auth) COLAB_AUTH="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --watchdog-once) WATCHDOG_ONCE=1; shift ;;
    --watchdog-only) WATCHDOG_ONLY=1; shift ;;
    --no-watchdog) NO_WATCHDOG=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "error: unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

COLAB_CMD=("$COLAB_BIN")
if [ -n "$COLAB_AUTH" ]; then
  COLAB_CMD+=("--auth=${COLAB_AUTH}")
fi
if [ -n "$COLAB_CONFIG" ]; then
  COLAB_CMD+=(--config "$COLAB_CONFIG")
fi

utc_now() {
  date -u +%Y-%m-%dT%H:%M:%SZ
}

epoch_now() {
  date -u +%s
}

log_msg() {
  local ts line
  ts="$(utc_now)"
  line="${ts} [colab_rent_and_run] $*"
  printf '%s\n' "$line"
  if [ "$DRY_RUN" = "0" ]; then
    mkdir -p "$(dirname "$LOG_FILE")"
    printf '%s\n' "$line" >> "$LOG_FILE"
  fi
}

write_alert() {
  local ts line
  ts="$(utc_now)"
  line="${ts} ALERT $*"
  printf '%s\n' "$line" >&2
  if [ "$DRY_RUN" = "0" ]; then
    mkdir -p "$(dirname "$ALERTS_LOG")"
    printf '%s\n' "$line" >> "$ALERTS_LOG"
    mkdir -p "$(dirname "$LOG_FILE")"
    printf '%s\n' "$line" >> "$LOG_FILE"
  fi
}

parse_time_to_epoch() {
  local raw="$1"
  python3 - "$raw" <<'PY'
import datetime, sys
raw = sys.argv[1].strip()
if raw.isdigit():
    print(int(raw))
    sys.exit(0)
if raw.endswith("Z"):
    raw = raw[:-1] + "+00:00"
try:
    dt = datetime.datetime.fromisoformat(raw)
except ValueError as exc:
    sys.exit(f"error: invalid timestamp {sys.argv[1]!r}: {exc}")
if dt.tzinfo is None:
    dt = dt.replace(tzinfo=datetime.timezone.utc)
print(int(dt.timestamp()))
PY
}

# Query `colab usage` and emit JSON:
# {"ok": true/false, "balance": float|null, "usage_rate": float|null, "active_assignments": int|null, "raw": str}
query_usage_json() {
  local rc=0 out=""
  if out="$(timeout 60 "${COLAB_CMD[@]}" usage </dev/null 2>&1)"; then
    rc=0
  else
    rc=$?
  fi
  python3 - "$rc" "$out" <<'PY'
import json, re, sys
rc = int(sys.argv[1])
out = sys.argv[2]
bal_m = re.search(r"Current balance:\s*([0-9]+(?:\.[0-9]+)?)", out)
rate_m = re.search(r"Usage rate:\s*([0-9]+(?:\.[0-9]+)?)", out)
asgn_m = re.search(r"Active assignments:\s*([0-9]+)", out)
doc = {
    "ok": rc == 0 and (bal_m is not None or rate_m is not None or asgn_m is not None),
    "rc": rc,
    "balance": float(bal_m.group(1)) if bal_m else None,
    "usage_rate": float(rate_m.group(1)) if rate_m else None,
    "active_assignments": int(asgn_m.group(1)) if asgn_m else None,
    "raw": " ".join(out.split())[:400],
}
print(json.dumps(doc))
PY
}

# Query `colab sessions` and emit JSON:
# {"ok": true/false, "sessions": [{"session":..., "endpoint":..., "gpu":..., "raw_line":...}], "raw": str}
query_sessions_json() {
  local rc=0 out=""
  if out="$(timeout 60 "${COLAB_CMD[@]}" sessions </dev/null 2>&1)"; then
    rc=0
  else
    rc=$?
  fi
  python3 - "$rc" "$out" <<'PY'
import json, re, sys
rc = int(sys.argv[1])
out = sys.argv[2]
sessions = []
for raw_line in out.splitlines():
    line = raw_line.strip()
    m = re.match(r"^\[([^\]]+)\]\s+(\S+)(.*)$", line)
    if not m:
        continue
    name, endpoint, rest = m.group(1).strip(), m.group(2).strip(), m.group(3)
    # `[colab] Error: No active sessions…` / `[colab] Using unique session…` are CLI messages, not sessions:
    # a real session line carries a `Hardware:` field.
    if name == "colab" or "Hardware:" not in rest:
        continue
    hw_m = re.search(r"Hardware:\s*([^|\s]+)", rest)
    gpu = hw_m.group(1).strip() if hw_m else ""
    sessions.append({
        "session": name,
        "endpoint": endpoint,
        "gpu": gpu,
        "raw_line": line,
    })
doc = {
    "ok": rc == 0,
    "rc": rc,
    "sessions": sessions,
    "raw": " ".join(out.split())[:400],
}
print(json.dumps(doc))
PY
}

# Append a single JSONL record to $REGISTRY_FILE.
registry_append() {
  local event="$1" status="$2" session="$3" endpoint="$4" gpu="$5" batch="$6" state_path="$7" raw_line="${8:-}"
  if [ "$DRY_RUN" = "1" ]; then
    return 0
  fi
  mkdir -p "$(dirname "$REGISTRY_FILE")"
  python3 - "$REGISTRY_FILE" "$event" "$status" "$session" "$endpoint" "$gpu" "$batch" "$state_path" "$raw_line" <<'PY'
import fcntl, json, os, sys, time
reg_path, event, status, session, endpoint, gpu, batch, state_path, raw_line = sys.argv[1:]
rec = {
    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "event": event,
    "status": status,
    "session": session,
    "endpoint": endpoint,
    "gpu": gpu,
    "batch": batch,
    "state": state_path,
}
if raw_line:
    rec["raw_line"] = raw_line
line = json.dumps(rec, ensure_ascii=False, sort_keys=False) + "\n"
os.makedirs(os.path.dirname(reg_path) or ".", exist_ok=True)
with open(reg_path, "a", encoding="utf-8") as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    f.write(line)
    f.flush()
    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
PY
}

# Account-level usage watchdog check (Requirement 2).
# NEVER auto-stops unknown sessions — writes ALERT to $ALERTS_LOG only.
watchdog_check_once() {
  local usage_json sess_json result alert_msg
  usage_json="$(query_usage_json)"
  sess_json="$(query_sessions_json)"
  result="$(python3 - "$REGISTRY_FILE" "$usage_json" "$sess_json" <<'PY'
import json, os, sys

reg_path, usage_raw, sess_raw = sys.argv[1:]
usage = json.loads(usage_raw)
sess = json.loads(sess_raw)

if not usage.get("ok") and not sess.get("ok"):
    print("QUERY_ERROR usage_rc=%s sess_rc=%s" % (usage.get("rc"), sess.get("rc")))
    sys.exit(0)

# Build latest active session set from registry JSONL.
reg_status = {}
if os.path.isfile(reg_path):
    with open(reg_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            s = rec.get("session")
            if not s:
                continue
            reg_status[s] = rec.get("status", "active")

reg_active = {s for s, st in reg_status.items() if st == "active"}
live_sessions = {x["session"] for x in sess.get("sessions", [])} if sess.get("ok") else set()
live_reg = reg_active & live_sessions

usage_rate = usage.get("usage_rate")
active_asgn = usage.get("active_assignments")
balance = usage.get("balance")

rate_val = float(usage_rate) if usage_rate is not None else 0.0
asgn_val = int(active_asgn) if active_asgn is not None else 0

reasons = []
if (rate_val > 0.0 or asgn_val > 0) and len(live_reg) == 0:
    reasons.append("usage_or_assignments_without_live_registered_session")
elif asgn_val > len(live_reg):
    reasons.append("active_assignments_exceed_live_registered_sessions")

unregistered_live = sorted(live_sessions - reg_active)
if unregistered_live:
    reasons.append("unregistered_live_session")

if reasons:
    msg = (
        f"reason={','.join(reasons)} "
        f"usage_rate={rate_val} active_assignments={asgn_val} "
        f"balance={balance} "
        f"live_sessions={sorted(live_sessions)} "
        f"live_registered={sorted(live_reg)} "
        f"unregistered_live={unregistered_live} "
        f"(owner_safe:no_auto_stop)"
    )
    print("ALERT " + msg)
else:
    print(
        f"OK usage_rate={rate_val} active_assignments={asgn_val} "
        f"balance={balance} live_registered={sorted(live_reg)}"
    )
PY
)"
  case "$result" in
    ALERT\ *)
      alert_msg="${result#ALERT }"
      write_alert "watchdog ${alert_msg}"
      ;;
    QUERY_ERROR\ *)
      log_msg "watchdog: query failed (${result}); skipping check"
      ;;
    OK\ *)
      log_msg "watchdog: ${result}"
      ;;
  esac
}

watchdog_loop() {
  log_msg "watchdog started (interval=${WATCHDOG_INTERVAL}s, registry=${REGISTRY_FILE}, alerts=${ALERTS_LOG})"
  while true; do
    watchdog_check_once || true
    sleep "$WATCHDOG_INTERVAL"
  done
}

# Handle standalone watchdog modes immediately (no queue required).
if [ "$WATCHDOG_ONCE" = "1" ]; then
  if [ "$DRY_RUN" = "1" ]; then
    echo "[dry-run] watchdog_check_once: would run \`${COLAB_CMD[*]} usage\` and \`${COLAB_CMD[*]} sessions\` against registry ${REGISTRY_FILE} -> alerts ${ALERTS_LOG}"
    exit 0
  fi
  watchdog_check_once
  exit 0
fi

if [ "$WATCHDOG_ONLY" = "1" ]; then
  if [ "$DRY_RUN" = "1" ]; then
    echo "[dry-run] watchdog_loop (interval=${WATCHDOG_INTERVAL}s): would poll \`${COLAB_CMD[*]} usage\` and \`${COLAB_CMD[*]} sessions\` against ${REGISTRY_FILE}"
    exit 0
  fi
  watchdog_loop
  exit 0
fi

if [ ! -f "$QUEUE_FILE" ]; then
  echo "error: queue file not found: $QUEUE_FILE" >&2
  exit 2
fi

# Validate queue file & load defaults (without mutating queue file).
QUEUE_DEFAULTS="$(python3 - "$QUEUE_FILE" "$REPO_ROOT" "${DEFAULT_GPUS:-A100,G4,L4}" <<'PY'
import json, os, pathlib, shlex, sys

qpath, repo_root, cli_gpus = sys.argv[1:]
doc = json.loads(pathlib.Path(qpath).read_text(encoding="utf-8"))
if doc.get("schema") != "vacant.redo.colab.queue/1":
    sys.exit(f"error: unexpected queue schema {doc.get('schema')!r} (expected 'vacant.redo.colab.queue/1')")
batches = doc.get("batches")
if not isinstance(batches, list):
    sys.exit("error: queue JSON 'batches' must be a list")

defaults = doc.get("defaults") or {}
def_gpus = defaults.get("preferred_gpus") or [g.strip() for g in cli_gpus.split(",") if g.strip()]
for g in def_gpus:
    if g not in ("T4", "L4", "G4", "A100", "H100"):
        sys.exit(f"error: invalid GPU in defaults.preferred_gpus: {g!r}")

seen_ids = set()
for idx, b in enumerate(batches):
    if not isinstance(b, dict):
        sys.exit(f"error: batch[{idx}] must be an object")
    for req in ("plan", "bank", "vllm_config"):
        if not b.get(req):
            sys.exit(f"error: batch[{idx}] missing required key {req!r}")
    bid = str(b.get("id") or f"batch_{idx}")
    if bid in seen_ids:
        sys.exit(f"error: duplicate batch id {bid!r}")
    seen_ids.add(bid)
    bgpus = b.get("preferred_gpus") or def_gpus
    for g in bgpus:
        if g not in ("T4", "L4", "G4", "A100", "H100"):
            sys.exit(f"error: invalid GPU {g!r} in batch {bid!r}")

print(f"Q_DEF_MAX_SPEND={shlex.quote(str(defaults.get('max_spend_cu', 180)))}")
print(f"Q_DEF_FLOOR={shlex.quote(str(defaults.get('balance_floor_cu', 20)))}")
print(f"Q_DEF_MAX_VMS={shlex.quote(str(defaults.get('max_concurrent_vms', 2)))}")
print(f"Q_DEF_GPUS={shlex.quote(','.join(def_gpus))}")
PY
)"
Q_DEF_MAX_SPEND=180
Q_DEF_FLOOR=20
Q_DEF_MAX_VMS=2
Q_DEF_GPUS="A100,G4,L4"
eval "$QUEUE_DEFAULTS"

MAX_SPEND="${MAX_SPEND:-$Q_DEF_MAX_SPEND}"
BALANCE_FLOOR="${BALANCE_FLOOR:-$Q_DEF_FLOOR}"
MAX_CONCURRENT_VMS="${MAX_CONCURRENT_VMS:-$Q_DEF_MAX_VMS}"
DEFAULT_GPUS="${DEFAULT_GPUS:-$Q_DEF_GPUS}"

NOW_START="$(epoch_now)"
if [ -n "$DEADLINE_ARG" ]; then
  DEADLINE_EPOCH="$(parse_time_to_epoch "$DEADLINE_ARG")"
else
  DEADLINE_EPOCH=$((NOW_START + 24 * 3600))
fi
if [ -n "$HARD_DEADLINE_ARG" ]; then
  HARD_DEADLINE_EPOCH="$(parse_time_to_epoch "$HARD_DEADLINE_ARG")"
else
  HARD_DEADLINE_EPOCH=$((DEADLINE_EPOCH + 6 * 3600))
fi

# Dry-run mode: validate everything, print exact commands, invoke NO colab commands.
if [ "$DRY_RUN" = "1" ]; then
  echo "[dry-run] colab_rent_and_run.sh"
  echo "[dry-run] queue=${QUEUE_FILE} repo_root=${REPO_ROOT}"
  echo "[dry-run] registry=${REGISTRY_FILE} alerts_log=${ALERTS_LOG} out_root=${OUT_ROOT}"
  echo "[dry-run] max_spend=${MAX_SPEND} balance_floor=${BALANCE_FLOOR} max_concurrent_vms=${MAX_CONCURRENT_VMS}"
  echo "[dry-run] intervals: rent=${RENT_INTERVAL}s poll=${POLL_INTERVAL}s partial_fetch=${PARTIAL_FETCH_INTERVAL}s watchdog=${WATCHDOG_INTERVAL}s"
  echo "[dry-run] deadline_epoch=${DEADLINE_EPOCH} hard_deadline_epoch=${HARD_DEADLINE_EPOCH}"
  echo "[dry-run] watchdog: every ${WATCHDOG_INTERVAL}s run \`${COLAB_CMD[*]} usage\` + \`${COLAB_CMD[*]} sessions\` -> alert to ${ALERTS_LOG} if usage>0 or assignments>0 with no live registered session (no auto-stop)"

  python3 - "$QUEUE_FILE" "$REPO_ROOT" "$DEFAULT_GPUS" "$OUT_ROOT" "$LAUNCH_SCRIPT" "$COLAB_BIN" "$COLAB_CONFIG" "$COLAB_AUTH" <<'PY'
import json, os, pathlib, shlex, subprocess, sys

qpath, repo_root, def_gpus_csv, out_root, launch_sh, cbin, ccfg, cauth = sys.argv[1:]
doc = json.loads(pathlib.Path(qpath).read_text(encoding="utf-8"))
defaults = doc.get("defaults") or {}
def_gpus = [g.strip() for g in def_gpus_csv.split(",") if g.strip()]

def resolve_path(p: str) -> str:
    expanded = os.path.expanduser(os.path.expandvars(p))
    if os.path.isabs(expanded):
        return expanded
    return os.path.join(repo_root, expanded)

pending = []
for idx, b in enumerate(doc["batches"]):
    st = b.get("status", "pending")
    if st != "pending":
        print(f"[dry-run] skip batch[{idx}] id={b.get('id')} status={st}")
        continue
    pending.append((idx, b))

print(f"[dry-run] pending_batches={len(pending)}")
first_session = None
for order_i, (idx, b) in enumerate(pending):
    bid = str(b.get("id") or f"batch_{idx}")
    plan = resolve_path(b["plan"])
    bank = resolve_path(b["bank"])
    vcfg = resolve_path(b["vllm_config"])
    gpus = b.get("preferred_gpus") or defaults.get("preferred_gpus") or def_gpus
    gpu0 = gpus[0]
    high_mem = bool(b.get("high_mem", defaults.get("high_mem", False)))
    commit = str(b.get("commit") or defaults.get("commit") or "HEAD")
    transport = str(b.get("transport") or defaults.get("transport") or "ssh")
    allow_unc = bool(b.get("allow_uncommitted_plan", False))
    sess = f"redo-{bid[:18]}-DRYRUN"
    bname = f"{bid}_DRYRUN"
    odir = os.path.join(out_root, bname)
    if first_session is None:
        first_session = sess

    print(f"[dry-run] queue[{order_i}] id={bid} gpus={','.join(gpus)} plan={plan} bank={bank} vllm_config={vcfg}")
    cmd = [
        "bash", launch_sh, plan, bank,
        "--gpu", gpu0,
        "--vllm-config", vcfg,
        "--commit", commit,
        "--transport", transport,
        "--batch-name", bname,
        "--out-dir", odir,
        "--colab-bin", cbin,
        "--dry-run",
    ]
    if order_i == 0:
        cmd.extend(["--session", sess])
    else:
        cmd.extend(["--reuse-session", first_session])
    if high_mem:
        cmd.append("--high-mem")
    if ccfg:
        cmd.extend(["--colab-config", ccfg])
    if cauth:
        cmd.extend(["--colab-auth", cauth])
    if allow_unc:
        cmd.append("--allow-uncommitted-plan")
    for et in b.get("extra_tars") or []:
        parts = et.split(":", 1)
        if len(parts) == 2:
            cmd.extend(["--extra-tar", f"{resolve_path(parts[0])}:{resolve_path(parts[1])}"])
    if b.get("extra_wheel"):
        cmd.extend(["--extra-wheel", resolve_path(b["extra_wheel"])])

    print(f"[dry-run] launch_cmd: {' '.join(shlex.quote(x) for x in cmd)}")
    if os.path.isfile(plan) and os.path.isdir(bank) and os.path.isfile(vcfg):
        r = subprocess.run(cmd, capture_output=True, text=True)
        for ln in r.stdout.splitlines():
            print(f"  {ln}")
        if r.returncode != 0:
            for ln in r.stderr.splitlines():
                print(f"  [stderr] {ln}", file=sys.stderr)
            sys.exit(r.returncode)
    else:
        print(f"[dry-run] (skipping launch_batch.sh --dry-run invocation: local path missing: plan={os.path.isfile(plan)} bank={os.path.isdir(bank)} vcfg={os.path.isfile(vcfg)})")

print(f"[dry-run] monitor: poll_batch.sh every poll_interval; partial fetch (`fetch_batch.sh <state> --force --no-stop`) every partial_fetch_interval; on BATCH_DONE fetch (`fetch_batch.sh <state> --no-stop`) -> reuse VM for next pending batch, or stop VM + verify usage 0 when queue empty.")
PY
  exit 0
fi

# Runtime temp directory & cleanup trap.
RUN_TMPDIR="$(mktemp -d "${TMPDIR:-/tmp}/colab_rent_and_run.XXXXXX")"
SLOTS_FILE="${RUN_TMPDIR}/slots.json"
printf '[]\n' > "$SLOTS_FILE"
WATCHDOG_PID=""

cleanup() {
  if [ -n "$WATCHDOG_PID" ] && kill -0 "$WATCHDOG_PID" 2>/dev/null; then
    kill "$WATCHDOG_PID" 2>/dev/null || true
    wait "$WATCHDOG_PID" 2>/dev/null || true
  fi
  rm -rf "$RUN_TMPDIR"
}
trap cleanup EXIT

# Helper: stop a session and verify via `colab sessions` + `colab usage` that it is gone
# and that assignment count dropped (to <= expected_max_assignments if >= 0).
stop_and_verify_session() {
  local session="$1"
  local expected_max_asgn="${2:--1}"
  local event_name="$3"
  local batch_name="$4"
  local state_path="$5"
  local gpu="$6"
  local endpoint="$7"
  local attempt stop_rc=0 stop_out="" sess_json usage_json check_res

  for attempt in 1 2; do
    log_msg "stopping session=${session} (attempt=${attempt}, reason=${event_name})"
    if stop_out="$(timeout 120 "${COLAB_CMD[@]}" stop -s "$session" </dev/null 2>&1)"; then
      stop_rc=0
    else
      stop_rc=$?
    fi
    log_msg "colab stop -s ${session} rc=${stop_rc} out=$(printf '%s' "$stop_out" | tr '\n' ' ' | cut -c1-200)"

    sess_json="$(query_sessions_json)"
    usage_json="$(query_usage_json)"
    check_res="$(python3 - "$session" "$expected_max_asgn" "$sess_json" "$usage_json" <<'PY'
import json, sys
target, max_asgn_s, sj, uj = sys.argv[1:]
max_asgn = int(max_asgn_s)
sess = json.loads(sj)
usage = json.loads(uj)

still_listed = any(x["session"] == target for x in sess.get("sessions", [])) if sess.get("ok") else None
asgn = usage.get("active_assignments") if usage.get("ok") else None
rate = usage.get("usage_rate") if usage.get("ok") else None

dropped_ok = True
if still_listed is True:
    dropped_ok = False
if max_asgn >= 0 and asgn is not None and asgn > max_asgn:
    dropped_ok = False

status = "OK" if dropped_ok else "STILL_ACTIVE"
print(f"{status} still_listed={still_listed} active_assignments={asgn} usage_rate={rate} expected_max={max_asgn}")
PY
)"
    log_msg "stop verification (${session}): ${check_res}"
    case "$check_res" in
      OK\ *)
        registry_append "$event_name" "stopped" "$session" "$endpoint" "$gpu" "$batch_name" "$state_path" ""
        return 0
        ;;
    esac
    if [ "$attempt" -eq 1 ] && [ "$STOP_RETRY_DELAY" -gt 0 ]; then
      sleep "$STOP_RETRY_DELAY"
    fi
  done

  write_alert "stop_verify_failed session=${session} reason=${event_name} details=[${check_res}]"
  return 1
}

# Verify account usage is 0 when queue is empty and no managed VMs remain.
verify_account_usage_zero() {
  local usage_json sess_json res
  usage_json="$(query_usage_json)"
  sess_json="$(query_sessions_json)"
  res="$(python3 - "$usage_json" "$sess_json" <<'PY'
import json, sys
usage = json.loads(sys.argv[1])
sess = json.loads(sys.argv[2])
rate = usage.get("usage_rate")
asgn = usage.get("active_assignments")
bal = usage.get("balance")
live = [x["session"] for x in sess.get("sessions", [])] if sess.get("ok") else []
if not usage.get("ok"):
    print(f"UNKNOWN usage_rc={usage.get('rc')} live={live}")
elif (rate is not None and rate > 0) or (asgn is not None and asgn > 0):
    print(f"NONZERO usage_rate={rate} active_assignments={asgn} balance={bal} live={live}")
else:
    print(f"ZERO usage_rate={rate} active_assignments={asgn} balance={bal}")
PY
)"
  case "$res" in
    ZERO\ *)
      log_msg "verified account usage is 0 (${res})"
      ;;
    NONZERO\ *)
      write_alert "post_release_usage_nonzero ${res} (not auto-stopping unknown sessions)"
      ;;
    *)
      log_msg "post-release usage check inconclusive: ${res}"
      ;;
  esac
}

# Update a batch entry in $QUEUE_FILE atomically.
queue_update_batch() {
  local batch_id="$1"
  local updates_json="$2"
  python3 - "$QUEUE_FILE" "$batch_id" "$updates_json" <<'PY'
import json, os, pathlib, sys
qpath, bid, upd_s = sys.argv[1:]
upd = json.loads(upd_s)
p = pathlib.Path(qpath)
doc = json.loads(p.read_text(encoding="utf-8"))
found = False
for idx, b in enumerate(doc.get("batches", [])):
    cur_id = str(b.get("id") or f"batch_{idx}")
    if cur_id == bid:
        b.update(upd)
        found = True
        break
if not found:
    sys.exit(f"error: batch id {bid!r} not found in {qpath}")
tmp = p.with_name(p.name + f".tmp.{os.getpid()}")
tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
os.replace(tmp, p)
PY
}

# Return JSON of next pending batch (optionally filtered to require compatible_gpu in preferred_gpus),
# or empty output if none.
queue_next_pending() {
  local compat_gpu="${1:-}"
  python3 - "$QUEUE_FILE" "$REPO_ROOT" "$DEFAULT_GPUS" "$compat_gpu" <<'PY'
import json, os, pathlib, sys

qpath, repo_root, def_gpus_csv, compat_gpu = sys.argv[1:]
doc = json.loads(pathlib.Path(qpath).read_text(encoding="utf-8"))
defaults = doc.get("defaults") or {}
def_gpus = [g.strip() for g in def_gpus_csv.split(",") if g.strip()]

def resolve_path(p: str) -> str:
    expanded = os.path.expanduser(os.path.expandvars(p))
    if os.path.isabs(expanded):
        return expanded
    return os.path.join(repo_root, expanded)

for idx, b in enumerate(doc.get("batches", [])):
    if b.get("status", "pending") != "pending":
        continue
    gpus = b.get("preferred_gpus") or defaults.get("preferred_gpus") or def_gpus
    if compat_gpu and compat_gpu not in gpus:
        continue
    bid = str(b.get("id") or f"batch_{idx}")
    extra_tars = []
    for et in b.get("extra_tars") or []:
        parts = et.split(":", 1)
        if len(parts) == 2:
            extra_tars.append(f"{resolve_path(parts[0])}:{resolve_path(parts[1])}")
    out = {
        "id": bid,
        "plan": resolve_path(b["plan"]),
        "bank": resolve_path(b["bank"]),
        "vllm_config": resolve_path(b["vllm_config"]),
        "preferred_gpus": gpus,
        "high_mem": bool(b.get("high_mem", defaults.get("high_mem", False))),
        "commit": str(b.get("commit") or defaults.get("commit") or "HEAD"),
        "transport": str(b.get("transport") or defaults.get("transport") or "ssh"),
        "allow_uncommitted_plan": bool(b.get("allow_uncommitted_plan", False)),
        "extra_tars": extra_tars,
        "extra_wheel": resolve_path(b["extra_wheel"]) if b.get("extra_wheel") else "",
    }
    print(json.dumps(out))
    sys.exit(0)
PY
}

queue_pending_count() {
  python3 - "$QUEUE_FILE" <<'PY'
import json, pathlib, sys
doc = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
print(sum(1 for b in doc.get("batches", []) if b.get("status", "pending") == "pending"))
PY
}

slots_count() {
  python3 - "$SLOTS_FILE" <<'PY'
import json, pathlib, sys
print(len(json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))))
PY
}

slots_add() {
  local slot_json="$1"
  python3 - "$SLOTS_FILE" "$slot_json" <<'PY'
import json, os, pathlib, sys
p = pathlib.Path(sys.argv[1])
slots = json.loads(p.read_text(encoding="utf-8"))
slots.append(json.loads(sys.argv[2]))
tmp = p.with_name(p.name + f".tmp.{os.getpid()}")
tmp.write_text(json.dumps(slots, indent=2) + "\n", encoding="utf-8")
os.replace(tmp, p)
PY
}

slots_remove_session() {
  local session="$1"
  python3 - "$SLOTS_FILE" "$session" <<'PY'
import json, os, pathlib, sys
p = pathlib.Path(sys.argv[1])
target = sys.argv[2]
slots = [s for s in json.loads(p.read_text(encoding="utf-8")) if s["session"] != target]
tmp = p.with_name(p.name + f".tmp.{os.getpid()}")
tmp.write_text(json.dumps(slots, indent=2) + "\n", encoding="utf-8")
os.replace(tmp, p)
PY
}

slots_update_session() {
  local session="$1"
  local updates_json="$2"
  python3 - "$SLOTS_FILE" "$session" "$updates_json" <<'PY'
import json, os, pathlib, sys
p = pathlib.Path(sys.argv[1])
target = sys.argv[2]
upd = json.loads(sys.argv[3])
slots = json.loads(p.read_text(encoding="utf-8"))
for s in slots:
    if s["session"] == target:
        s.update(upd)
tmp = p.with_name(p.name + f".tmp.{os.getpid()}")
tmp.write_text(json.dumps(slots, indent=2) + "\n", encoding="utf-8")
os.replace(tmp, p)
PY
}

# Check budget: returns 0 if OK, 1 if breached (sets BUDGET_BREACH_REASON), 2 if query failed.
BUDGET_BREACH_REASON=""
check_budget() {
  local usage_json res
  BUDGET_BREACH_REASON=""
  usage_json="$(query_usage_json)"
  res="$(python3 - "$START_BALANCE" "$MAX_SPEND" "$BALANCE_FLOOR" "$usage_json" <<'PY'
import json, sys
start_bal, max_spend, floor = map(float, sys.argv[1:4])
usage = json.loads(sys.argv[4])
if not usage.get("ok") or usage.get("balance") is None:
    print("QUERY_FAIL")
    sys.exit(0)
bal = float(usage["balance"])
spent = round(start_bal - bal, 4)
eff_floor = max(floor, start_bal - max_spend)
if bal <= floor:
    print(f"BREACH balance={bal}<=floor={floor} spent={spent} start_balance={start_bal}")
elif spent >= max_spend:
    print(f"BREACH spent={spent}>=max_spend={max_spend} balance={bal} start_balance={start_bal}")
else:
    print(f"OK balance={bal} spent={spent} eff_floor={eff_floor:.2f}")
PY
)"
  case "$res" in
    OK\ *)
      log_msg "budget check: ${res}"
      return 0
      ;;
    BREACH\ *)
      BUDGET_BREACH_REASON="${res#BREACH }"
      return 1
      ;;
    *)
      log_msg "budget check: colab usage query failed (${usage_json}); continuing cautiously"
      return 2
      ;;
  esac
}

# Emergency stop all managed VMs (budget breach or hard deadline):
# partial fetch -> stop -> verify -> alert.
emergency_stop_all() {
  local reason="$1"
  local batch_status="$2"
  local slots_lines line sess gpu bid bname st ep stopped_list=""
  slots_lines="$(python3 - "$SLOTS_FILE" <<'PY'
import json, pathlib, sys
for s in json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")):
    print("\t".join([s["session"], s["gpu"], s["batch_id"], s["batch_name"], s["state_file"], s.get("endpoint", "")]))
PY
)"
  if [ -n "$slots_lines" ]; then
    while IFS=$'\t' read -r sess gpu bid bname st ep; do
      [ -n "$sess" ] || continue
      log_msg "emergency partial fetch before stop: session=${sess} state=${st}"
      if [ -f "$st" ]; then
        timeout 1800 bash "$FETCH_SCRIPT" "$st" --force --no-stop </dev/null >> "$LOG_FILE" 2>&1 || \
          log_msg "WARNING: emergency partial fetch failed for session=${sess}"
      fi
      stop_and_verify_session "$sess" -1 "stopped_${reason}" "$bname" "$st" "$gpu" "$ep" || true
      queue_update_batch "$bid" "$(python3 -c 'import json,sys,time; print(json.dumps({"status":sys.argv[1],"finished_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"error":sys.argv[2]}))' "$batch_status" "$reason")" || true
      slots_remove_session "$sess"
      stopped_list="${stopped_list:+${stopped_list},}${sess}"
    done <<< "$slots_lines"
  fi
  write_alert "reason=${reason} details=[${BUDGET_BREACH_REASON:-$reason}] stopped_sessions=[${stopped_list}]"
}

# Build launch_batch.sh argument array for a batch JSON + mode (new vs reuse).
# Invokes launch_batch.sh, queries `colab sessions` immediately afterward, updates registry,
# and on failure stops + verifies any leaked assignment.
# Sets LAST_LAUNCH_STATUS to: OK | FAILED | TOO_MANY_ASSIGNMENTS
# Sets LAST_LAUNCH_SESSION, LAST_LAUNCH_ENDPOINT, LAST_LAUNCH_GPU, LAST_LAUNCH_BATCH_NAME, LAST_LAUNCH_STATE_FILE
LAST_LAUNCH_STATUS=""
LAST_LAUNCH_SESSION=""
LAST_LAUNCH_ENDPOINT=""
LAST_LAUNCH_GPU=""
LAST_LAUNCH_BATCH_NAME=""
LAST_LAUNCH_STATE_FILE=""

run_launch_attempt() {
  local batch_json="$1"
  local gpu="$2"
  local reuse_session="${3:-}"

  local bid="" safe_bid="" plan="" bank="" vcfg="" high_mem="0" commit="HEAD" transport="ssh" allow_unc="0" extra_wheel=""
  local ts batch_name session_name out_dir state_file
  local before_usage before_sess before_asgn
  local launch_log launch_rc=0
  local after_sess after_usage

  eval "$(python3 - "$batch_json" <<'PY'
import json, re, shlex, sys
b = json.loads(sys.argv[1])
bid = b["id"]
safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", bid).strip("-")[:32] or "batch"
print(f"bid={shlex.quote(bid)}")
print(f"safe_bid={shlex.quote(safe)}")
print(f"plan={shlex.quote(b['plan'])}")
print(f"bank={shlex.quote(b['bank'])}")
print(f"vcfg={shlex.quote(b['vllm_config'])}")
print(f"high_mem={shlex.quote('1' if b.get('high_mem') else '0')}")
print(f"commit={shlex.quote(b.get('commit', 'HEAD'))}")
print(f"transport={shlex.quote(b.get('transport', 'ssh'))}")
print(f"allow_unc={shlex.quote('1' if b.get('allow_uncommitted_plan') else '0')}")
print(f"extra_wheel={shlex.quote(b.get('extra_wheel') or '')}")
PY
)"

  LAUNCH_SEQ=$((LAUNCH_SEQ + 1))
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  batch_name="${safe_bid}_${ts}_n${LAUNCH_SEQ}"
  if [ -n "$reuse_session" ]; then
    session_name="$reuse_session"
  else
    session_name="redo-${safe_bid:0:15}-${ts:9:6}-${LAUNCH_SEQ}"
  fi
  out_dir="${OUT_ROOT}/${batch_name}"
  state_file="${out_dir}/state.json"

  local cmd=(
    bash "$LAUNCH_SCRIPT" "$plan" "$bank"
    --gpu "$gpu"
    --vllm-config "$vcfg"
    --commit "$commit"
    --transport "$transport"
    --batch-name "$batch_name"
    --out-dir "$out_dir"
    --colab-bin "$COLAB_BIN"
  )
  if [ -n "$reuse_session" ]; then
    cmd+=(--reuse-session "$reuse_session")
  else
    cmd+=(--session "$session_name")
  fi
  if [ "$high_mem" = "1" ]; then
    cmd+=(--high-mem)
  fi
  if [ -n "$COLAB_CONFIG" ]; then
    cmd+=(--colab-config "$COLAB_CONFIG")
  fi
  if [ -n "$COLAB_AUTH" ]; then
    cmd+=(--colab-auth "$COLAB_AUTH")
  fi
  if [ "$allow_unc" = "1" ]; then
    cmd+=(--allow-uncommitted-plan)
  fi
  if [ -n "$extra_wheel" ]; then
    cmd+=(--extra-wheel "$extra_wheel")
  fi
  local et_line
  while IFS= read -r et_line; do
    [ -n "$et_line" ] && cmd+=(--extra-tar "$et_line")
  done < <(python3 - "$batch_json" <<'PY'
import json, sys
for et in json.loads(sys.argv[1]).get("extra_tars") or []:
    print(et)
PY
)

  # Snapshot pre-launch usage & sessions so we can detect any newly created assignment.
  before_usage="$(query_usage_json)"
  before_sess="$(query_sessions_json)"
  before_asgn="$(python3 -c 'import json,sys; u=json.loads(sys.argv[1]); print(u["active_assignments"] if u.get("ok") and u.get("active_assignments") is not None else -1)' "$before_usage")"

  launch_log="${RUN_TMPDIR}/launch_${batch_name}.log"
  log_msg "launching batch_id=${bid} batch_name=${batch_name} session=${session_name} gpu=${gpu} reuse=${reuse_session:-no}"
  if timeout 600 "${cmd[@]}" </dev/null > "$launch_log" 2>&1; then
    launch_rc=0
  else
    launch_rc=$?
  fi
  mkdir -p "$(dirname "$LOG_FILE")"
  cat "$launch_log" >> "$LOG_FILE"

  # Requirement 1: ALWAYS query `colab sessions` after every launch attempt (success or failure).
  after_sess="$(query_sessions_json)"
  after_usage="$(query_usage_json)"

  local inspect_out
  inspect_out="$(python3 - "$session_name" "$gpu" "$before_sess" "$after_sess" "$before_asgn" "$after_usage" <<'PY'
import json, shlex, sys
target, req_gpu, bs_raw, as_raw, before_asgn_s, au_raw = sys.argv[1:]
bs = json.loads(bs_raw)
as_ = json.loads(as_raw)
au = json.loads(au_raw)
before_asgn = int(before_asgn_s)
after_asgn = au["active_assignments"] if au.get("ok") and au.get("active_assignments") is not None else -1

before_names = {x["session"] for x in bs.get("sessions", [])} if bs.get("ok") else set()
after_map = {x["session"]: x for x in as_.get("sessions", [])} if as_.get("ok") else {}

target_info = after_map.get(target)
new_sessions = [x for name, x in after_map.items() if name not in before_names]
asgn_increased = (before_asgn >= 0 and after_asgn > before_asgn)

print(f"FOUND_TARGET={1 if target_info else 0}")
print(f"TARGET_ENDPOINT={shlex.quote(target_info['endpoint'] if target_info else '')}")
print(f"TARGET_GPU={shlex.quote((target_info['gpu'] or req_gpu) if target_info else req_gpu)}")
print(f"TARGET_RAW={shlex.quote(target_info['raw_line'] if target_info else '')}")
print(f"NEW_SESSIONS_JSON={shlex.quote(json.dumps(new_sessions))}")
print(f"ASGN_INCREASED={1 if asgn_increased else 0}")
PY
)"
  local FOUND_TARGET=0 TARGET_ENDPOINT="" TARGET_GPU="$gpu" TARGET_RAW="" NEW_SESSIONS_JSON="[]" ASGN_INCREASED=0
  eval "$inspect_out"

  if [ "$launch_rc" -eq 0 ]; then
    local ev="launched"
    [ -n "$reuse_session" ] && ev="reused"
    registry_append "$ev" "active" "$session_name" "$TARGET_ENDPOINT" "$TARGET_GPU" "$batch_name" "$state_file" "$TARGET_RAW"
    log_msg "launch succeeded: session=${session_name} endpoint=${TARGET_ENDPOINT:-unknown} gpu=${TARGET_GPU} state=${state_file}"
    LAST_LAUNCH_STATUS="OK"
    LAST_LAUNCH_SESSION="$session_name"
    LAST_LAUNCH_ENDPOINT="$TARGET_ENDPOINT"
    LAST_LAUNCH_GPU="$TARGET_GPU"
    LAST_LAUNCH_BATCH_NAME="$batch_name"
    LAST_LAUNCH_STATE_FILE="$state_file"
    return 0
  fi

  log_msg "launch FAILED (rc=${launch_rc}) for batch_id=${bid} session=${session_name} gpu=${gpu} reuse=${reuse_session:-no}"

  # If this was a fresh `colab new` attempt and ANY assignment exists/appeared,
  # record it in registry, ALWAYS stop it, and verify assignment count dropped.
  if [ -z "$reuse_session" ]; then
    local stopped_any=0
    if [ "$FOUND_TARGET" = "1" ]; then
      registry_append "launch_failed_assignment" "active" "$session_name" "$TARGET_ENDPOINT" "$TARGET_GPU" "$batch_name" "$state_file" "$TARGET_RAW"
      stop_and_verify_session "$session_name" "$before_asgn" "stopped_after_launch_failure" "$batch_name" "$state_file" "$TARGET_GPU" "$TARGET_ENDPOINT" || true
      stopped_any=1
    fi

    # Also stop any other newly created session that wasn't present before this attempt.
    local extra_lines es eep egpu eraw
    extra_lines="$(python3 - "$NEW_SESSIONS_JSON" "$session_name" <<'PY'
import json, sys
target = sys.argv[2]
for x in json.loads(sys.argv[1]):
    if x["session"] == target:
        continue
    print("\t".join([x["session"], x.get("endpoint", ""), x.get("gpu", ""), x.get("raw_line", "")]))
PY
)"
    if [ -n "$extra_lines" ]; then
      while IFS=$'\t' read -r es eep egpu eraw; do
        [ -n "$es" ] || continue
        registry_append "launch_failed_assignment" "active" "$es" "$eep" "${egpu:-$gpu}" "$batch_name" "$state_file" "$eraw"
        stop_and_verify_session "$es" "$before_asgn" "stopped_after_launch_failure" "$batch_name" "$state_file" "${egpu:-$gpu}" "$eep" || true
        stopped_any=1
      done <<< "$extra_lines"
    fi

    if [ "$stopped_any" = "0" ] && [ "$ASGN_INCREASED" = "1" ]; then
      # Assignment count rose even though `colab sessions` didn't list the name; attempt stop anyway + alert if unresolved.
      registry_append "launch_failed_assignment" "active" "$session_name" "" "$gpu" "$batch_name" "$state_file" ""
      stop_and_verify_session "$session_name" "$before_asgn" "stopped_after_launch_failure" "$batch_name" "$state_file" "$gpu" "" || true
    fi
  fi

  if grep -iEq 'too many assignments|toomanyassignments|assignment limit|maximum.*assignments|exceeded.*assignments|max.*concurrent.*assignments' "$launch_log"; then
    log_msg "detected too-many-assignments error from colab CLI during launch of ${bid} (gpu=${gpu})"
    LAST_LAUNCH_STATUS="TOO_MANY_ASSIGNMENTS"
  else
    LAST_LAUNCH_STATUS="FAILED"
  fi
  return 1
}

# --- Startup ---
log_msg "START queue=${QUEUE_FILE} max_spend=${MAX_SPEND} balance_floor=${BALANCE_FLOOR} max_concurrent_vms=${MAX_CONCURRENT_VMS} deadline=${DEADLINE_EPOCH} hard_deadline=${HARD_DEADLINE_EPOCH}"

INIT_USAGE="$(query_usage_json)"
START_BALANCE="$(python3 -c 'import json,sys; u=json.loads(sys.argv[1]); print(u["balance"] if u.get("ok") and u.get("balance") is not None else "")' "$INIT_USAGE")"
if [ -z "$START_BALANCE" ]; then
  log_msg "ERROR: unable to read initial balance from colab usage (${INIT_USAGE}); refusing to run without spend cap baseline"
  exit 12
fi
log_msg "initial balance=${START_BALANCE} CU (max_spend=${MAX_SPEND} CU, balance_floor=${BALANCE_FLOOR} CU)"

# Start account-level usage watchdog as a separate background loop (Requirement 2).
if [ "$NO_WATCHDOG" = "0" ]; then
  watchdog_loop &
  WATCHDOG_PID=$!
fi

LAST_RENT_ATTEMPT_TS=0

# --- Main Orchestrator Loop ---
while true; do
  NOW="$(epoch_now)"

  # 1) Hard deadline check: partial fetch + stop all active VMs + exit.
  if [ "$NOW" -ge "$HARD_DEADLINE_EPOCH" ]; then
    log_msg "hard deadline reached (now=${NOW} >= ${HARD_DEADLINE_EPOCH}); stopping any active VMs"
    BUDGET_BREACH_REASON="hard_deadline_reached"
    emergency_stop_all "hard_deadline" "stopped_deadline"
    exit 11
  fi

  # 2) Budget check every loop iteration / poll (Requirement 4).
  if ! check_budget; then
    if [ -n "$BUDGET_BREACH_REASON" ]; then
      log_msg "BUDGET BREACH: ${BUDGET_BREACH_REASON}"
      emergency_stop_all "budget_breach" "stopped_budget"
      exit 10
    fi
  fi

  # 3) Poll all active VM slots whose poll interval has elapsed.
  SLOTS_DUMP="$(python3 - "$SLOTS_FILE" "$NOW" "$POLL_INTERVAL" <<'PY'
import json, pathlib, sys
slots = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
now, poll_int = int(sys.argv[2]), int(sys.argv[3])
for s in slots:
    due = 1 if (now - int(s.get("last_poll_ts", 0))) >= poll_int else 0
    print("\t".join([
        str(due), s["session"], s["gpu"], s["batch_id"], s["batch_name"],
        s["state_file"], s.get("endpoint", ""), str(s.get("last_partial_fetch_ts", 0)),
    ]))
PY
)"

  if [ -n "$SLOTS_DUMP" ]; then
    while IFS=$'\t' read -r poll_due sess gpu bid bname st ep last_pf; do
      [ -n "$sess" ] || continue
      if [ "$poll_due" != "1" ]; then
        continue
      fi

      log_msg "polling session=${sess} batch=${bname} gpu=${gpu}"
      timeout 180 bash "$POLL_SCRIPT" "$st" </dev/null >> "$LOG_FILE" 2>&1 || true
      slots_update_session "$sess" "$(python3 -c 'import json,sys; print(json.dumps({"last_poll_ts":int(sys.argv[1])}))' "$NOW")"

      # Check if BATCH_DONE is ready and fetch+verify WITHOUT stopping yet (`--no-stop`).
      fetch_rc=0
      if timeout 1800 bash "$FETCH_SCRIPT" "$st" --no-stop </dev/null >> "$LOG_FILE" 2>&1; then
        fetch_rc=0
      else
        fetch_rc=$?
      fi

      if [ "$fetch_rc" -eq 0 ]; then
        log_msg "BATCH_DONE fetched & verified: batch_id=${bid} session=${sess}"
        queue_update_batch "$bid" "$(python3 -c 'import json,time; print(json.dumps({"status":"done","finished_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}))')"

        # Re-check budget before deciding whether to reuse VM for next batch (Requirement 4).
        if ! check_budget && [ -n "$BUDGET_BREACH_REASON" ]; then
          log_msg "BUDGET BREACH right after batch completion: ${BUDGET_BREACH_REASON}"
          emergency_stop_all "budget_breach" "stopped_budget"
          exit 10
        fi

        # Requirement 3: if queue has a next compatible pending batch (and before deadline), reuse SAME session.
        reused_ok=0
        while [ "$(epoch_now)" -lt "$DEADLINE_EPOCH" ]; do
          next_batch="$(queue_next_pending "$gpu")"
          [ -n "$next_batch" ] || break
          next_bid="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$next_batch")"
          log_msg "queue has next pending batch=${next_bid} compatible with gpu=${gpu}; reusing session=${sess}"
          if run_launch_attempt "$next_batch" "$gpu" "$sess"; then
            now_reuse="$(epoch_now)"
            queue_update_batch "$next_bid" "$(python3 -c 'import json,sys,time; print(json.dumps({"status":"running","session":sys.argv[1],"gpu":sys.argv[2],"batch_name":sys.argv[3],"state_file":sys.argv[4],"started_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}))' \
              "$LAST_LAUNCH_SESSION" "$LAST_LAUNCH_GPU" "$LAST_LAUNCH_BATCH_NAME" "$LAST_LAUNCH_STATE_FILE")"
            slots_update_session "$sess" "$(python3 -c 'import json,sys; print(json.dumps({"batch_id":sys.argv[1],"batch_name":sys.argv[2],"state_file":sys.argv[3],"endpoint":sys.argv[4],"last_poll_ts":int(sys.argv[5]),"last_partial_fetch_ts":int(sys.argv[5])}))' \
              "$next_bid" "$LAST_LAUNCH_BATCH_NAME" "$LAST_LAUNCH_STATE_FILE" "$LAST_LAUNCH_ENDPOINT" "$now_reuse")"
            reused_ok=1
            break
          else
            log_msg "ERROR: reuse launch failed for batch=${next_bid} on session=${sess}"
            queue_update_batch "$next_bid" "$(python3 -c 'import json,time; print(json.dumps({"status":"failed","finished_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"error":"reuse_launch_failed"}))')"
            # Check if the session itself died; if so, stop trying to reuse it.
            cur_sess_json="$(query_sessions_json)"
            if ! python3 -c 'import json,sys; d=json.loads(sys.argv[1]); sys.exit(0 if (not d.get("ok") or any(x["session"]==sys.argv[2] for x in d.get("sessions",[]))) else 1)' "$cur_sess_json" "$sess"; then
              log_msg "reused session=${sess} is no longer active in colab sessions"
              registry_append "session_gone" "stopped" "$sess" "$ep" "$gpu" "$bname" "$st" ""
              slots_remove_session "$sess"
              reused_ok=2
              break
            fi
          fi
        done

        if [ "$reused_ok" -eq 0 ]; then
          # No more compatible pending batches (or queue empty): release VM and verify usage 0 if last VM.
          rem_slots_after=$(($(slots_count) - 1))
          exp_max=-1
          [ "$rem_slots_after" -eq 0 ] && exp_max=0
          stop_and_verify_session "$sess" "$exp_max" "released_queue_empty" "$bname" "$st" "$gpu" "$ep" || true
          slots_remove_session "$sess"
          if [ "$(slots_count)" -eq 0 ]; then
            verify_account_usage_zero
          fi
        fi
      else
        if [ "$fetch_rc" -eq 1 ]; then
          log_msg "WARNING: fetch_batch.sh verification/download failed (rc=1) for session=${sess}; keeping session alive for retry"
        fi

        # Requirement 5: periodic partial fetch every PARTIAL_FETCH_INTERVAL (default 30 min).
        if [ $((NOW - last_pf)) -ge "$PARTIAL_FETCH_INTERVAL" ]; then
          log_msg "partial fetch (no stop) for session=${sess} batch=${bname}"
          if timeout 1800 bash "$FETCH_SCRIPT" "$st" --force --no-stop </dev/null >> "$LOG_FILE" 2>&1; then
            log_msg "partial fetch OK for session=${sess}"
          else
            log_msg "WARNING: partial fetch failed for session=${sess}"
          fi
          slots_update_session "$sess" "$(python3 -c 'import json,sys; print(json.dumps({"last_partial_fetch_ts":int(sys.argv[1])}))' "$NOW")"
        fi

        # Check if session vanished unexpectedly from `colab sessions`.
        live_check="$(query_sessions_json)"
        if python3 -c 'import json,sys; d=json.loads(sys.argv[1]); sys.exit(0 if d.get("ok") and not any(x["session"]==sys.argv[2] for x in d.get("sessions",[])) else 1)' "$live_check" "$sess"; then
          write_alert "session_gone_without_fetch session=${sess} batch=${bname} state=${st}"
          registry_append "session_gone" "stopped" "$sess" "$ep" "$gpu" "$bname" "$st" ""
          queue_update_batch "$bid" "$(python3 -c 'import json,time; print(json.dumps({"status":"failed","finished_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"error":"session_gone_without_fetch"}))')"
          slots_remove_session "$sess"
        fi
      fi
    done <<< "$SLOTS_DUMP"
  fi

  # 4) Check if queue is completely done and no active VMs remain.
  PENDING_N="$(queue_pending_count)"
  ACTIVE_N="$(slots_count)"
  if [ "$PENDING_N" -eq 0 ] && [ "$ACTIVE_N" -eq 0 ]; then
    verify_account_usage_zero
    log_msg "QUEUE_COMPLETE all batches processed and all managed VMs stopped."
    exit 0
  fi

  # 5) If past rent deadline and no active VMs remain, stop trying to rent and exit.
  NOW="$(epoch_now)"
  if [ "$NOW" -ge "$DEADLINE_EPOCH" ] && [ "$ACTIVE_N" -eq 0 ]; then
    log_msg "deadline reached with ${PENDING_N} pending batch(es) and 0 active VMs; exiting."
    exit 11
  fi

  # 6) Rent attempts (Requirement 6): A100 -> G4 -> L4 every RENT_INTERVAL (20 min) up to DEADLINE,
  # supporting up to MAX_CONCURRENT_VMS (2).
  if [ "$NOW" -lt "$DEADLINE_EPOCH" ] && [ "$PENDING_N" -gt 0 ] && [ "$ACTIVE_N" -lt "$MAX_CONCURRENT_VMS" ] \
     && { [ "$LAST_RENT_ATTEMPT_TS" -eq 0 ] || [ $((NOW - LAST_RENT_ATTEMPT_TS)) -ge "$RENT_INTERVAL" ]; }; then
    rent_cycle_blocked=0
    while [ "$(slots_count)" -lt "$MAX_CONCURRENT_VMS" ] && [ "$rent_cycle_blocked" -eq 0 ]; do
      next_batch="$(queue_next_pending "")"
      [ -n "$next_batch" ] || break

      # Check budget before every launch (Requirement 4).
      if ! check_budget && [ -n "$BUDGET_BREACH_REASON" ]; then
        log_msg "BUDGET BREACH before rent attempt: ${BUDGET_BREACH_REASON}"
        emergency_stop_all "budget_breach" "stopped_budget"
        exit 10
      fi

      next_bid="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$next_batch")"
      gpu_list="$(python3 -c 'import json,sys; print("\n".join(json.loads(sys.argv[1])["preferred_gpus"]))' "$next_batch")"

      rented_this_batch=0
      while IFS= read -r try_gpu; do
        [ -n "$try_gpu" ] || continue
        if run_launch_attempt "$next_batch" "$try_gpu" ""; then
          now_launched="$(epoch_now)"
          queue_update_batch "$next_bid" "$(python3 -c 'import json,sys,time; print(json.dumps({"status":"running","session":sys.argv[1],"gpu":sys.argv[2],"batch_name":sys.argv[3],"state_file":sys.argv[4],"started_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}))' \
            "$LAST_LAUNCH_SESSION" "$LAST_LAUNCH_GPU" "$LAST_LAUNCH_BATCH_NAME" "$LAST_LAUNCH_STATE_FILE")"
          slots_add "$(python3 -c 'import json,sys; print(json.dumps({"session":sys.argv[1],"endpoint":sys.argv[2],"gpu":sys.argv[3],"batch_id":sys.argv[4],"batch_name":sys.argv[5],"state_file":sys.argv[6],"last_poll_ts":int(sys.argv[7]),"last_partial_fetch_ts":int(sys.argv[7])}))' \
            "$LAST_LAUNCH_SESSION" "$LAST_LAUNCH_ENDPOINT" "$LAST_LAUNCH_GPU" "$next_bid" "$LAST_LAUNCH_BATCH_NAME" "$LAST_LAUNCH_STATE_FILE" "$now_launched")"
          rented_this_batch=1
          break
        fi

        if [ "$LAST_LAUNCH_STATUS" = "TOO_MANY_ASSIGNMENTS" ] && [ "$(slots_count)" -ge 1 ]; then
          log_msg "concurrent VM rent rejected (too many assignments); keeping existing $(slots_count) VM(s) running via queue"
          rent_cycle_blocked=1
          break
        fi
      done <<< "$gpu_list"

      if [ "$rented_this_batch" -eq 0 ]; then
        rent_cycle_blocked=1
      fi
    done
    LAST_RENT_ATTEMPT_TS="$(epoch_now)"
  fi

  # 7) Sleep until next tick (capped at TICK_INTERVAL; 0 allowed for fast unit tests).
  if [ "$TICK_INTERVAL" -gt 0 ]; then
    sleep "$TICK_INTERVAL"
  fi
done
