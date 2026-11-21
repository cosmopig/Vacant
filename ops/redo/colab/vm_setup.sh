#!/usr/bin/env bash
# Colab VM setup for redo-harness batches (idempotent).
#
# Installs pinned vLLM (in isolated /content/venv-vllm), pinned Node + pi
# (matching local `pi --version`), optional opencode, renders pi models.json
# pointing at http://127.0.0.1:8000/v1, launches `vllm serve` listening on
# 127.0.0.1 with VLLM_USE_FLASHINFER_SAMPLER=0 and --enable-prompt-tokens-details,
# waits for /v1/models, and writes a provenance ready file (VM_READY.json).
#
# Lessons carried over from ops/colab_campaign_20260927 & ops/colab_dabstep_v37_20261002:
# - VLLM_USE_FLASHINFER_SAMPLER=0 on sm_120 (RTX PRO 6000 Blackwell).
# - --enable-prompt-tokens-details so cached_tokens is reported.
# - Listen strictly on 127.0.0.1 (never 0.0.0.0).
# - Isolated uv venv for vLLM (do not mix with Colab preinstalled torch/CUDA).
# - Never `pkill -f` a pattern that could match this shell; manage vLLM via PID file.
# - No extra Python dependencies for redo.py (stdlib only).
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CONFIG=""
WORK_DIR="/srv/redo"
OPT_DIR="/opt/redo"
VLLM_VENV="/content/venv-vllm"
MODELS_CACHE_DIR="/content/models"
PI_DIR="${HOME}/.pi/agent"
READY_FILE=""
DRY_RUN=0
SKIP_INSTALL=0
SKIP_VLLM=0

usage() {
  cat <<'EOF'
Usage: vm_setup.sh --config <vllm_config.json> [options]

Options:
  --config <path>       JSON config for vLLM, model, and pinned tool versions (required)
  --work-dir <dir>      VM working dir for logs, pidfile, templates (default: /srv/redo)
  --opt-dir <dir>       Install root for node/pi/opencode (default: /opt/redo)
  --vllm-venv <dir>     Isolated venv path for vLLM (default: /content/venv-vllm)
  --models-dir <dir>    Directory for downloaded HF weights (default: /content/models)
  --pi-dir <dir>        Directory where pi models.json is written (default: ~/.pi/agent)
  --ready-file <path>   Provenance ready JSON path (default: <work-dir>/VM_READY.json)
  --skip-install        Skip installing vLLM, node, pi, opencode (use existing binaries)
  --skip-vllm           Skip model download & vLLM start (expect endpoint already running)
  --dry-run             Print exact commands that would run; modify nothing
  -h, --help            Show this help
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --config) CONFIG="$2"; shift 2 ;;
    --work-dir) WORK_DIR="$2"; shift 2 ;;
    --opt-dir) OPT_DIR="$2"; shift 2 ;;
    --vllm-venv) VLLM_VENV="$2"; shift 2 ;;
    --models-dir) MODELS_CACHE_DIR="$2"; shift 2 ;;
    --pi-dir) PI_DIR="$2"; shift 2 ;;
    --ready-file) READY_FILE="$2"; shift 2 ;;
    --skip-install) SKIP_INSTALL=1; shift ;;
    --skip-vllm) SKIP_VLLM=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$CONFIG" ] || [ ! -f "$CONFIG" ]; then
  echo "error: --config <vllm_config.json> is required and must exist" >&2
  exit 2
fi

READY_FILE="${READY_FILE:-${WORK_DIR}/VM_READY.json}"

# Parse config safely via stdlib python3 (no jq dependency).
eval "$(python3 - "$CONFIG" <<'PY'
import json, shlex, sys
cfg = json.loads(open(sys.argv[1], encoding="utf-8").read())

def out(k, v):
    if v is None:
        v = ""
    elif isinstance(v, bool):
        v = "1" if v else "0"
    print(f"{k}={shlex.quote(str(v))}")

