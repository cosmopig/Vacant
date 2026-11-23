# Larger-model R3 replication pilot — frozen protocol

**Question.** Does the research harness's no-hint restart policy improve independently graded completion with a model with more total parameters on original, harder programming tasks? This is a directional replication pilot, **not** a product test of vacant do opencode, a comparison against Gemma, or an estimate of an effect caused by model size alone.

- **Agent/model:** OpenCode 1.18.33, native headless mode in both arms, matching the original CLI version. Local Qwen3-Coder-30B-A3B-Instruct, Q4_K_M GGUF; 30.5B total / 3.3B active according to Qwen. This is a larger parameter count, not a claim that the active compute or accuracy is higher than Gemma's. The hosted Beam Free endpoint allowed a neutral smoke with CLI 1.19.6 but subsequently rate-limited; we selected local Qwen before the first scored request. Sampling uses llama.cpp random request seeds and the frozen server settings. The plan seed controls arm ordering only.
- **Tasks:** eight original synthetic requirements, one pair per task: multigraph connectivity, transactional TTL/LRU, constrained interval optimization, coupon routing, trace span accounting, Unicode edit merging, online rank statistics, and parallel rule closure. Unlike the original bank, these blend domain rules, tie-breaking/state behavior, and adversarial or scale cases. No direct empirical difficulty calibration: the pilot records how hard they were for this agent after the freeze. Do not claim task novelty against model training data.
- **Arms:** A one agent run for up to 900 agent wall seconds; R3 up to three fresh OpenCode processes with fresh workspaces, no hints, up to 300 seconds each and 900 seconds total. Identical compact system prompt, local bash/read tools, task text, starting stub and visible tests in both arms. Caps and tools were chosen using only neutral startup checks, before any scored requests. A process that finishes early is not continued. Evaluate saved work even on agent timeout. Stop R3 at first visible pass; if no attempt visibly passes choose most visible cases passed, latest on ties (existing redo selection). Hidden results are never used to stop or select. Seconds are upper bounds of the subprocess, not equal consumed time, tokens or spend. Grading and void retries are outside the agent budget.
- **Ordering:** redo's fixed seed shuffles tasks and decides within-pair arm order; four concurrent pairs, arms sequential within a pair. CPU contention can affect wall-clock progress. Each active attempt reserves an inference slot. The proxy disables reuse of prompt KV state on the first request and allows reuse on subsequent turns of the same attempt; it records both original and forwarded requests. No changes to tasks, model, grading or caps after the first scored request. Fresh non-root Docker per attempt with only synthetic inputs; no repo, hidden files or host home mounted. The agent and inference services share an internal Docker network with no internet route. Grading containers have no network, get only the candidate file and case input, and never receive expected outputs. Compare parsed JSON outputs literally (except object key order).
- **Outcome:** pair success is delivered solution passing **all** independently held-out cases, one pair per original task. Report completed pairs, voids, paired pass counts, discordance, delta and exact two-sided McNemar (alpha .05, descriptive pilot; six unanimous discordances are needed even for nominal significance). With fewer than all eight scored pairs report an incomplete pilot regardless of p. An unresolved result is not equivalence evidence. Record visible/hidden disagreement, timeout counts, attempts, elapsed time, model HTTP requests (including retries/cancellations), and usage only where returned. No generalization to other models/banks or current product claims.
- **Evidence:** retain plan, version/image/input hashes, UTC timings, prompts, OpenCode JSONL events, raw local inference request/response logs, candidate files, visible/hidden case results and errors including voids. Before scoring, verify a neutral model/tool run and run grader controls: manual examples, disjoint visible/hidden inputs, a visible-fixture stub rejected by the hidden grader, a blank implementation rejected, and hidden-fixture stubs accepted (plumbing controls, not independent correctness proofs). Run data must pass RECORD_SPEC integrity check before reporting metrics.

## Reproduce

Use x86-64 Linux, Docker and Python 3.11+, with at least 30 GiB RAM. From the repository root, with the experiment inputs committed:

```bash
export LAB="$HOME/r3-lab"
mkdir -p "$LAB/wire" tmp
npm install --prefix "$LAB/opencode" opencode-ai@1.18.33
export OPENCODE="$LAB/opencode/node_modules/opencode-linux-x64-baseline/bin/opencode"
export MODEL="$LAB/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"
curl -fL 'https://huggingface.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF/resolve/b17cb02dd882d5b6ab62fc777ad2995f19668350/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf' -o "$MODEL"
export PY_IMG='python@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df'
export LLAMA_IMG='ghcr.io/ggml-org/llama.cpp@sha256:c2cf6c72d913b6c89a5f0929f2a866e6161e09e7dc187e0f3b0f21e923e26db3'
docker pull "$PY_IMG"
docker pull "$LLAMA_IMG"
docker network create --internal hard-r3-inference
docker run -d --name hard-r3-model --network hard-r3-inference --read-only \
  --cap-drop ALL --security-opt no-new-privileges -v "$MODEL:/model/model.gguf:ro" \
  "$LLAMA_IMG" $(python3 ops/redo/hard_r3/run.py server-args)
docker run -d --name hard-r3-trace --network hard-r3-inference --read-only \
  --cap-drop ALL --security-opt no-new-privileges --user "$(id -u):$(id -g)" \
  -v "$PWD/ops/redo/hard_r3/trace_proxy.py:/trace_proxy.py:ro" -v "$LAB/wire:/trace:rw" \
  "$PY_IMG" python -B /trace_proxy.py /trace
# Wait for 'model loaded' in docker logs hard-r3-model. Use a new output directory.
# The runner saves grader preflight outputs before making any scored requests.
python3 ops/redo/hard_r3/run.py run tmp/hard-r3-evidence --opencode "$OPENCODE"
python3 ops/redo/hard_r3/run.py regrade tmp/hard-r3-evidence --verify-output tmp/hard-r3-replay
docker stop hard-r3-trace hard-r3-model
PYTHONPATH=. python3 ops/redo/hard_r3/archive.py tmp/hard-r3-evidence --wire "$LAB/wire" --replay tmp/hard-r3-replay/REPLAY.json
```

Use the audited x86-64 static ripgrep binary (15.2.0 on the Devin Linux image), or pass its path as `--rg`. The runner checks the binary and weight hashes in `run.py`. Repeating inference need not reproduce the same solutions or wall time; offline regrade is deterministic apart from workload-sensitive case timeouts.
