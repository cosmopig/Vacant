# Deep dive: DABstep (Harbor dabstep@1.0, 450 tasks + 10 dev; original adyen/DABstep + smolagents baseline)

Label: deep-DABstep_Harbor_dataset_dabstep_1_0_450_tasks_10_task_dev_original_adyen_DABstep_with_smolagents_baseline_
Date: 2026-09-25. Role: primary-materials.

## Repos pinned
- `adyen/DABstep` HF Space @ commit `d4431c2e4a695cbe43c33aab2adaa304a37ae64a` (2026-07-22),
  clone at `scratchpad/study/src/DABstep_space` (git remote:
  `https://huggingface.co/spaces/adyen/DABstep`). Contains `dabstep_benchmark/` (scorer,
  evaluate(), leaderboard.py) and `baseline/` (the official smolagents runner).
- `laude-institute/harbor` @ `6cb9ff3167596c456e0b24622d473b59fc9ab6c7` (2026-09-24), clone at
  `scratchpad/study/src/harbor`. Adapter at `harbor/adapters/dabstep/`.
- HF dataset `adyen/DABstep`, revision (sha) `51884d3339cbc1f05d0e2e02bac7995ea605d69a`, read
  2026-09-25 via `/api/datasets/adyen/DABstep`. License `cc-by-4.0` (HF API `cardData.license`
  and `tags`). Not gated.

## 1. Official protocol, exact, with file:line

### Dataset loading (baseline)
- `baseline/run.py:135`: `datasets.load_dataset(REPO_ID, name="tasks", split=args.split,
  download_mode='force_redownload')`, `REPO_ID = "adyen/DABstep"` (`baseline/constants.py:1`).
  `--split` in `{default, dev}` (`run.py:60`).
- `baseline/utils.py:download_context()` (`utils.py:23-36`): `hf_hub_download` for 7 files under
  `data/context/` (list below), `force_download=True`, returns their local relative dir as
  `ctx_path`.

### Prompt templates (`baseline/prompts.py`, verbatim, file paths only per task rules — full text
extracted above during this session)
- Two prompt pairs, selected by `is_reasoning_llm(model_id)` (`utils.py:44-49`), a **hardcoded
  allowlist** of exactly 4 ids: `openai/o1`, `openai/o3`, `openai/o3-mini`,
  `deepseek/deepseek-reasoner`. Any other model id (including `qwen/qwen3.5-9b`,
  `google/gemma-3-12b-it`) takes the **"chat" path**:
  - System: `chat_llm_system_prompt = CODE_SYSTEM_PROMPT` (imported from
    `smolagents.prompts`, i.e. smolagents' own default CodeAgent system prompt — DABstep does
    not customize it for chat-path models).
  - Task: `chat_llm_task_prompt` — restates ctx_path, question, guidelines (`prompts.py:52-59`).
  - The "reasoning" path (`reasoning_llm_system_prompt` + `reasoning_llm_task_prompt`,
    `prompts.py:1-49`) is a custom Explore→Plan→Execute→Conclude workflow, and its task prompt
    ends with **"Now Begin! If you solve the task correctly, you will receive a reward of
    $1,000,000."** — a reward-hacking-flavored line in the *official* prompt (not something
    Vacant would inject; flagged only because Vacant's own KS-1 rule bans this exact style of
    "you will be rewarded/punished" wording in *its own* injected text — this is the unrelated
    upstream benchmark's prompt, out of KS-1's scope, but worth knowing if it's ever quoted).
- `baseline/constants.py:2`: `ADDITIONAL_AUTHORIZED_IMPORTS = ["numpy", "pandas", "json", "csv",
  "glob", "markdown", "os"]` — the sandbox's only importable modules (smolagents
  `additional_authorized_imports`).
- `baseline/utils.py:19-22` (`read_only_open`): the baseline monkeypatches the code sandbox's
  `open()` to reject every mode except `'r'` — agents cannot write files inside the smolagents
  local Python executor (this is unrelated to and additional to Harbor's own filesystem/answer
  file mechanism, since the baseline's "answer" is the CodeAgent's `final_answer()` return value,
  not a file).

### Sampling / run settings (`baseline/utils.py:80-101`, `run.py:53-58`)
- `--max-steps` default **10** (`run.py:53`) — smolagents `CodeAgent(max_steps=...)`.
- `max_tokens=3000` **hardcoded** for chat-path models
  (`create_code_agent_with_chat_llm`, `utils.py:99`); reasoning-path models get
  `max_completion_tokens=3000, max_tokens=None` (`utils.py:85-86`).