out("VLLM_VERSION", cfg.get("vllm_version", "0.30.0"))
vllm_ver = str(cfg.get("vllm_version", "0.30.0"))
family = str(cfg.get("model_family", "gemma4")).lower()
out("NODE_VERSION", cfg.get("node_version", "v22.23.2"))
out("PI_VERSION", cfg.get("pi_version", "0.87.1"))
out("INSTALL_OPENCODE", bool(cfg.get("install_opencode", False)))
out("OPENCODE_VERSION", cfg.get("opencode_version", "1.18.33"))
out("MODEL_FAMILY", family)
out("MODEL_ID", cfg.get("model_id", "google/gemma-4-12B-it-qat-w4a16-ct"))
out("MODEL_REVISION", cfg.get("model_revision") or "")
out("SERVED_MODEL_NAME", cfg.get("served_model_name", "gemma-4-12b-it-qat"))
out("HOST", cfg.get("host", "127.0.0.1"))
out("PORT", int(cfg.get("port", 8000)))
out("MAX_MODEL_LEN", int(cfg.get("max_model_len", 262144)))
out("MAX_TOKENS", int(cfg.get("max_tokens", 16384)))
out("MAX_NUM_SEQS", int(cfg.get("max_num_seqs", 16)))
out("GPU_MEM_UTIL", cfg.get("gpu_memory_utilization", 0.90))
out("ENABLE_PREFIX_CACHING", bool(cfg.get("enable_prefix_caching", True)))
out("ENABLE_PROMPT_TOKENS_DETAILS", bool(cfg.get("enable_prompt_tokens_details", True)))
out("ASYNC_SCHEDULING", bool(cfg.get("async_scheduling", True)))
out("FLASHINFER_SAMPLER", cfg.get("flashinfer_sampler", 0))

# Family defaults when keys are omitted from a minimal config (explicit null disables).
def family_default(key, gemma_val, qwen_val):
    if key in cfg:
        return cfg[key] or ""
    if family == "gemma4":
        return gemma_val
    if family in ("qwen", "qwen3"):
        return qwen_val
    return ""

out("TOOL_CALL_PARSER", family_default("tool_call_parser", "gemma4", "hermes"))
out("REASONING_PARSER", family_default("reasoning_parser", "gemma4", "qwen3"))
out("CHAT_TEMPLATE_URL", family_default(
    "chat_template_url",
    f"https://raw.githubusercontent.com/vllm-project/vllm/v{vllm_ver}/examples/tool_chat_template_gemma4.jinja",
    "",
))
out("CHAT_TEMPLATE_PATH", cfg.get("chat_template_path") or "")
out("LIMIT_MM_PER_PROMPT", family_default("limit_mm_per_prompt", '{"image": 0, "audio": 0}', ""))
out("READY_TIMEOUT_S", int(cfg.get("ready_timeout_s", 1200)))
PY
)"

# Derive safe local directory slug for downloaded HF model weights.
MODEL_SLUG=$(python3 -c 'import re,sys; print(re.sub(r"[^A-Za-z0-9._-]+", "_", sys.argv[1]).strip("_"))' "$MODEL_ID")
if [ -d "$MODEL_ID" ]; then
  LOCAL_MODEL_DIR="$MODEL_ID"
else
  LOCAL_MODEL_DIR="${MODELS_CACHE_DIR}/${MODEL_SLUG}"
fi

# Determine chat template path on disk.
TEMPLATE_LOCAL=""
if [ -n "$CHAT_TEMPLATE_PATH" ]; then
  TEMPLATE_LOCAL="$CHAT_TEMPLATE_PATH"
elif [ -n "$CHAT_TEMPLATE_URL" ]; then
  TEMPLATE_LOCAL="${WORK_DIR}/chat_template_${MODEL_FAMILY}.jinja"
fi

