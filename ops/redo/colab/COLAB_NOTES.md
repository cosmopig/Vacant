# Colab GPU Execution Notes for `ops/redo/redo.py`

> **Verification status (honest boundary):** Everything in `ops/redo/colab/` has been tested
> **locally only** (dry-run mode with a trap `colab` binary + local end-to-end test against a
> stdlib `http.server` fake OpenAI-compatible server with real `pi 0.87.1` and `ops/redo/redo.py`).
> **Nothing in this directory has been run on Google Colab yet** (pending user authorization of the
> `colab` CLI).

---

## 1. Architecture & Prior Lessons Carried Forward

The redo harness runs **inside the Colab GPU VM**:

- `vllm serve` binds strictly to `127.0.0.1:8000` inside an isolated `/content/venv-vllm` (Python 3.12 via `uv`, avoiding Colab's preinstalled CUDA/torch mismatch).
- `pi` (pinned to `0.87.1`, matching local `pi --version`) and Node (`v22.23.2`) are installed under `/opt/redo/` and symlinked into `/usr/local/bin/`. `redo.py` itself requires **stdlib Python only**.
- `models.json` is rendered into `~/.pi/agent/models.json` (`chmod 600`) pointing at `http://127.0.0.1:8000/v1` with `contextWindow == max_model_len`.
- Frozen repo code (`git archive <commit>`), task bank tarball, plan JSON, and vLLM config are uploaded once; `vm_run_batch.sh` runs under `setsid nohup`.
- Results are tarred on the VM, downloaded back to `~/dev/ops/redo_runs_colab/<batch>/`, verified (SHA-256 + `tar -tzf`), and only then is `colab stop` invoked.

Lessons reused from `ops/colab_campaign_20260927/` and `ops/colab_dabstep_v37_20261002/`:

1. **`VLLM_USE_FLASHINFER_SAMPLER=0`** — mandatory on `sm_120` (Colab G4 / RTX PRO 6000 Blackwell), where FlashInfer's top-k/top-p sampler misdetects compute capability on vLLM `0.30.0` / flashinfer `0.6.18`.
2. **`--enable-prompt-tokens-details`** — required for vLLM to report `cached_tokens` in usage objects.
3. **Bind `127.0.0.1`** — never expose vLLM on `0.0.0.0`.
4. **Never use `pkill -f` with a pattern that matches your own shell** — vLLM is managed strictly by PID file (`/srv/redo/vllm.pid`).
5. **Status & completion via files + `colab download`** — `colab exec` / interactive consoles can hang or go blank on long runs (causing 1h52m idle GPU burn in `dabstep_v37`). `vm_run_batch.sh` periodically writes `/srv/redo/run/STATUS.txt`, and writes `/srv/redo/run/BATCH_DONE.json` + `/content/redo_results_<batch>.tar.gz` + `.sha256` on completion; `poll_batch.sh` and `fetch_batch.sh` rely on `colab download` by default.
6. **Always pass `-s <session>` explicitly** and validate `--gpu` against `{T4, L4, G4, A100, H100}` (`colab new` silently falls back to `A100` on an unrecognized GPU name).
7. **Never run `colab pay`.**

---

## 2. Exact Commands

### 2.1 Local Offline End-to-End Test (run anytime, no Colab auth required)

```bash
python3 ops/redo/colab/test_local_e2e.py
```

Proves:
- `--dry-run` works on every script (`render_models.py`, `vm_setup.sh`, `vm_run_batch.sh`, `launch_batch.sh`, `poll_batch.sh`, `fetch_batch.sh`) and never executes `colab`.
- Rendered `models.json` works with real `pi -p` against a local stdlib fake OpenAI-compatible server (`reasoning_effort: "none"` sent, reply received).
- `vm_run_batch.sh` + `vm_setup.sh` runs a 1-pair `redo.py` smoke plan (`A` + `R3`) end-to-end in a temp dir and produces a verified `results.tar.gz`.

### 2.2 Authorize `colab` CLI (human step, once)

Preferred headless auth (`adc`, default):

```bash
gcloud auth application-default login \
  --scopes=openid,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/colaboratory
colab sessions
```

Or browser OAuth2:

```bash
colab --auth=oauth2 sessions
```

Check remaining compute units (read-only; never run `colab pay`):

```bash
colab usage
```

### 2.3 Dry-Run a Real Plan Before Launching

```bash
bash ops/redo/colab/launch_batch.sh \
  ops/redo/plans/<your_colab_plan>.json \
  ~/dev/ops/ref/bm_tasks/<bank> \
  --gpu G4 \
  --vllm-config ops/redo/colab/vllm_gemma4_12b.json \
  --dry-run
```

### 2.4 Launch a Preregistered Batch (one command)

First commit your preregistered plan JSON (with `providers` pointing to `colab-vllm-nothink` or `colab-vllm-think`, `health_url: "http://127.0.0.1:8000/v1/models"`, and `health_contains: "<served_model_name>"`).

```bash
bash ops/redo/colab/launch_batch.sh \
  ops/redo/plans/<your_colab_plan>.json \
  ~/dev/ops/ref/bm_tasks/<bank> \
  --gpu G4 \
  --commit HEAD \
  --vllm-config ops/redo/colab/vllm_gemma4_12b.json
```

Outputs a local state file at `~/dev/ops/redo_runs_colab/<batch>/state.json`.

Options of note:
- `--high-mem` if you need high-RAM shape (e.g. `A100-80GB`).
- `--transport exec` if `colab ssh` is unavailable (no SSH key or server 429).
- `--vllm-config ops/redo/colab/vllm_qwen3_27b.json` for Qwen (edit `model_id`, `model_revision`, `served_model_name`, `max_model_len`, `tool_call_parser`, `reasoning_parser` first and commit).
- `--allow-uncommitted-plan` for temporary smoke tests only (never for preregistered batches).

### 2.5 Poll Progress (file-based via `colab download`)

```bash
bash ops/redo/colab/poll_batch.sh ~/dev/ops/redo_runs_colab/<batch>/state.json
```

Add `--live-status` to run `redo.py status` live via `ssh`/`exec` instead of waiting for the 60s `STATUS.txt` snapshot. Add `--tail 100` for more `runner.log` lines.

### 2.6 Fetch, Verify Tarball, and Stop VM

Once `poll_batch.sh` reports `DONE : YES`:

```bash
bash ops/redo/colab/fetch_batch.sh ~/dev/ops/redo_runs_colab/<batch>/state.json
```

This downloads `results.tar.gz` and `results.tar.gz.sha256`, verifies the SHA-256 against both `.sha256` and `BATCH_DONE.json`, checks `RUN.json` inside the archive, extracts to `~/dev/ops/redo_runs_colab/<batch>/run/`, and **only after verification passes** executes `colab stop -s <session>`.

- Pass `--no-stop` to keep the VM alive after verified download.
- Pass `--force` to snapshot and download an in-progress run (runs `tar` on the VM via `ssh`/`exec` first).

### 2.7 Optional Kernel Keepalive (Long Batches > 25 min)

Prior campaign `RUNLOG.md` (`ops/colab_dabstep_v37_20261002/RUNLOG.md`) observed Colab reclaiming VMs after ~25–30 minutes of Jupyter kernel inactivity even when background `setsid` processes were busy. If running multi-hour batches, you can periodically touch the kernel from another terminal or check `colab status -s <session>`, and always inspect `colab sessions` so no VM runs unattended.

---

## 3. Experimental Conditions Required in Every Preregistration

A Colab batch is a **different experimental condition** from local LM Studio / llama.cpp runs (different inference engine, different quantization format such as compressed-tensors W4A16 vs GGUF Q4_0, different KV/attention kernels). **Never pool Colab counts with local LM Studio counts into a single p-value.**

Every preregistered plan JSON (and `VM_READY.json` archived inside `results.tar.gz`) must fix and record:

| Condition | Where fixed before launch | Where verified at runtime (`VM_READY.json` / `launch_meta.json`) |
|---|---|---|
| **Backend & vLLM version** | `vllm_config.json` (`vllm_version`, `flashinfer_sampler`, `enable_prefix_caching`, `enable_prompt_tokens_details`, `async_scheduling`, `tool_call_parser`, `reasoning_parser`) | `vllm_version`, `torch_version`, `cuda_version`, `vllm_use_flashinfer_sampler`, `vllm_argv` |
| **GPU type & machine shape** | `launch_batch.sh --gpu <GPU> [--high-mem]` | `gpu` (`nvidia-smi` name, total VRAM, compute cap, driver version), `launch_meta.json` |
| **Model weights identity** | `vllm_config.json` (`model_id`, `model_revision`, `served_model_name`, `chat_template_url`) | `model_id`, `model_hf_api_sha`, `model_safetensors_sha256`, `chat_template_sha256` |
| **Concurrency** | `vllm_config.json` (`max_num_seqs`) AND `plan.json` (`providers[].jobs`) | `max_num_seqs` in `VM_READY.json`, `plan.providers[].jobs` in `RUN.json` |
| **Context & output limits** | `vllm_config.json` (`max_model_len`, `max_tokens`) | `max_model_len`, rendered `models.json` (`contextWindow == max_model_len`, `maxTokens`) |
| **Reasoning / thinking mode** | `plan.json` (`providers[].provider`: `colab-vllm-nothink` vs `colab-vllm-think`) and `vllm_config.json` (`reasoning`) | `models.json` (`models_json_sha256`), `vllm_argv` (`--reasoning-parser`) |
| **Agent & harness versions** | `vllm_config.json` (`pi_version`, `node_version`, optional `opencode_version`) and `launch_batch.sh --commit <sha>` | `pi_version`, `node_version`, `git_commit` in `launch_meta.json`, `harness_sha256` in every `cell.json` |

For `gemma4` on vLLM `0.30.0`, keep the prior campaign flags:
- `--tool-call-parser gemma4 --reasoning-parser gemma4`
- `--chat-template <pinned tool_chat_template_gemma4.jinja>`
- `--limit-mm-per-prompt '{"image": 0, "audio": 0}'`

For `qwen` (e.g. `vllm_qwen3_27b.json`), verify `--tool-call-parser` (`hermes` or model-specific parser) and `--reasoning-parser` (`qwen3`) with a 1-pair smoke batch before preregistering a full run — Qwen flags have **not** yet been tested on Colab in this repo.

---

## 4. How Infrastructure Failures Map to `infra_void`

`ops/redo/redo.py` separates infrastructure failures from model/agent failures independently of pass/fail:

1. **Per-attempt `void` detection (`redo.py:589-600`):** An attempt is discarded as `void` (does NOT consume one of the arm's attempts) if any of:
   - `spawn_error`: agent binary failed to launch (`pi` missing / OSError).
   - `model_died_mid_run`: `usage.final_error` matches `infra_re` (e.g., `Connection error`, `ECONNREFUSED`, `ECONNRESET`, `fetch failed`, `socket hang up`, `Premature close`, `502/503/504`, `model crashed/unloaded`), even if workspace already changed.
   - `no_model_calls`: workspace did not change AND `usage.calls == 0` (e.g., vLLM unreachable when `pi` started — `pi` exits 0 with `stopReason="error"` and 0 usage).
   - `infra_marker`: workspace did not change AND last 20 KB of `agent.log` matches `infra_re`.
2. **Retry & escalation to `infra_void` (`redo.py:641-661`):**
   - Before each attempt, `redo.py` calls `health_wait` on `providers[].health_url` (e.g., `http://127.0.0.1:8000/v1/models`, default wait 900s). If it times out, the cell is marked `infra_void = "endpoint_down"`.
   - Each `void` attempt is archived under `void_<n>_attempt_<k>/` and retried up to `VOID_RETRIES = 4` times with backoff `(30, 60, 120, 240)` seconds.
   - After 4 voids, the cell gets `infra_void = "void×4:<reason>"`.
   - If the grader crashes/fails to emit JSON with `"pass"`, `infra_void = "grader_failed"`.
3. **Accounting (`redo.py:876-884`):**
   - Any cell with `infra_void != None` is excluded from its arm's scored denominator.
   - If **either** arm in a `(task, rep)` pair is `infra_void`, the **entire pair** is excluded from McNemar and listed under `pairs_infra_void` in `REPORT.json`.
4. **What is NOT `infra_void`:**
   - Model/agent errors that are not connection/50x failures — e.g. `400 context length exceeded` — count as normal attempts and enter the denominator, while being surfaced in `REPORT.md` under `final_errors_counted_as_attempts`. (Avoid spurious context-length errors by keeping `models.json` `contextWindow == vLLM max_model_len`.)
5. **Colab-specific failure modes:**
   - **VM preemption / kernel timeout:** `redo.py` dies mid-batch. Completed cells (`cell.json` present) remain intact if recovered; incomplete cells have no `cell.json` and are redone cleanly on resume. If the VM is lost before `fetch_batch.sh`, any un-downloaded cells on VM disk are lost (use `fetch_batch.sh --force --no-stop` periodically for multi-hour batches if you want intermediate local checkpoints).
   - **vLLM OOM / crash:** manifests as `Connection refused` -> `endpoint_down` or `void×4:no_model_calls` -> `infra_void`. Lower `max_num_seqs` / `providers[].jobs` or `max_model_len`, commit a new plan, and start a fresh run root.

---

## 5. Stopping Sessions & Avoiding Idle GPU Burn

**Idle Colab GPU VMs continuously burn compute units (~8.90 CU/h on G4, ~5.30–6.77 CU/h on A100).**

1. **Normal shutdown:** `fetch_batch.sh <state.json>` automatically runs `colab stop -s <session>` immediately after verifying the downloaded tarball SHA-256 and contents.
2. **Manual / emergency stop:**
   ```bash
   colab stop -s <session>
   ```
   (Look up `<session>` in `~/dev/ops/redo_runs_colab/<batch>/state.json` or via `colab sessions`.)
3. **Audit for leaked / orphan VMs:**
   ```bash
   colab sessions
   colab usage
   ```
   Any unexpected session shown by `colab sessions` should be stopped immediately with `colab stop -s <name>`.
4. **Optional CU balance guard:** You can adapt `ops/colab_campaign_20260927/cu_guard.sh` to watch `colab usage` and stop if remaining balance drops below your floor. **Never run `colab pay`.**