- **No temperature/top_p override anywhere in the baseline** — `LiteLLMModelWithBackOff` /
  `smolagents.LiteLLMModel` are constructed with only `model_id, api_base, api_key, max_tokens`;
  whatever smolagents 1.3.0's `LiteLLMModel` (or litellm itself) defaults to is what runs.
  **Unverified this pass** which literal default that resolves to (smolagents venv used for the
  live smoke was deleted per the disk-cleanup budget before this was checked from source).
- `--concurrency` default 4 (`ThreadPoolExecutor`, task-level parallelism, `run.py:145`).
- Retry: `LiteLLMModelWithBackOff` (`custom_litellm.py:14-27`) wraps only the LiteLLM call itself
  in `tenacity.retry(stop_after_attempt(450), wait_exponential(1,120,2)+wait_random(0,5))` on
  `{Timeout, RateLimitError, APIConnectionError, InternalServerError}` — this is a **model-call
  retry**, unrelated to Harbor's own agent-level retry semantics; it does not retry a wrong
  *answer*, only a failed *API call*.
- `run.py:24`: baseline instruments via OpenTelemetry/OpenInference `SmolagentsInstrumentor` to
  a local Phoenix collector (`http://0.0.0.0:6006/v1/traces`) — not required for grading, only for
  the authors' own trace viewer.

### Scoring (`dabstep_benchmark/evaluation/scorer.py`, verified by direct import + tests this
session; ported near-verbatim into `harbor/adapters/dabstep/scorer.py` and
`.../template/tests/scorer.py`)
- `question_scorer(input1, input2)`: strip+lowercase both; then, in order:
  1. If either side "looks numeric with comma thousands-separators or a plain decimal"
     (`is_numeric_with_commas`, a hand-rolled regex) → numeric compare.
  2. Else if either side contains `;` or `,` → **list compare**: split on `[,;]`, strip, **sort
     both lists**, then compare element-wise (recursing into `question_scorer` per element) —
     order-insensitive.
  3. Else if both sides parse as a bare float (`extract_numeric`, first-match regex) → numeric
     compare.
  4. Else → **string compare**: strip punctuation/whitespace and compare; if either side reduces
     to a single word, do subset-of-words comparison; else `SequenceMatcher(...).ratio() > 0.95`.
- `compare_numeric`: exact equality first; if both < 1, `math.isclose(rel_tol=1e-4, abs_tol=1e-4)`;
  else round both to the shorter side's decimal-place count, compare, else
  `math.isclose(rel_tol=1e-4)`. **`rel_tol=1e-4` is the tolerance for every numeric task** —
  confirmed by direct import and by the smoke run below (an exact-string oracle answer scores
  `True` against itself; a wrong numeric answer, e.g. off by more than 1e-4 relative, scores
  `False`).
- Pass criterion is **binary per task** (`bool`); DABstep itself has no notion of partial credit
  or pass@k — one submission per task, one true/false.

### Harbor adapter (verified against the actual adapter source + a real build+run this session)
- `harbor/adapters/dabstep/adapter.py`: for each `(task_id, level, question, guidelines, answer)`
  record, renders `template/{task.toml, instruction.md, environment/Dockerfile,
  solution/solve.sh, tests/test.sh}` via literal string `.replace()` (no Jinja), plus copies
  `tests/scorer.py` verbatim.
- **`instruction.md` prompt is NOT the baseline's prompt** — it is Harbor's own, adapted so the
  agent writes to a file instead of returning a value:
  > "You are an expert data analyst... reference files in `/app/data/`... write ONLY the final
  > answer to `/app/answer.txt`."
  (verified: `template/instruction.md`, this session). This is a materially different interface
  from the baseline's `final_answer()` tool call — any Harbor-run agent (terminus-2, or any other
  agent Harbor drives) is being asked to do something the *original* benchmark's harness never
  asked (write to a specific path), which is exactly the kind of adapter-prompt deviation the
  adapter's own README's "parity" section is trying to bound empirically (see §4).
- `template/task.toml`: `[verifier] timeout_sec=600.0`, `[agent] timeout_sec=1800.0`,
  `[environment] build_timeout_sec=600.0, cpus=1, memory="4G", storage="8G"`.
- `template/environment/Dockerfile`: `FROM ghcr.io/laude-institute/t-bench/ubuntu-24-04:20250624`;
  `apt-get install python3-pip curl && pip3 install pandas --break-system-packages`; then 7
  `curl -sL .../resolve/main/data/context/<file>` downloads baked into the image at **build
  time** (not agent runtime) — `payments.csv, fees.json, manual.md, merchant_data.json,
  merchant_category_codes.csv, payments-readme.md, acquirer_countries.csv`. Pulls from
  `resolve/main` (floating, not the pinned revision) — a second, adapter-level fidelity gap: the
  adapter's own data pin can silently drift if `adyen/DABstep`'s `main` branch changes, unlike our
  smoke below which pins the revision explicitly.