# Build exact vllm serve argv array (preserving quoting for extra_vllm_args).
VLLM_ARGS=(
  "${VLLM_VENV}/bin/vllm" serve "$LOCAL_MODEL_DIR"
  --served-model-name "$SERVED_MODEL_NAME"
  --max-model-len "$MAX_MODEL_LEN"
  --max-num-seqs "$MAX_NUM_SEQS"
  --gpu-memory-utilization "$GPU_MEM_UTIL"
  --host "$HOST"
  --port "$PORT"
)
[ "$ENABLE_PREFIX_CACHING" = "1" ] && VLLM_ARGS+=(--enable-prefix-caching)
[ "$ENABLE_PROMPT_TOKENS_DETAILS" = "1" ] && VLLM_ARGS+=(--enable-prompt-tokens-details)
[ "$ASYNC_SCHEDULING" = "1" ] && VLLM_ARGS+=(--async-scheduling)
if [ -n "$TOOL_CALL_PARSER" ]; then
  VLLM_ARGS+=(--enable-auto-tool-choice --tool-call-parser "$TOOL_CALL_PARSER")
fi
if [ -n "$REASONING_PARSER" ]; then
  VLLM_ARGS+=(--reasoning-parser "$REASONING_PARSER")
fi
if [ -n "$TEMPLATE_LOCAL" ]; then
  VLLM_ARGS+=(--chat-template "$TEMPLATE_LOCAL")
fi
if [ -n "$LIMIT_MM_PER_PROMPT" ]; then
  VLLM_ARGS+=(--limit-mm-per-prompt "$LIMIT_MM_PER_PROMPT")
fi
while IFS= read -r extra_arg; do
  [ -n "$extra_arg" ] && VLLM_ARGS+=("$extra_arg")
done < <(python3 - "$CONFIG" <<'PY'
import json, sys
for a in json.loads(open(sys.argv[1], encoding="utf-8").read()).get("extra_vllm_args", []):
    print(a)
PY
)

fmt_cmd() {
  local out="" a
  for a in "$@"; do
    out+="$(printf '%q ' "$a")"
  done
  printf '%s\n' "${out% }"
}

if [ "$DRY_RUN" = "1" ]; then
  echo "[dry-run] vm_setup.sh config=${CONFIG} work_dir=${WORK_DIR} ready_file=${READY_FILE}"
  if [ "$SKIP_INSTALL" = "0" ]; then
    echo "[dry-run] mkdir -p $(printf '%q' "$WORK_DIR") $(printf '%q' "$OPT_DIR") $(printf '%q' "$MODELS_CACHE_DIR")"
    echo "[dry-run] install Node ${NODE_VERSION} -> ${OPT_DIR}/node (symlink into /usr/local/bin)"
    echo "[dry-run] PATH=${OPT_DIR}/node/bin:\$PATH npm install -g --ignore-scripts --prefix ${OPT_DIR}/pi @earendil-works/pi-coding-agent@${PI_VERSION}"
    if [ "$INSTALL_OPENCODE" = "1" ]; then
      echo "[dry-run] PATH=${OPT_DIR}/node/bin:\$PATH npm install -g --ignore-scripts --prefix ${OPT_DIR}/opencode opencode-ai@${OPENCODE_VERSION}"
    fi
    echo "[dry-run] python3 -m pip install -q uv && uv venv -q -p 3.12 ${VLLM_VENV} && uv pip install -q -p ${VLLM_VENV}/bin/python vllm==${VLLM_VERSION}"
  else
    echo "[dry-run] --skip-install set: skipping Node/pi/vLLM installation"
  fi
  if [ "$SKIP_VLLM" = "0" ]; then
    if [ -n "$CHAT_TEMPLATE_URL" ]; then
      echo "[dry-run] curl -fsSL -o $(printf '%q' "$TEMPLATE_LOCAL") $(printf '%q' "$CHAT_TEMPLATE_URL")"
    fi
    if [ ! -d "$MODEL_ID" ]; then
      if [ -n "$MODEL_REVISION" ]; then
        echo "[dry-run] ${VLLM_VENV}/bin/hf download $(printf '%q' "$MODEL_ID") --revision $(printf '%q' "$MODEL_REVISION") --local-dir $(printf '%q' "$LOCAL_MODEL_DIR")"
      else
        echo "[dry-run] ${VLLM_VENV}/bin/hf download $(printf '%q' "$MODEL_ID") --local-dir $(printf '%q' "$LOCAL_MODEL_DIR")"
      fi
    fi
    echo "[dry-run] setsid nohup env VLLM_USE_FLASHINFER_SAMPLER=${FLASHINFER_SAMPLER} $(fmt_cmd "${VLLM_ARGS[@]}") </dev/null > ${WORK_DIR}/vllm_server.log 2>&1 & echo \$! > ${WORK_DIR}/vllm.pid"
  else
    echo "[dry-run] --skip-vllm set: skipping weight download and vllm serve"
  fi
  echo "[dry-run] python3 $(printf '%q' "${SCRIPT_DIR}/render_models.py") --template $(printf '%q' "${SCRIPT_DIR}/models.json.tmpl") --config $(printf '%q' "$CONFIG") --out $(printf '%q' "${PI_DIR}/models.json")"
  echo "[dry-run] wait up to ${READY_TIMEOUT_S}s for http://${HOST}:${PORT}/v1/models containing ${SERVED_MODEL_NAME}"
  echo "[dry-run] write provenance JSON to ${READY_FILE}"
  exit 0
fi

mkdir -p "$WORK_DIR" "$PI_DIR"
SETUP_LOG="${WORK_DIR}/vm_setup.log"

log() {
  local line
  line="$(date -u +%Y-%m-%dT%H:%M:%SZ)  $*"
  echo "$line" | tee -a "$SETUP_LOG"
}

log "vm_setup start (config=${CONFIG}, model=${MODEL_ID}, served=${SERVED_MODEL_NAME}, host=${HOST}:${PORT})"

# 1) Install pinned Node, pi, optional opencode, and vLLM (in isolated venv).
if [ "$SKIP_INSTALL" = "0" ]; then
  mkdir -p "$OPT_DIR" "$MODELS_CACHE_DIR"

  # 1a) Node (pinned binary tarball, matching local node -v)
  if [ "$("${OPT_DIR}/node/bin/node" -v 2>/dev/null || true)" != "$NODE_VERSION" ]; then
    log "Installing Node ${NODE_VERSION} into ${OPT_DIR}/node"
    curl -fsSL -o /tmp/node.tar.xz "https://nodejs.org/dist/${NODE_VERSION}/node-${NODE_VERSION}-linux-x64.tar.xz"
    rm -rf "${OPT_DIR}/node" && mkdir -p "${OPT_DIR}/node"
    tar -xJf /tmp/node.tar.xz -C "${OPT_DIR}/node" --strip-components=1
    rm -f /tmp/node.tar.xz
  fi
  ln -sf "${OPT_DIR}/node/bin/node" /usr/local/bin/node
  ln -sf "${OPT_DIR}/node/bin/npm" /usr/local/bin/npm
  ln -sf "${OPT_DIR}/node/bin/npx" /usr/local/bin/npx
  log "Node ready: $("${OPT_DIR}/node/bin/node" -v)"

  # 1b) pi (pinned to match local `pi --version`)
  if [ "$(PATH="${OPT_DIR}/node/bin:$PATH" "${OPT_DIR}/pi/bin/pi" --version 2>/dev/null | tail -1 || true)" != "$PI_VERSION" ]; then
    log "Installing @earendil-works/pi-coding-agent@${PI_VERSION} into ${OPT_DIR}/pi"
    PATH="${OPT_DIR}/node/bin:$PATH" npm install -g --ignore-scripts --prefix "${OPT_DIR}/pi" "@earendil-works/pi-coding-agent@${PI_VERSION}" >> "$SETUP_LOG" 2>&1
  fi
  ln -sf "${OPT_DIR}/pi/bin/pi" /usr/local/bin/pi
  GOT_PI=$(PATH="${OPT_DIR}/node/bin:$PATH" "${OPT_DIR}/pi/bin/pi" --version | tail -1)
  if [ "$GOT_PI" != "$PI_VERSION" ]; then
    log "ERROR: pi version mismatch: got=${GOT_PI} expected=${PI_VERSION}"
    exit 1
  fi
  log "pi ready: ${GOT_PI}"

  # 1c) Optional opencode
  if [ "$INSTALL_OPENCODE" = "1" ]; then
    if [ "$(PATH="${OPT_DIR}/node/bin:$PATH" "${OPT_DIR}/opencode/bin/opencode" --version 2>/dev/null | tail -1 || true)" != "$OPENCODE_VERSION" ]; then
      log "Installing opencode-ai@${OPENCODE_VERSION} into ${OPT_DIR}/opencode"
      PATH="${OPT_DIR}/node/bin:$PATH" npm install -g --ignore-scripts --prefix "${OPT_DIR}/opencode" "opencode-ai@${OPENCODE_VERSION}" >> "$SETUP_LOG" 2>&1
    fi
    ln -sf "${OPT_DIR}/opencode/bin/opencode" /usr/local/bin/opencode
    log "opencode ready: $(PATH="${OPT_DIR}/node/bin:$PATH" "${OPT_DIR}/opencode/bin/opencode" --version | tail -1)"
  fi

  # 1d) vLLM (isolated venv so we never clash with Colab's preinstalled torch/CUDA)
  export PATH="/usr/local/bin:${HOME}/.local/bin:${PATH}"
  GOT_VLLM=$("${VLLM_VENV}/bin/python" -c 'import vllm; print(vllm.__version__)' 2>/dev/null || true)
  if [ "$GOT_VLLM" != "$VLLM_VERSION" ]; then
    log "Installing vllm==${VLLM_VERSION} into isolated venv ${VLLM_VENV}"
    if ! command -v uv >/dev/null 2>&1; then
      python3 -m pip install -q uv >> "$SETUP_LOG" 2>&1
    fi
    if [ ! -x "${VLLM_VENV}/bin/python" ]; then
      uv venv -q -p 3.12 "$VLLM_VENV" >> "$SETUP_LOG" 2>&1
    fi
    uv pip install -q -p "${VLLM_VENV}/bin/python" "vllm==${VLLM_VERSION}" >> "$SETUP_LOG" 2>&1
  fi
  log "vLLM ready: $("${VLLM_VENV}/bin/python" -c 'import vllm, torch; print(f"vllm={vllm.__version__} torch={torch.__version__} cuda={torch.version.cuda}")')"