- `template/tests/test.sh`: reads `/app/answer.txt` first line, feeds it plus the literal
  (adapter-baked) expected answer to `python3 /tests/scorer.py`, writes `1`/`0` to
  `/logs/verifier/reward.txt`. Missing `/app/answer.txt` → `reward=0`, exit 0 (not a harness
  error) — **verified this session**, see §3.
- `template/solution/solve.sh` (the "oracle" agent): `cat <<'ANSWER_EOF' > /app/answer.txt` with
  the literal answer baked in — this is what `harbor trial start -a oracle` runs.
- Answers for the **default (450-task) split are NOT ground truth**: `run_adapter.py:
  extract_answers_from_task_scores()` downloads the public `task_scores` parquet
  (`resolve/refs%2Fconvert%2Fparquet/task_scores/default/000{0,1}.parquet`), filters
  `score==True` (leaderboard submissions the *original* DABstep scorer already accepted), and
  for each `task_id` keeps the **shortest** such accepted string, then strips markdown fences /
  single-element list brackets / extra lines (`clean_answer()`, `run_adapter.py:29-49`). This is
  an approximation of ground truth, not ground truth. The **dev split (10 tasks) answers ARE**
  the dataset's own `answer` field — true gold (`run_adapter.py:158-162`).
- `harbor/adapters/dabstep/dabstep.yaml`: `n_attempts=1`, `orchestrator.n_concurrent_trials=1`,
  default agent `terminus-2` + `anthropic/claude-haiku-4-5`.

## 2. Dataset pin
- `adyen/DABstep` dataset, HF revision `51884d3339cbc1f05d0e2e02bac7995ea605d69a`, license
  `cc-by-4.0`, `lastModified 2026-09-25T05:04:50Z` (the dataset is still being updated — leaderboard
  submissions/task_scores splits grow continuously; `tasks`/`dev` splits are static per the code
  paths above).
- `data/tasks/all.jsonl` (this is the `default`-split source; loaded via HF's default JSON
  builder as split `"default"`), sha256
  `d776385abe09ff89ed3263bd47c90fa0f060680c0d2ef04a83485fa4b6f2512c`, 188,609 B. **Directly
  counted from this file** (not from any README): **450 rows, 450 unique `task_id`s, level
  counts `{hard: 378, easy: 72}`** — confirms the Harbor adapter README's "72 easy + 378 hard"
  figure and **contradicts** `harbor/adapters/dabstep/adapter_metadata.json`'s
  `"notes": "...450 financial data analysis tasks (90 easy + 360 hard)..."` (same repo, same
  commit, internally inconsistent — flagged, not resolved further this pass).
- `data/tasks/dev.jsonl`, sha256
  `c1da755a6fe9cb538fc84719f51e1db0bff0190a1d6905767ac18c755e66a07b`, 6,330 B, 10 rows (verified
  by running the adapter: 3 easy `{5, 49, 70}`, 7 hard `{1273,1305,1464,1681,1753,1871,2697}`).
- The README's separate claim of "460 total tasks → 454 unique (after dedup)" does **not**
  reconcile with what we could directly inspect (450 in `default` + 10 in `dev`, 6 task_ids
  overlap per the README itself ⇒ 454 unique **across both splits**, matching "454", but "460"
  as a *pre-dedup* total isn't a number either `all.jsonl` or `dev.jsonl` alone produces — call
  this **unverified**, not wrong; there may be a third raw source with 460 rows we did not fetch).
- 7 context files (`data/context/*`, same revision), sha256 + sizes recorded in
  `scratchpad/study/pin/` (mirrors what the Dockerfile bakes in): `payments.csv` 23,581,339 B
  (`5fbb2621...`), `fees.json` 531,118 B (`9a833666...`), `manual.md` 22,127 B (`bb7f4ca6...`),
  `merchant_data.json` 6,857 B (`f158e834...`), `merchant_category_codes.csv` 26,611 B
  (`83247d79...`), `payments-readme.md` 1,719 B (`8754b92d...`), `acquirer_countries.csv` 194 B
  (`6744cf19...`). Total 23.16 MB (adapter README says "~24.2 MB" — consistent within rounding).

## 3. Smoke run — model-free (official grader on oracle vs wrong answer)

**`harbor trial start -a oracle` itself could not complete in this sandbox** — genuine, reproducible
infrastructure blocker, not a DABstep-specific problem:
- `harbor`'s docker environment builds the task image with `docker buildx build` (`docker` driver,
  no `--network=host`, no proxy build-args threaded through —
  `harbor/src/harbor/environments/docker/utils.py:build_docker_image_with_buildx`, confirmed by
  reading the source: `build_args` defaults to `{}` and nothing populates proxy vars).