fi

# 2) Render pi models.json before starting/checking server.
python3 "${SCRIPT_DIR}/render_models.py" \
  --template "${SCRIPT_DIR}/models.json.tmpl" \
  --config "$CONFIG" \
  --out "${PI_DIR}/models.json"
log "Rendered pi models.json -> ${PI_DIR}/models.json (contextWindow=${MAX_MODEL_LEN})"

# 3) Download weights & template, then start vLLM (managed via PID file; never pkill -f).
VLLM_PID=""
if [ "$SKIP_VLLM" = "0" ]; then
  if [ -n "$CHAT_TEMPLATE_URL" ] && [ ! -f "$TEMPLATE_LOCAL" ]; then
    log "Downloading chat template -> ${TEMPLATE_LOCAL}"
    curl -fsSL -o "$TEMPLATE_LOCAL" "$CHAT_TEMPLATE_URL"
  fi

  if [ ! -d "$MODEL_ID" ]; then
    mkdir -p "$LOCAL_MODEL_DIR"
    log "Downloading HF model ${MODEL_ID} (revision=${MODEL_REVISION:-HEAD}) -> ${LOCAL_MODEL_DIR}"
    HF_ARGS=("${VLLM_VENV}/bin/hf" download "$MODEL_ID" --local-dir "$LOCAL_MODEL_DIR")
    if [ -n "$MODEL_REVISION" ]; then
      HF_ARGS+=(--revision "$MODEL_REVISION")
    fi
    "${HF_ARGS[@]}" >> "$SETUP_LOG" 2>&1
  fi

  # Stop a previous vLLM started by this script using its exact PID file (never pkill -f).
  PID_FILE="${WORK_DIR}/vllm.pid"
  if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
      log "Stopping previous vLLM PID ${OLD_PID} from ${PID_FILE}"
      kill "$OLD_PID" 2>/dev/null || true
      for _ in $(seq 1 15); do
        kill -0 "$OLD_PID" 2>/dev/null || break
        sleep 1
      done
      kill -9 "$OLD_PID" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
  fi

  log "Starting vLLM: VLLM_USE_FLASHINFER_SAMPLER=${FLASHINFER_SAMPLER} $(fmt_cmd "${VLLM_ARGS[@]}")"
  setsid nohup env "VLLM_USE_FLASHINFER_SAMPLER=${FLASHINFER_SAMPLER}" "${VLLM_ARGS[@]}" \
    </dev/null > "${WORK_DIR}/vllm_server.log" 2>&1 &
  VLLM_PID=$!
  echo "$VLLM_PID" > "$PID_FILE"
  log "vLLM launched with PID ${VLLM_PID} (log: ${WORK_DIR}/vllm_server.log)"
fi

# 4) Wait for /v1/models to respond with HTTP 200 and served_model_name.
MODELS_URL="http://${HOST}:${PORT}/v1/models"
log "Waiting up to ${READY_TIMEOUT_S}s for ${MODELS_URL} containing ${SERVED_MODEL_NAME}"
python3 - "$MODELS_URL" "$SERVED_MODEL_NAME" "$READY_TIMEOUT_S" "${VLLM_PID}" "${WORK_DIR}/vllm_server.log" <<'PY'
import os, sys, time, urllib.request

url, need, timeout_s, pid_s, log_path = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]
deadline = time.time() + timeout_s
last_err = ""
while True:
    if pid_s:
        try:
            os.kill(int(pid_s), 0)
        except OSError:
            print(f"ERROR: vLLM process {pid_s} exited before becoming ready.", file=sys.stderr)
            if os.path.isfile(log_path):
                tail = open(log_path, encoding="utf-8", errors="replace").read()[-4000:]
                print(tail, file=sys.stderr)
            sys.exit(1)
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read(200_000).decode("utf-8", "replace")
            if resp.status == 200 and (not need or need in body):
                print(f"Endpoint ready: {url} (matched {need!r})")
                sys.exit(0)
            last_err = f"HTTP {resp.status}, body missing {need!r}"
    except Exception as exc:
        last_err = repr(exc)
    if time.time() >= deadline:
        print(f"ERROR: timed out after {timeout_s}s waiting for {url}: {last_err}", file=sys.stderr)
        sys.exit(1)
    time.sleep(2 if timeout_s <= 60 else 5)
PY

# 5) Collect provenance & write ready file atomically.
python3 - "$READY_FILE" "$CONFIG" "$LOCAL_MODEL_DIR" "$TEMPLATE_LOCAL" "$VLLM_VENV" "${PI_DIR}/models.json" "$VLLM_PID" "$SKIP_VLLM" "${VLLM_ARGS[@]}" <<'PY'
import glob, hashlib, json, os, pathlib, shutil, subprocess, sys, time, urllib.request