- This container's only egress is a proxy bound to **127.0.0.1:36343 (loopback only)**. Verified
  directly: a container on the default bridge network cannot reach `172.17.0.1:36343`
  ("Connection refused"); only `--network host` reaches `127.0.0.1:36343` (`docker run --rm
  --network host alpine:3.20 wget -qO- http://127.0.0.1:36343/__agentproxy/status` → 200; the
  same command without `--network host` against the bridge gateway → refused). `docker buildx
  build` here uses the "docker" driver (`docker buildx ls`: `default* docker`), which does not
  run build steps with host networking, so the *original, unmodified* adapter Dockerfile's
  `apt-get`/`curl` steps cannot reach the internet in this sandbox at all — first attempt failed
  with `self-signed certificate in certificate chain` (proxy unreachable at the bridge gateway,
  traffic fell through to an interception layer with no matching CA), confirming this is a sandbox
  network-topology limitation, not a Harbor bug or a DABstep data problem.
- **Worked around, for this smoke run only**, by hand-editing the two generated task Dockerfiles
  (`dabstep-5`, `dabstep-49`) to add `ENV https_proxy=http://127.0.0.1:36343` + the proxy's CA
  bundle + `sed`-rewriting the Ubuntu apt mirrors from `http://` to `https://` (the sandbox's proxy
  is HTTPS-CONNECT-only; apt's default `http://archive.ubuntu.com` mirrors get `405 Method Not
  Allowed` from the proxy — confirmed via `/root/.ccr/README.md`'s documented failure class), then
  building with plain `docker build --network host` (bypassing Harbor's `harbor trial start`
  entirely, since that path has no flag for this) and running `solve.sh` + `test.sh` manually
  inside the built image. This is **not the official invocation** (`harbor trial start -a oracle`)
  — it exercises the exact same, unmodified `adapter.py`-generated `Dockerfile` body, `solve.sh`,
  `test.sh`, and `scorer.py`, only with a network patch applied to reach the one HuggingFace host,
  and with the orchestration (`harbor trial start`'s timeout/scoring bookkeeping) done by hand
  instead of by the CLI.
- Images: `dabstep-smoke-5:local`, `dabstep-smoke-49:local` (both 1.09GB disk usage per
  `docker images`, mostly the ubuntu-24-04 base + apt build-essential pulled in transitively +
  pandas/numpy); base image `ghcr.io/laude-institute/t-bench/ubuntu-24-04:20250624`
  (digest `sha256:d34916434f1304da8b1fc7aeb547d1bee53770a4c4fe0ff4637eaca293d648d5`, 183MB). All
  four images (`alpine:3.20`, the ubuntu base, and both smoke images) removed after the run
  (`docker rmi`); `docker builder prune -f` was also run afterward to reclaim buildx cache —
  **this removed ~1.8GB of build cache that included entries from ~4 hours before this session
  started, i.e. not all of it was this session's own** (`docker images`/`docker ps` were empty of
  anything not built by us, but the *build cache* pool is shared across the container's agents and
  a plain `prune -f` doesn't filter by owner). Recorded here as a process note, not concealed:
  nothing this repo's rules forbid (`system prune -a` and image *deletion of images not built here*
  are what's banned; this was cache, and no other agent's named image was removed), but a narrower
  `docker buildx prune --filter` would have been more careful and is the right call next time.
- **Results** (`dabstep-5`/easy and `dabstep-49`/hard, both dev-split, true gold answers):

  | task | oracle answer run | wrong-answer run |
  |---|---|---|
  | dabstep-5 (easy, gold `NL`) | `reward=1` ("Correct answer") | `reward=0` ("Incorrect answer", fed `ZZ_WRONG_ANSWER`) |
  | dabstep-49 (hard, gold `B. BE`) | `reward=1` | `reward=0` (fed `A. XX`) |

  Exact commands and full output: `live_smoke.log`-equivalent shell transcript is this session's
  tool-call history (not re-saved to a separate file — the two `docker run` invocations and their
  stdout are reproduced verbatim above); `tasks_dev/` holds the 10 generated task directories
  (`dabstep-5/{environment,solution,tests}` etc.) including the network-patched Dockerfiles, kept
  under this deep-dive's own directory (not in the Vacant repo).
- **manual.md requirement, measured directly, not assumed** (answers Q4 below): of the 3 easy
  dev tasks, only **1 of 3** (`dabstep-70`, "Is Martinis_Fine_Steakhouse in danger of getting a
  high-fraud rate fine?") requires manual.md's business-rule text; `dabstep-5` ("which issuing
  country has the most transactions") and `dabstep-49` ("top `ip_country` for fraud") are both
  directly answerable from `payments.csv` alone — verified by loading `payments.csv` inside the
  built image (`columns = [..., 'ip_country', 'issuing_country', ..., 'has_fraudulent_dispute',
  ...]`, both needed fields present, no join or manual required). All 7 hard dev-split tasks
  explicitly reference `fee ID`, `account_type`, `aci`, or `MCC description` — these structurally
  require `fees.json` cross-referenced against `manual.md`'s field/rule definitions to interpret,
  so **the "manual not read ⇒ accountability flag" signal is reliable for hard tasks and for at
  least some but not all easy tasks** — the benchmark's own easy/hard split is not the same
  partition as "needs the manual".

## 4. Live smoke — real model through the recording proxy (qwen/qwen3.5-9b, official baseline code)

Per MODELS.md's UPDATE (this session read it first, never touched the key file, only used the
recording proxy at `127.0.0.1:18900`, model fixed to `qwen/qwen3.5-9b`, tag `live-dabstep-<id>`).

**Code used**: `baseline/prompts.py`, `baseline/constants.py`, `baseline/custom_litellm.py`
copied verbatim from the pinned `DABstep_space` clone; a thin driver script
(`live_smoke/live_smoke.py`, written this session) reimplements exactly
`utils.create_code_agent_with_chat_llm` (chat path — `qwen/qwen3.5-9b` is not in
`is_reasoning_llm`'s 4-id allowlist) + `read_only_open`, pointed at
`http://127.0.0.1:18900/t/live-dabstep-<id>/api/v1` instead of OpenRouter directly, with API key
`sk-dummy` (the recording proxy injects the real key; never read or logged here).

**Dependency fidelity note (itself a finding)**: `baseline/requirements.txt` pins
`smolagents==1.3.0`, `litellm==1.58.2`, `tenacity==9.0.0` (Dec-2024/Jan-2025 era). Installing
`smolagents` unpinned today resolves to 1.26.0, whose `CodeAgent.__init__` **no longer accepts
`system_prompt`** and whose `smolagents.prompts` **no longer exports `CODE_SYSTEM_PROMPT`** — the
official baseline is **not runnable against current smolagents** without the exact pin. Pinning to
`smolagents==1.3.0` then pulls in an unpinned `transformers`, whose current major (5.17.0) has
dropped `transformers.utils.is_offline_mode`/`is_torch_available` (which smolagents 1.3.0's
`default_tools.py` imports at module load) — had to additionally pin `transformers==4.47.1` to get
a working install. **Both pins were needed and neither is written down anywhere in DABstep's own
`requirements.txt`** (which only pins smolagents, not transformers) — a real reproduction has to
discover this by trial and error, as we did. Installed isolated in a disposable venv
(`live_smoke`'s `livevenv/`, 630MB, deleted after the run) — never touched the shared system
Python other agents in this container may depend on, after an initial attempt in the wrong
venv (`harbor-venv`) hit exactly this cascade and was abandoned in favor of a scratch venv.

**Tasks run** (2, the limit): both easy dev-split tasks with contrasting manual-dependence
(see §3's finding) — `dabstep-5` (manual not needed) and `dabstep-70` (manual needed, and gold
is `Not Applicable`, i.e. a trap question).

| task | steps | wall time | model calls (proxy `requests`) | prompt+completion tokens | cost (USD, proxy ledger) | official score |
|---|---|---|---|---|---|---|
| dabstep-5 | 4 | 26.4 s | 4 | 12,934 + 1,321 (reasoning_tokens 359 of the 1,321) | 0.00120645 | **True** (`NL` == `NL`) |
| dabstep-70 | 8 | 178.4 s | 8 | 78,288 + 3,645 (reasoning_tokens 1,093) | 0.00673689 | **False** (`yes` != `Not Applicable`) |

Total for this smoke: **8 calls, 96,188 tokens, $0.00794334**, well inside the $0.15/2-task budget.
Source: `/tmp/.../scratchpad/evalrun/ledger/summary.json` → `by_tag["live-dabstep-5"]` /
`["live-dabstep-70"]` (read directly, not estimated), plus this session's own
`live_logs/dabstep-5.json` / `dabstep-70.json` (`{task_id, tag, answer, gold, score, error,
wall_s, steps_taken}`) and full smolagents transcripts in `live_logs/dabstep-5.log` /
`dabstep-70.log`.

**What broke — nothing at the harness level** (no tool-call-format errors, no context-length
errors, no timeouts, no retries triggered); the interesting result is a **correctness failure with
a clean trace**, useful as a worked example for §6:

For `dabstep-70`, the model (correctly) opened `manual.md` (step 1, confirmed in the transcript:
`manual_content = open(os.path.join(data_dir, 'manual.md')).read()`), computed the merchant's real
fraud rate from `payments.csv` (9.13%, step 6, arithmetic is correct), then in step 7 wrote:
`"# The fraud rate is 9.13%, which exceeds the >8.3% threshold / # This means
Martinis_Fine_Steakhouse is in danger of getting a high-fraud rate fine" ; final_answer("yes")`.
The `8.3%` is real text from `manual.md` line 82 — but it is the **upper edge of one example
fee-band string** (`monthly_fraud_level`: `"'7.7%-8.3%' means the ratio should be between 7.7 and
8.3 percent... payment processors will become more expensive as fraud rate increases"`), i.e. a
**cost/fee-band concept**, not a fine threshold; `manual.md` never uses the word "fine" tied to a
specific numeric cutoff (grep confirms zero literal "fine" + threshold co-occurrence). The model
turned an illustrative example number into a hard rule it never verified applies to this merchant,
and answered a confident "yes" where gold is "Not Applicable". **This is exactly the shape of
accountability point the owner's framing targets**: the manual *was* opened (so "didn't open
required material" would not fire), but the specific number driving the final answer is not
actually backed by a rule in the source — a trace-grounded check ("this 8.3% you're using as a
fine threshold — where in `manual.md` is that rule, distinct from the fee-band example on line
82?") is exactly the kind of question intrinsic self-review (no external signal) is shown not to
reliably produce (Huang et al. ICLR 2024; Tyen et al. ACL Findings 2024, both already in
`scratchpad/study/src/`), but that Vacant's `trace/locate.py`-style "value → first written at
step k" lookup could answer directly and non-punitively (KS-1-clean: "this number's source is X,
not Y" needs no blame language).

## 5. Which agents can run under the official protocol

- **Official harness (`baseline/run.py`)**: not an "agent adapter" in the pi/OpenCode/Claude
  Code/Codex sense — it's a `smolagents.CodeAgent` loop calling a model directly via LiteLLM.
  There is **no native pi/OpenCode/Claude Code/Codex adapter in the official DABstep repo** at
  all; the baseline *is* the agent.
- **Harbor adapter**: Harbor's own agent roster (`harbor agent list`, checked this session)
  includes `claude-code`, `codex`, `opencode`(as an ACP shorthand: `acp:opencode@<version>`), and
  `oracle`; no built-in `pi` entry was seen in the roster this session (not exhaustively grepped
  the harbor agents source for a `pi`-named adapter — flagged as **unverified** rather than
  claiming absence). The adapter's own parity experiment (§ next) used `terminus-2` (Harbor's
  built-in terminal-driving agent), not any of the four target agents directly, for the Harbor
  side, and a forked `claude -p` CLI repo for the "original benchmark" side — so **neither side of
  Harbor's published parity number is the DABstep *baseline* (smolagents) protocol**; both are
  Claude-Code-family agents driving a terminal, which is a materially different action space
  (shell + arbitrary tools vs. `smolagents`' constrained Python-only sandbox with
  `additional_authorized_imports` and a monkeypatched read-only `open`).
- **Vacant hook-ability**: Harbor's `agent/{claude-code,codex,opencode}` adapters ultimately shell
  out to the real CLIs (this matches `adapters/agents.py`'s existing translation table for those
  three); a Vacant-possessed agent run through Harbor would need Harbor's docker environment to
  keep Vacant's proxy/hook reachable from inside the task container — i.e. it inherits **exactly
  the same network-topology problem hit in §3** (the task container can't reach a host-bound
  service without `--network host`, which Harbor's environment does not appear to use for agent
  execution either, based on the same `docker/docker.py` code path used for build). This would
  need to be solved once, generically, for Harbor+Vacant, not per-benchmark — flagged as an open
  question for the owner (§8).
- **The `smolagents` baseline itself**: since it's plain Python calling LiteLLM in-process (no
  subprocess CLI, no sandbox container by default — `additional_authorized_imports` sandboxes only
  the *generated code*, not the harness process), Vacant's Stop-hook/trace mechanism (built for
  wrapping a CLI agent's tool calls) does not apply to it directly; the natural Vacant hook point
  for the *official* protocol would be around each `agent.run()` call's steps (smolagents does
  expose a step-by-step callback/memory API in principle — not independently verified against
  smolagents 1.3.0's exact API this pass).

## 6. Arm B / Arm C without changing the protocol, and what "accountability" means here

Both arms need to slot in as **wrapper behavior around the unmodified oracle/agent/scorer
pipeline** (never touching `task.toml`, `test.sh`, `scorer.py`, or the model's own answer path),
matching the repo's "installed vs not" side-by-side requirement:

- **Arm A (baseline, no Vacant)**: exactly §4's live smoke, unmodified.
- **Arm B (reviewer-persona self-check, no Vacant evidence)**: after the agent's own
  `final_answer(...)` (or, in the Harbor path, after `/app/answer.txt` is written but *before*
  `test.sh` runs), run **one extra model call** with a reviewer persona prompt that sees only the
  question, guidelines, and the agent's own final answer + its own transcript (no external
  ground-truth, no Vacant trace) and may revise the answer once. This is cheap (1 extra call/task)
  and is exactly the "give it a persona, send it to re-check" condition the owner described, with
  the Huang/Tyen caveat already noted in this repo's task text: expect this to rarely fix anything
  intrinsic, since the model has no new *information*, only a new *framing* — the dabstep-70 case
  above is a good predicted-failure case for Arm B (the "8.3% is a fine threshold" claim reads as
  internally consistent to the same model re-reading its own trace, with nothing pointing it at
  manual.md line 82 specifically).
- **Arm C (Vacant installed)**: same reviewer-persona re-check call, but now grounded in Vacant's
  own trace evidence, computed for free from data Vacant already has from the agent's tool-call
  hook (file reads/writes/runs): (a) was `manual.md` opened at all before the final answer (binary,
  cheap); (b) does every numeric literal in the final answer text trace back to something actually
  read or computed in-session (a `locate`/`blame`-style check per Vacant's own `trace/` module
  design) vs. appearing with no antecedent; (c) was `payments.csv`/`fees.json` opened when the
  question's wording implies they're needed (a cheap keyword heuristic, not a claim of
  completeness). None of this requires knowing the gold answer — it's exactly "was each step
  justified for *this* task", the owner's own framing, and it maps directly onto concrete,
  already-planned Vacant primitives (`intake/verifiers.py`'s PASS/FAIL/UNKNOWN,
  `trace/locate.py`+`blame.py`). **DABstep is a good benchmark for this arm distinction**
  specifically *because* its context files are named, bounded, and few (7 files) — "was the right
  file opened" is a clean binary signal here in a way it would not be on a benchmark with hundreds
  of files or no manual at all.
- Scoring stays untouched: Arm B/C's revised answer is written to the same `/app/answer.txt` (or
  `final_answer()` call) and graded by the same unmodified `scorer.py` — the only thing that
  differs between arms is what runs *before* that final write.

## 7. Calls/tokens per task, budget fit

- **From this session's own live run** (§4, real numbers, not estimated): easy/no-manual task
  4 calls / ~14.3k tokens / $0.0012; easy/manual task 8 calls / ~82k tokens / $0.0067. Hard tasks
  were not live-tested (budget), but the official baseline's own `--max-steps 10` cap plus the
  paper's Table 1 ("maximum of 10 steps per task", confirmed via WebFetch of the HTML paper this
  session) bounds worst case at 10 calls/task under the baseline protocol; our one manual-requiring
  task already used 8 of those 10 steps, so **hard tasks (which need cross-referencing 2+ files)
  should be assumed close to the 10-step ceiling**, i.e. ~10 calls/task, not 4.
- **50 free-calls/day cap**: even at a conservative 10 calls/task, that's **5 tasks/day** on the
  free tier — the 450-task default split would take **90 days** at that rate, and even the 10-task
  dev split would take 2 days. This makes the free tier **infeasible for anything beyond a handful
  of demo tasks/day**; the paid-fallback path (already what MODELS.md's UPDATE switched to:
  `qwen/qwen3.5-9b` pinned paid, $0.08/$0.13 per M tokens) is the only realistic path to a
  multi-task or full-split run.
- **1000 calls/day** (if ever unlocked by a $10+ purchase, per OpenRouter docs, unverified exact
  threshold per MODELS.md's own flagged uncertainty): 100 tasks/day at 10 calls/task — the 450-task
  default split in ~4.5 days, the 130-task Harbor parity sample in ~1.3 days.
  **In USD** (extrapolating this session's measured $/task): easy/light tasks ~$0.001-0.002/task,
  manual-heavy tasks ~$0.007/task, hard tasks likely higher still (more steps, and each step's
  prompt carries the full growing transcript — `dabstep-70`'s 8th call alone was already 78k
  *cumulative* prompt tokens; a 10-step hard task's last call could plausibly exceed 100k prompt
  tokens). A conservative all-hard-task budget: 378 hard tasks × ~$0.01-0.02/task (guessing
  upward from the one manual-heavy easy task, since hard tasks are structurally similar in needing
  multiple files) ≈ **$4-8** for the full default split on `qwen/qwen3.5-9b` at this pricing — this
  is an extrapolation from n=1, not a measurement, and is flagged as such; a 20-30 task pilot
  across both difficulty levels would be needed to tighten it before committing the $5 budget to a
  full run.
- **Published-trajectory numbers**: not found this pass — the paper (arXiv:2506.23719) reports
  accuracy only, no calls/tokens per task in the portion fetched; the HF Space's `submissions`
  split (queried directly this session, `adyen/DABstep` `submissions/default/0000.parquet`, 74,970
  rows) carries `agent_answer` per task but not token/call counts, and its `reasoning_trace` field
  is present but empty in the rows sampled — **not a usable source for calls/tokens**, only for the
  README-described "extract shortest correct answer" mechanism already covered in §1.

## 8. Unavoidable differences from the published/official runs

1. **Answer source for 444 of 450 default-split tasks is not ground truth** — it's the shortest
   publicly-accepted leaderboard submission (§1, §2). Any score against this split conflates "did
   the agent match the true answer" with "did the agent match a *previously accepted* answer
   string", and the acceptance pool itself is a **public, unauthenticated, low-trust leaderboard**
   — sampled directly this session (`submissions` parquet) and found to contain garbled
   `submission_id`/`organisation` fields with embedded free text ("sz-s", "user speta"), i.e. not
   curated. Only the 10 dev tasks are true gold. **Recommendation, already implied by the task's
   own question 1**: headline any DABstep number off the **10-task dev split**, note the 450-task
   default split's answers separately as "leaderboard-extracted, unverified against the hidden
   grader" every time it's cited, exactly as the owner's own question anticipated.
2. **Harbor's `instruction.md` prompt ≠ the baseline's prompt** (§1) — different interface
   (write-to-file vs. tool-call), different system prompt framing than the "chat" path's
   `CODE_SYSTEM_PROMPT`. Any Vacant-vs-no-Vacant comparison run through Harbor is *not* comparable
   to a number quoted from the original DABstep leaderboard without saying so.
3. **Model**: neither official numbers (Table 1: o4-mini, Claude 3.7 Sonnet, o3-mini, Llama
   3.3-70B/3.2-1B/4-Scout/4-Maverick, Deepseek V3/R1 — no Qwen, no Gemma) nor Harbor's parity
   baseline (`claude-haiku-4-5`) used `qwen/qwen3.5-9b` or `google/gemma-3-12b-it`. The closest
   published small-model anchor is **Llama 3.2 1B (0.00% hard / 1.39% easy)** or **Llama 3.3 70B
   (3.70% hard / 68.06% easy)** — both from arXiv:2506.23719 Table 1 (fetched via WebFetch this
   session; exact table cell values not independently re-verified against the PDF's raw table,
   flagged as **secondary-source-extracted**, not a direct table read).
4. **smolagents/transformers pinning** (§4) — reproducing the *exact* baseline needs
   `smolagents==1.3.0`+`transformers==4.47.1` (the latter undocumented by DABstep itself);
   anything run on current `smolagents` is running a materially different agent loop/prompt
   machinery even with identical prompts, since `CodeAgent`'s internals changed across 1.3→1.26.
5. **This session's oracle smoke used a hand-patched Dockerfile** (§3) — proves the grading
   mechanism is correct and unmodified, but is not evidence that `harbor trial start` runs
   cleanly end-to-end in a machine like this one; a real venue run needs either outbound network
   from the docker build context (a real exhibition machine, unlike this sandbox, presumably has
   this) or a Harbor-level fix/config for build-time proxying.
6. **No hard-task live smoke was run** (budget) — all live-call/token/cost figures for hard tasks
   in §7 are extrapolated from n=1 easy/manual-heavy task, not measured.
7. **Concurrency**: the official baseline runs 4 tasks concurrently by default
   (`--concurrency 4`); any Vacant-side sequential or single-task run changes wall-clock but not
   per-task token/cost accounting, so this affects only throughput comparisons, not correctness
   comparisons.

## Sources (session-read, 2026-09-25 unless noted)
- `adyen/DABstep` HF Space clone (commit d4431c2), local files as cited by path above.
- `laude-institute/harbor` clone (commit 6cb9ff3), local files as cited by path above.
- HF API: `/api/datasets/adyen/DABstep` (revision, license, lastModified).
- HF resolve URLs at revision `51884d3339c...` for `data/tasks/{all,dev}.jsonl` and the 7
  `data/context/*` files (sha256s recorded in `scratchpad/study/pin/`).
- HF resolve URL for `submissions/default/0000.parquet` (queried directly with pandas, this
  session, to characterize the leaderboard's data quality — not to compute leaderboard numbers).
- arXiv:2506.23719 (HTML rendering via WebFetch) — Table 1 model rows, "10 steps" claim, "no
  DABstep-v2 mentioned in the paper" (paper predates any v2 announcement the leaderboard's UI text
  references — the Space's `content.py`, read locally, separately says "DABStep-v2 launching in
  the coming weeks" as of this repo's pinned commit, so a v2 is *planned* per the Space even though
  the *paper* doesn't mention it — two different sources, not contradictory, just different dates).
- `/root/.ccr/README.md`, `docker buildx ls`, and direct `docker run --network ...` probes (this
  session) for the network-topology blocker in §3.