ready_path = pathlib.Path(sys.argv[1])
cfg_path = pathlib.Path(sys.argv[2])
local_model_dir = pathlib.Path(sys.argv[3])
template_local = sys.argv[4]
vllm_venv = pathlib.Path(sys.argv[5])
models_json_path = pathlib.Path(sys.argv[6])
vllm_pid = int(sys.argv[7]) if sys.argv[7] else None
skip_vllm = sys.argv[8] == "1"
vllm_argv = sys.argv[9:]

cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

def run_out(argv):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=15)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None

def sha256_file(p: pathlib.Path) -> str | None:
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

gpu_info = run_out(["nvidia-smi", "--query-gpu=name,memory.total,compute_cap,driver_version", "--format=csv,noheader"])

vllm_py = vllm_venv / "bin" / "python"
vllm_ver = run_out([str(vllm_py), "-c", "import vllm; print(vllm.__version__)"]) if vllm_py.is_file() else None
torch_ver = run_out([str(vllm_py), "-c", "import torch; print(torch.__version__)"]) if vllm_py.is_file() else None
cuda_ver = run_out([str(vllm_py), "-c", "import torch; print(torch.version.cuda)"]) if vllm_py.is_file() else None

safetensors_sha = {}
if not skip_vllm and local_model_dir.is_dir():
    for fp in sorted(local_model_dir.glob("*.safetensors")):
        safetensors_sha[fp.name] = sha256_file(fp)

hf_api_sha = None
if not skip_vllm and "/" in str(cfg.get("model_id", "")) and not pathlib.Path(cfg["model_id"]).is_dir():
    try:
        url = f"https://huggingface.co/api/models/{cfg['model_id']}"
        with urllib.request.urlopen(url, timeout=10) as r:
            hf_api_sha = json.loads(r.read().decode("utf-8", "replace")).get("sha")
    except Exception:
        hf_api_sha = None

pi_exe = shutil.which("pi")
node_exe = shutil.which("node")
oc_exe = shutil.which("opencode")

ready = {
    "schema": "vacant.redo.colab.ready/1",
    "ready_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "gpu": gpu_info,
    "python_version": run_out([sys.executable, "--version"]),
    "node_version": run_out([node_exe, "-v"]) if node_exe else None,
    "pi_version": (run_out([pi_exe, "--version"]) or "").splitlines()[-1] if pi_exe else None,
    "opencode_version": (run_out([oc_exe, "--version"]) or "").splitlines()[-1] if oc_exe else None,
    "vllm_version": vllm_ver,
    "torch_version": torch_ver,
    "cuda_version": cuda_ver,
    "vllm_use_flashinfer_sampler": cfg.get("flashinfer_sampler", 0),
    "model_id": cfg.get("model_id"),
    "model_revision_requested": cfg.get("model_revision"),
    "model_hf_api_sha": hf_api_sha,
    "model_safetensors_sha256": safetensors_sha,
    "chat_template_path": template_local or None,
    "chat_template_sha256": sha256_file(pathlib.Path(template_local)) if template_local else None,
    "served_model_name": cfg.get("served_model_name"),
    "host": cfg.get("host", "127.0.0.1"),
    "port": int(cfg.get("port", 8000)),
    "max_model_len": int(cfg.get("max_model_len", 262144)),
    "max_num_seqs": int(cfg.get("max_num_seqs", 16)),
    "models_json_path": str(models_json_path),
    "models_json_sha256": sha256_file(models_json_path),
    "vllm_pid": vllm_pid,
    "vllm_argv": None if skip_vllm else vllm_argv,
    "skip_vllm": skip_vllm,
}

ready_path.parent.mkdir(parents=True, exist_ok=True)
tmp = ready_path.with_name(ready_path.name + f".tmp.{os.getpid()}")
tmp.write_text(json.dumps(ready, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, ready_path)
PY

log "VM_READY written -> ${READY_FILE}"
echo "VM_SETUP_READY ${READY_FILE}"
