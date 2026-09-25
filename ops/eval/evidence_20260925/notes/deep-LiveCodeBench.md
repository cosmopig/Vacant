# Deep dive: LiveCodeBench v6 code generation (official lcb_runner + Harbor livecodebench@6.0)

Label: deep-LiveCodeBench_v6_code_generation_official_LiveCodeBench_LiveCodeBench_lcb_runner_Harbor_livecodebench_6_0_100_task_subset_
Date: 2026-09-25. Role: reproduction-check.

## Repos pinned
- `livecodebench/LiveCodeBench` @ `28fef95ea8c9f7a547c8329f2cd3d32b92c1fa24` (2025-07-15), clone at
  `scratchpad/study/src/LiveCodeBench`. Confirmed current HEAD via
  `git ls-remote https://github.com/LiveCodeBench/LiveCodeBench.git HEAD` (matches, 2026-09-25).
  MIT license (`LICENSE`).
- `laude-institute/harbor` @ `6cb9ff3167596c456e0b24622d473b59fc9ab6c7` (2026-09-24), clone at
  `scratchpad/study/src/harbor`.

## 1. Official protocol, exact, with file:line

### Dataset loading
- `lcb_runner/benchmarks/code_generation.py:125`: `load_dataset("livecodebench/code_generation_lite", split="test", version_tag=release_version, trust_remote_code=True)`.
- The HF loading script `code_generation_lite.py` (fetched 2026-09-25 from
  `https://huggingface.co/datasets/livecodebench/code_generation_lite/resolve/main/code_generation_lite.py`,
  dataset commit `0fe84c3912ea0c4d4a78037083943e8f0c4dd505`, last modified 2025-06-05):
  `_split_generators` calls `dl_manager.download_and_extract(_URLS)` where `_URLS["test"]` is the
  **full list of all 6 files** (`test.jsonl`..`test6.jsonl`) **regardless of `version_tag`** — the
  `ALLOWED_FILES[version_tag]` filter is only applied in `_generate_examples`, *after* download.
  **=> Requesting `release_v6` (or any single version) still downloads all 6 raw files.**
- Measured sizes (HEAD via `resolve/main`, 2026-09-25): test.jsonl 1,252,609,773 B, test2 713,377,060 B,
  test3 623,360,766 B, test4 1,204,644,685 B, test5 557,699,297 B, test6 134,303,240 B.
  **Total ≈ 4.486 GB** for the full official dataset load, independent of which release version is requested.
  This alone exceeds our 2 GB smoke-disk budget, so the model-free smoke below uses Vacant's own
  already-downloaded, sha256-pinned LCB reference-solution bank instead of re-downloading (see §3).
- `README.md:52-57`: version table — `release_v1` 400 problems (May 2023–Mar 2024) ... **`release_v6`
  1055 problems (May 2023–Apr 2025)**. `release_latest` == `release_v6` contents as of this repo commit.
- Dataset license per HF API (`/api/datasets/livecodebench/code_generation_lite`, read 2026-09-25): `cc`
  (repo also states MIT for the *loading script*; the two are different: MIT covers lcb_runner code,
  `cc` is the HF dataset card's declared license for the data itself — not independently disambiguated
  further this pass, "cc" without a more specific SPDX tag is what the API returns).
- Dataset does **not** ship gold/oracle solutions (Harbor adapter README, confirmed): only test I/O.

### Prompt template (code generation, generic/"OpenAIChat"-style models)
`lcb_runner/prompts/code_generation.py`:
- `PromptConstants.SYSTEM_MESSAGE_GENERIC` (used for `LMStyle.OpenAIChat` and most API models):
  `"You are an expert Python programmer. You will be given a question (problem specification) and
  will generate a correct Python program that matches the specification and passes all tests."`
- `get_generic_question_template_answer(question)`:
  ```
  ### Question:
  {question_content}

  ### Format: {FORMATTING_MESSAGE_WITH_STARTER_CODE or FORMATTING_WITHOUT_STARTER_CODE}
  ```python
  {starter_code or "# YOUR CODE HERE"}
  ```

  ### Answer: (use the provided format with backticks)

  ```
- Sent as `[{"role":"system","content":SYSTEM_MESSAGE_GENERIC}, {"role":"user","content":<above>}]`
  (see `oai_runner.py` construction path via `scenario_router.py`, verified by reading
  `format_prompt_generation`/`PromptConstants` directly — not re-quoted in full here for space).

### Sampling / run settings (defaults), `lcb_runner/runner/parser.py`
- `--n` default **10** samples per problem (pass@1/pass@5 computed from these).
- `--temperature` default **0.2**, `--top_p` default **0.95**, `--max_tokens` default **2000**.
- `--timeout` (per-test-case grading timeout) default **6** seconds.
- `--release_version` default `release_latest`.
- `--openai_timeout` default 90s (API call timeout, not grading).
- `oai_runner.py:34-43`: for non-reasoning OpenAI-style models, request kwargs are exactly
  `{temperature, max_tokens, top_p, frequency_penalty:0, presence_penalty:0, n, timeout}` — no
  explicit `reasoning`/`thinking` control. For `LMStyle.OpenAIReason*` models it instead sends
  `reasoning_effort` and drops temperature/top_p/max_tokens (25000 max_completion_tokens for
  `OpenAIReasonPreview`, no cap enforced beyond the model default for plain `OpenAIReason`).
  **No `LMStyle` entry exists for Qwen3.5-9B or Gemma-3-12B-it in `lm_styles.py` (871 lines, checked
  2026-09-25) — the repo is frozen at 2025-07-15 and neither model existed/was added yet.** A real
  reproduction attempt must either (a) add an `LMStyle`/`LanguageModel` entry (a few lines, low risk),
  or (b) go through `custom_evaluator.py` (see below) with your own generation loop, which is what we
  did.

### Code extraction
`lcb_runner/utils/extraction_utils.py:extract_code` (non-CodeLLaMa, non-GenericBase style): finds all
lines containing `` ``` `` and returns the text between the **second-to-last and last** such line
(i.e., the *last* fenced code block in the model's output). Returns `""` if fewer than 2 fence lines.

### Grading (the actual checker)
`lcb_runner/evaluation/testing_util.py` + `compute_code_generation_metrics.py`:
- `sample["input_output"]` = `json.dumps({"inputs": [...], "outputs": [...], "fn_name": <str or None>})`.
  `fn_name` present ⇒ call-based (LeetCode `class Solution` or bare function); absent ⇒ stdin/stdout.
- `compile_code` (`testing_util.py:191-208`): `exec(code, tmp_sol.__dict__)`; if the literal substring
  `"class Solution"` appears in the code, instantiates `tmp_sol.Solution()`; else uses the module
  directly (so a bare top-level function named `fn_name` also works — confirmed by our smoke test).
- `grade_call_based` (`testing_util.py:229+`): for each test, `all_inputs` parsed as
  `[json.loads(l) for l in inputs.split("\n")]` (one JSON value per line = one positional arg),
  `prediction = method(*gt_inp)`, compared to `json.loads(expected_output)`.
- Grading timeout: `run_test(..., timeout=6)` (matches `--timeout` default) per test case;
  `check_correctness` (`compute_code_generation_metrics.py:29`) wraps `run_test` in a
  **fresh `multiprocessing.Process`** with an outer wall budget of
  `(timeout+1) * n_test_cases + 5` seconds, and returns all `-1` ("failed") if that outer process
  never reports back (global timeout / crash).
- **Found by hitting it**: `run_test()` calls `reliability_guard()` (`testing_util.py:437`), which
  monkeypatches/disables `os.environ`, `os.putenv`, `builtins.exit`, etc. **in the calling process,
  permanently**, as an untrusted-code sandbox measure. Calling `run_test()` directly, more than once,
  in the same Python process crashes on the 2nd call (`TypeError: 'NoneType' object is not callable`
  inside `os.environ.__setitem__` → `os.putenv`). This is why the official pipeline never calls
  `run_test()` in-process for more than one sample — it *always* goes through `check_correctness`'s
  `multiprocessing.Process` wrapper. Confirmed empirically (see §3).
- Scoring: `pass_k_utils.py:estimate_pass_at_k` (standard HumanEval-style unbiased estimator);
  `compute_metrics_from_results` — a problem's generation is "correct" iff **all** its test results are
  truthy (`np.all(gen > 0)`); `pass@1`/`pass@5` are means of per-problem `estimate_pass_at_k` over `n`
  samples. Final headline score = accuracy = mean `pass@1` (README: "Accuracy — the percentage of
  coding questions with all test cases passed" — matches Harbor's framing too).
- Paper vs code: paper (arXiv:2403.07974) frames the *evaluation as contamination-resistant/rolling*;
  the `--start_date`/`--end_date` flags exist specifically because "In our paper, to counter
  contamination in the DeepSeek models, we only report results on problems released after August 2023"
  (`README.md:94-97`) — i.e. the paper's headline numbers for some models use a **narrower date window
  than the full release**, a paper-vs-code nuance not visible from the code defaults alone.

### `custom_evaluator.py` (bring-your-own-model path — what a non-listed model like ours must use)
`lcb_runner/runner/custom_evaluator.py`: takes `--custom_output_file` (a JSON list of
`{"question_id":..., "code_list":[...]}`, one entry per problem, `code_list` = list of `n` extracted
solutions), builds `save_results`, calls `get_metrics(Scenario.codegeneration, args, benchmark,
combined_results)`, writes `<file>_codegeneration_output(_eval[/_all]).json`. This is the exact,
sanctioned "official" way to grade a model that isn't in `lm_styles.py`: build the prompt yourself with
the exported template functions, call the model yourself, extract code with the exported
`extract_code`, then hand the extracted code to this script (or, as we did for the smoke, call its
same underlying `compute_code_generation_metrics` functions directly).

## 2. Dataset pin
- HF dataset `livecodebench/code_generation_lite`, commit `0fe84c3912ea0c4d4a78037083943e8f0c4dd505`
  (`/api/datasets/...` `sha`), last modified 2025-06-05T17:18:27Z, license tag `cc`, read 2026-09-25.
  Files/sizes: see §1. We did **not** download these files to disk this pass (budget); sizes were
  measured by streaming to `/dev/null` (`curl -sSL ... | wc -c`), so no sha256 of the raw bytes was
  taken — recorded as a gap, not a claim.
- Vacant's own pinned substitute used for the model-free smoke: `ops/gain/data/lcb_bank_v2.jsonl`
  (120 problems) + `ops/gain/data/lcb_probe_solutions.json` (12 reference solutions), both already in
  the Vacant repo (not re-fetched). Built by `ops/gain/build_lcb_bank.py` from the same underlying
  `livecodebench/code_generation_lite` test5/test6 files (per that script's docstring), but **the
  `prompt` field in the bank has been rewritten**: the original English `starter_code`
  (`class Solution: def f(self, ...)`) was stripped and replaced with a Traditional-Chinese
  top-level-function instruction, for Vacant's own (different) G-experiment. This is *not* the raw HF
  record — flagged and handled explicitly in §3/§8.

## 3. Smoke run — model-free (official grader on oracle vs wrong solution)

Ran **unmodified** `lcb_runner.evaluation.compute_code_generation_metrics.check_correctness` (which
calls the unmodified `testing_util.run_test`) against 3 tasks common to Vacant's `lcb_bank_v2.jsonl`
and `lcb_probe_solutions.json` (`lcb_3594`, `lcb_3607`, `lcb_3629`), reconstructing the official
`input_output` JSON shape from the bank's `{"args":[...], "expected":...}` records.

- Script: `smoke_grader.py`, log: `smoke_grader.log`, results: `smoke_grader_results.json`.
- venv: `venv/` (Python 3.11.15, `numpy` + `tqdm` only — did **not** install `torch`/`vllm` for this
  part since `testing_util.py`/`pass_k_utils.py`/`compute_code_generation_metrics.py` import neither).
- Result: **all 3 correct/reference solutions pass all tests (27, 27, 26 respectively); all 3
  trivially-wrong solutions (`return None`) fail all tests.** Wall time ≈0.03–0.04s per grading call.
- Hit and fixed the `reliability_guard()`/`os.environ` in-process crash described in §1 by switching
  from calling `run_test()` directly to `check_correctness()` (subprocess-isolated) — this is itself a
  finding about the official code, not a bug in our script.
- Disk: venv with numpy+tqdm only ≈ small (<50MB); see §7 for the later, larger venv.

## 4. Smoke run — live, qwen/qwen3.5-9b via recording proxy

Script: `live_smoke.py`, log: `live_smoke.log`, per-task logs: `live_logs/`, results:
`live_smoke_results.json`. Tasks: `lcb_3594`, `lcb_3607` (2 tasks, per budget). Model:
`qwen/qwen3.5-9b`, proxy tag `live-lcb-<task_id>`, base `http://127.0.0.1:18900/t/live-lcb-<id>/api/v1`.

Built the **official** prompt (`SYSTEM_MESSAGE_GENERIC` + `get_generic_question_template_answer`
verbatim, imported from the pinned repo, not re-typed) with **reconstructed** `question_content`
(English portion of the bank's `prompt` field, before the injected Chinese suffix) and a
**reconstructed** `starter_code` (`class Solution:\n    def <entry_point>(self, <params>):`, params
parsed from the Chinese suffix's function-signature line). **This reconstruction is a known deviation
from the byte-exact original HF `question_content`/`starter_code`** (see §2) — good enough to exercise
the real template/extraction/grader end-to-end, not claimed as an exact-text reproduction.

Extra deps needed beyond numpy/tqdm to even `import lcb_runner.prompts.code_generation` (its
`__init__.py` eagerly imports every scenario's prompt module): `datasets`, `anthropic`, `cohere`,
`google-genai`, `mistralai==0.4.2`, `openai`, `pebble`, `together`, `annotated-types`
(**not** `torch`/`vllm` — those are only needed for local/vLLM runners, not for
prompt-building/extraction/grading). Two more findings surfaced doing this:

- **`lcb_runner/prompts/code_generation.py`** guards its `anthropic` import in a `try/except
  ImportError`, but **`lcb_runner/prompts/test_output_prediction.py:3`** does the *same* `from
  anthropic import HUMAN_PROMPT, AI_PROMPT` **unguarded**, and `prompts/__init__.py` imports that
  module eagerly too — so *any* import of `lcb_runner.prompts` (including just for code-generation)
  requires `anthropic` to be installed and importable, contradicting the "generic" prompt path's own
  defensive import.
- **`anthropic>=0.42.0`** (the repo's declared minimum, `pyproject.toml`) resolves today to a current
  `anthropic` release that **removed `HUMAN_PROMPT`/`AI_PROMPT`** (legacy Completions-API constants),
  so `pip install "anthropic>=0.42.0"` **breaks the import outright** on a fresh install as of
  2026-09-25. Had to pin `anthropic==0.42.0` exactly to get past this. **This means `uv pip install -e
  .` / `pip install -e .` against the unmodified `pyproject.toml`, on a machine with network access
  today, does not actually work out of the box** — a real, reproducible repo-freshness bug, not
  something specific to our environment.

Live results:
| task | attempt | max_tokens | finish_reason | prompt_tok | completion_tok (all reasoning) | cost (USD) | wall (gen) | code extracted | graded pass |
|---|---|---|---|---|---|---|---|---|---|
| lcb_3594 | 1 (official default) | 2000 | length | 453 | 2000 | 0.000296 | 14.0s | no (content=None) | n/a (0/27) |
| lcb_3594 | 2 (4x bump) | 8000 | length | 453 | 8000 | 0.001076 | 53.4s | no (content=None) | 0/27 |
| lcb_3607 | 1 (4x bump; skipped 2000 given attempt above) | 8000 | length | 365 | 8000 | 0.001069 | 53.8s | no (content=None) | 0/27 |

Inspected the raw `reasoning` field (`live_logs/lcb_3594_response.json`): at 8000 reasoning tokens the
model is still mid-derivation (25,278 chars of `<think>`-style content, not looping/repeating, not
near a final answer) — this looks like the model genuinely needing far more budget on this endpoint,
not a formatting bug. **Finding, load-bearing for feasibility**: reproducing LiveCodeBench-style
problems against `qwen/qwen3.5-9b` pinned to `darkbloom/fp4` through this recording proxy, at the
**official default `max_tokens=2000`, yields empty completions on 100% of our (small, n=2) sample** —
`finish_reason="length"` with the entire budget spent on reasoning and `message.content=None`. Even at
4x the default (8000) it still didn't finish either task. This directly bears on feasibility/cost
(§7): a real reproduction attempt against this model+endpoint needs either (a) a much larger
`max_tokens` (untested how much; cost scales linearly with it since reasoning tokens are billed as
output at 0.13 USD/M) or (b) a way to cap/disable "thinking" for this model on this endpoint (not
investigated this pass — no `reasoning: {enabled:false}`-style param was tried), or (c) a different
model/endpoint. **We could not, this pass, get qwen/qwen3.5-9b via darkbloom/fp4 to actually answer a
LiveCodeBench-style problem within a plausible token budget** — this is the single most important
result of this deep-dive for planning.

Ledger (`scratchpad/evalrun/ledger/summary.json`, `by_tag`, read 2026-09-25 after the run):
`live-lcb-lcb_3594`: 2 requests, 906 prompt / 10000 completion (all reasoning) tokens, $0.00137248.
`live-lcb-lcb_3607`: 1 request, 365 prompt / 8000 completion tokens, $0.0010692.
**Total spent by this deep-dive: $0.0032543** (cap for this agent was $0.15; global cap $4.80,
$0.0033 total spent across all tags as of this run per `summary.json`).

## 5. Published baselines (small/open-weight, and reproduction-check candidates)

- **Qwen/Qwen3.5-9B** — LiveCodeBench v6 = **65.6** (row: `"LiveCodeBench v6 | 82.7 | 74.6 | 68.7 |
  66.0 | 65.6 | 55.8"`, positioned among GPT-OSS-120B/20B and Qwen3 variants, "Reasoning & Coding"
  section). Source: https://huggingface.co/Qwen/Qwen3.5-9B, read 2026-09-25.
  **No evaluation settings are stated on the card** — no release window, thinking on/off, temperature,
  top_p, max_tokens, n, or pass@k specified anywhere near the table (checked explicitly this pass,
  confirms/settles open question (1): **the exact window/settings behind 65.6 are not published**).
  Given our live-smoke finding above (this exact model, via a paid fp4 endpoint, cannot even complete
  an answer at 2000–8000 output tokens), the 65.6 number almost certainly used a much larger output
  budget and/or a different (non-quantized, non-rate-shaped) serving path than what's available to us.
- **google/gemma-3-12b-it** — LiveCodeBench = **32.0** (not 24.6 as an earlier, unverified pass had
  recalled — that number was **wrong**, corrected this pass). Source: arXiv:2503.19786 ("Gemma 3
  Technical Report"), **Table 18** ("Performance of instruction fine-tuned (IT) models of different
  sizes on more internal and external benchmarks"), Gemma-3 12B column (values across the row:
  Gemma2-2B 7.0, Gemma2-9B 20.0, Gemma2-27B 29.0, Gemma3-1B 5.0, Gemma3-4B 23.0, **Gemma3-12B 32.0**,
  Gemma3-27B 39.0 bold/best). Verified by direct HTML table extraction from
  https://ar5iv.labs.arxiv.org/html/2503.19786 (fetched to `gemma3_ar5iv.html`, grepped, table
  structure confirmed with header row `Sx1.T18.2.1`/`Sx1.T18.2.2` giving the Gemma2/Gemma3 x
  2B/9B/27B/1B/4B/12B/27B column layout) — read 2026-09-25. Same table, same column: **HumanEval 85.4,
  MBPP 73.0** for Gemma-3-12B-it (these two match the earlier pass's recollection; the LCB number did
  not). Eval methodology, **Table 21** ("Details on instruction fine-tuned (IT) benchmarks"),
  LiveCodeBench row: Metric = "Average over 8 samples", Type = "sampling" (not greedy), n-shot =
  "0-shot", COT = "Yes". **No release-date window, temperature, or top_p given in Table 21** — same
  gap as the Qwen card, confirms open question (1) can't be settled from the vendor-published numbers
  for either candidate model without contacting the authors or finding a companion eval script.
- Both are **useful reproduction anchors but for different reasons**: Qwen3.5-9B is the actual model
  Vacant plans to route through OpenRouter (fp4-quantized), so matching ~65.6 would validate the
  serving path; Gemma-3-12b-it is the actual weights class people run locally at Q4 (deepinfra/bf16 is
  the only OpenRouter provider, i.e. **not actually quantized** on that route — a real mismatch with
  "behaves like a local Q4 12B" that CLAUDE.md's owner concept wants, flagged in MODELS.md already).

## 6. Which agents can run under the official protocol

- **The official `lcb_runner` is not an agent harness at all** — it's a single-shot
  prompt-in/completion-out benchmark (`oai_runner.py` et al. call `chat.completions.create` once per
  sample, no tool use, no multi-turn). There is **no concept of "an agent" in the official protocol**:
  pi/OpenCode/Claude Code/Codex have no native adapters here and *cannot* meaningfully be "run under"
  it — the closest thing is pointing any of their underlying model-call plumbing at the same
  chat-completions endpoint the official runner would use, but that bypasses the agent entirely (no
  hooks, no tool calls, nothing for Vacant's trace/accountability layer to observe). **Vacant hooking
  the official lcb_runner path is a null proposition — there's no agent step to hook.**
- **Harbor's `livecodebench` adapter (`adapters/livecodebench/`) turns it into an agentic terminal
  task instead**: the agent gets an `instruction.md`, a Docker sandbox, `check_solution.py` for
  iterative public-test runs, and must write a solution file before the container's `final_test.py`
  grades public+private tests — genuinely different from the official protocol (multi-turn, tool use,
  iterative self-testing allowed) even though it's built from the same underlying dataset. Confirmed:
  **Harbor's agent factory (`src/harbor/agents/factory.py`) natively registers all four target
  agents**: `AgentName.CLAUDE_CODE → installed.claude_code:ClaudeCode`, `AgentName.CODEX →
  installed.codex:Codex`, `AgentName.OPENCODE → installed.opencode:OpenCode`, `AgentName.PI →
  installed.pi:Pi`. So **pi, OpenCode, Claude Code and Codex can all run Harbor's livecodebench@6.0
  task via their native Harbor adapters** — but this is a materially different (agentic,
  multi-attempt, tool-using) benchmark than "the official LiveCodeBench harness", not a drop-in
  reproduction of the 65.6/32.0-style numbers.
- Gotcha for wiring our OpenRouter-via-proxy models into Harbor's agent adapters (found while checking
  this): `harbor/agents/installed/opencode.py:548-552` — the custom `base_url`
  (`access.configured_base_url`) is only written into the opencode provider config **when `provider in
  {"anthropic","google","openai"}`**; a model routed as e.g. `openrouter/qwen/qwen3.5-9b` would **not**
  get the base_url override at all under Harbor's OpenCode adapter as-is. `pi.py`
  (`access.configured_base_url` used unconditionally at line 218) does not have this restriction.
  Not exhaustively checked for `claude_code.py`/`codex.py` this pass — flagged as an open question.
- **Official scaffold**: none — `lcb_runner` has no "scaffold" concept (no mini-swe-agent/Terminus
  usage anywhere in the pinned commit; `grep` for those terms in `lcb_runner/` returned nothing).
  Harbor's adapter *does* support `terminus-2` (see the harbor README's own parity experiments using
  `terminus-2 + gpt-5-mini`) as well as the four Vacant target agents.

## 7. Arm C / Arm B and the owner concept on this benchmark

- **Official lcb_runner protocol**: no natural place for "arm C" (Vacant installed) since there's no
  agent step — Vacant's trace/accountability layer has literally nothing to hook (one API call, no
  tool use, no files, no intermediate steps to justify or second-guess). The only way to test the
  owner's "installed is better than not installed" claim on *this exact protocol* would be to run the
  single generation once "bare" (arm A: no Vacant, no reviewer) and once wrapping that single call with
  a Vacant-instrumented self-review pass that re-prompts with the actual failing test output before
  final submission (arm C) — which is really a self-repair/self-debug variant of the benchmark, not
  the vanilla protocol, so it should be labeled and reported as a **modified** LiveCodeBench-selfrepair
  style comparison, not "LiveCodeBench v6 with/without Vacant".
- **Harbor's agentic adapter** is a much more natural fit for arm B/C as the owner's concept describes
  it, since there *are* real steps to check ("did the agent actually run `check_solution.py` before
  declaring done, does its final code match what `check_solution.py` last showed passing, did it
  invent a test result it never ran"): arm A = bare agent, arm B = same agent + a reviewer-persona
  self-check prompt appended before final submission (no Vacant evidence, model's own judgment only),
  arm C = same agent + Vacant's Stop-hook feedback loop grounded in the actual recorded trace (did it
  call `check_solution.py`? what did it print? does the submitted file match what passed?). This maps
  cleanly onto the owner's "checked whether each step was justified" framing **only under the Harbor
  adapter**, not the official single-shot protocol.
- Concretely, on Harbor-livecodebench, "justified for the current task" cashes out as: (1) did the
  agent run the provided `check_solution.py` (public tests) at all before finishing — Vacant's trace
  can see this directly (a `tool_use`/bash-run step); (2) does the final submitted solution file match
  byte-for-byte (or was it edited after) the version that last showed a passing `check_solution.py`
  run — Vacant's `blame`/`locate` machinery is built for exactly this; (3) did the agent claim (in its
  own chat/completion text) a test passed that the trace shows it never ran — the KS-1-clean feedback
  language ("report.md line 3 first written at step 2, check_solution.py never invoked for this file")
  fits directly, no "you are responsible" framing needed.

## 8. Model calls / tokens per task, and feasibility under call/day and USD caps

- **No published per-call trajectory/token data found this pass** for either Qwen3.5-9B's 65.6 or
  Gemma-3's 32.0 on LiveCodeBench — neither source publishes raw generations, token counts, or
  wall-clock; both are single aggregate numbers with (for Gemma) only a coarse methodology row
  ("avg over 8 samples") and (for Qwen) no methodology at all. So "calls per task" below is **derived
  from our own live smoke**, not from official trajectories — flagged as such.
- **Official lcb_runner protocol**: `n=10` samples per problem (default) = **10 model calls per task**
  minimum for pass@1/pass@5 as computed by the repo (a single sample, n=1, is possible and would still
  give a pass@1 estimate, just noisier / not what the published pass@1 numbers use).
  - Full `release_v6` = 1055 problems × 10 samples = **10,550 calls** for one full run.
  - Harbor's "100-task subset" (sample_seed=42, `sample-size 100`) × 10 = **1,000 calls** for one
    n=10 run of the subset; **100 calls** for a single-sample (n=1) pass@1-only run of the subset.
  - At our free-tier cap of **50 free-model calls/UTC day**, even the 100-task subset at n=1 needs
    **2 UTC days** minimum (100 calls / 50/day), and the full n=10 protocol on the subset needs
    **20 days**. The full 1055-problem release_v6 at n=10 is **211 days** at 50/day — not remotely
    feasible on the free tier; **a paid model is required for anything beyond a tiny slice**, which
    matches why the owner already switched to the $5 paid-credit plan for qwen3.5-9b/gemma-3-12b-it
    (MODELS.md UPDATE 2026-09-25).
  - Under a hypothetical 1000/day tier (>=10 USD purchased, per OpenRouter docs, unverified exact
    numbers this pass per MODELS.md's own caveat): the 100-task subset at n=10 (1000 calls) fits in
    **1 day**; full release_v6 at n=10 (10,550 calls) needs **~11 days**.
- **Cost, USD, from our measurements** (§4): at `max_tokens=8000` and **still not finishing**, one
  qwen3.5-9b call on this endpoint costs ≈**$0.00107–0.00137** (prompt ~365-453 tok @ $0.08/M +
  8000-10000 completion/reasoning tok @ $0.13/M) — and that's for a call that **produced no usable
  answer**. Since we never observed a completed answer, we cannot give a reliable "$ per solved task"
  number; we can only give a **lower bound on $ per attempted call**:
  - 100-task subset, n=1, at the (insufficient) 8000-token budget: 100 × $0.0011 ≈ **$0.11** just to
    get 100 *empty* completions — before even trying a larger budget that might actually finish.
  - If a much larger budget (e.g. 16k-32k tokens) turns out to be needed to get real answers (untested
    this pass — see §4's open flag), cost roughly doubles/quadruples again per call, i.e. plausibly
    **$0.20-$0.45 for a 100-task, n=1 sweep at qwen3.5-9b prices**, still inside the $4.80 global cap
    for a single n=1 pass, but **n=10 (the protocol's actual default) would need ~$2-4.5**, consuming
    most or all of the remaining budget for one model, one subset, one arm.
  - `openai/gpt-oss-20b` (fp4, ~$0.02-0.03/M input, cheaper paid fallback per MODELS.md) was not tested
    live this pass (budget prioritized qwen3.5-9b per the lead's instructions) but is worth a follow-up
    smoke given qwen3.5-9b's reasoning-token blowup problem here.
- **Bottom line for feasibility**: the free 50-calls/day tier cannot run even the 100-task Harbor
  subset once at the protocol's default n=10; a paid small/quantized model is required, and — per our
  live finding — **qwen/qwen3.5-9b on the darkbloom/fp4 route may not be usable at all for this
  benchmark within any output-token budget we tested**, which is a much bigger feasibility problem than
  the calls/day math alone suggests, and should be resolved (try gpt-oss-20b, or a reasoning-disable
  param, or a much larger token cap on qwen3.5-9b) before committing to a full run.

## 9. Unavoidable differences from the published runs (recording plan)

Every item below would be logged as a structured field alongside any Vacant-vs-bare comparison run on
this benchmark, not left implicit:

1. **Serving path / quantization**: our qwen3.5-9b calls go through OpenRouter → `darkbloom` provider,
   pinned `fp4`; the Qwen3.5-9B card's 65.6 gives no serving/quantization detail at all — could be
   full-precision on Alibaba's own infra. Gemma-3-12b-it on OpenRouter (`deepinfra/bf16`, per
   MODELS.md) is **not quantized** on that route, while the "12B gemma at 4-bit" the owner asked to
   match implies Q4 — a real precision mismatch, recorded per-run as `{provider, quant}`.
2. **Sampling budget / thinking control**: official default `max_tokens=2000`, `n=10`. We could not get
   qwen3.5-9b to finish even one sample at 8000. Any real run will need a different `max_tokens` (TBD,
   see §8) and likely `n=1` (not `n=10`) purely for cost/day-limit reasons — both are protocol
   deviations from the published pass@1/pass@5 methodology, not equivalent to it, and must be reported
   as "pass@1 (n=1)" rather than compared numerically to a published "pass@1 (n=10 estimator)".
3. **Dataset window**: whatever subset is actually run (Harbor's 100-task seed-42 sample of
   release_v6, most likely, for cost reasons) is not the same 1055-problem population either published
   number was computed over — record the exact task-id list and seed used, not just "release_v6".
4. **Prompt template match**: if we go through `custom_evaluator.py`'s sanctioned bring-your-own-model
   path (recommended, given neither target model is in `lm_styles.py`), the prompt is built with the
   *exact* exported `SYSTEM_MESSAGE_GENERIC`/`get_generic_question_template_answer` — byte-identical
   to what a listed OpenAIChat-style model would get. This is one axis where we can claim "no
   difference at all" truthfully, unlike quantization/sampling above.
5. **Grading harness**: model-free smoke (§3) used the **unmodified** official grader against
   Vacant's own bank data reconstructed into the official `input_output` shape — not the raw HF
   records, since we didn't download them this pass (§2). A full run should grade against the **actual
   downloaded** HF `release_v6` records (or Harbor's task-per-problem Docker grading, if using the
   agentic Harbor path) rather than the bank reconstruction, to remove this gap.
6. **Repo bit-rot**: `pip install -e .` against the pinned commit's unmodified `pyproject.toml` does
   **not** work as of 2026-09-25 (`anthropic>=0.42.0` pin resolves to a version missing
   `HUMAN_PROMPT`/`AI_PROMPT`, imported unconditionally by `test_output_prediction.py`, itself imported
   eagerly by `prompts/__init__.py`). Any reproduction must either pin `anthropic==0.42.0` (what we
   did) or patch the import — both are deviations from "just run the official installer", to be
   recorded verbatim (exact pin used) rather than silently worked around.
7. **Agent identity, if the Harbor agentic path is used**: which of pi/OpenCode/Claude Code/Codex, and
   which underlying model each is driving (the agent's own "thinking" model could differ from the
   qwen3.5-9b/gemma-3-12b-it under test if not configured carefully) — record both explicitly per run.

## Open questions (not resolved this pass)

- Whether a larger `max_tokens` (16k/32k+) ever lets qwen/qwen3.5-9b (darkbloom/fp4) produce a real
  answer on LiveCodeBench-style problems, and at what cost — not tested, budget-conscious stopping
  point after 2 non-finishing attempts.
- Whether OpenRouter/darkbloom exposes any reasoning-effort/thinking-budget control param for this
  model that would avoid the blowup entirely (not investigated).
- Exact settings (window, temperature, n, thinking) behind both the Qwen3.5-9B 65.6 and Gemma-3-12b-it
  32.0 numbers remain genuinely unpublished, confirmed by direct inspection of both primary sources —
  this is not a research gap on our side, it's a real gap in what the vendors disclosed.
- Whether `claude_code.py`/`codex.py`'s Harbor adapters have the same custom-base-url provider
  restriction found in `opencode.py` — not checked this pass.
- HF dataset license disambiguation (`cc` tag with no more specific SPDX identifier returned by the
  API) — not chased further.

## Sources (all read 2026-09-25 unless noted)
- https://github.com/LiveCodeBench/LiveCodeBench @ 28fef95ea8c9f7a547c8329f2cd3d32b92c1fa24 (local clone, read directly)
- https://github.com/laude-institute/harbor @ 6cb9ff3167596c456e0b24622d473b59fc9ab6c7 (local clone, read directly)
- https://huggingface.co/api/datasets/livecodebench/code_generation_lite (dataset metadata, sha/license/siblings)
- https://huggingface.co/datasets/livecodebench/code_generation_lite/resolve/main/code_generation_lite.py (loading script, fetched)
- https://huggingface.co/datasets/livecodebench/code_generation_lite/resolve/main/test{,2,3,4,5,6}.jsonl (HEAD/size probe only, not downloaded to disk)
- https://huggingface.co/Qwen/Qwen3.5-9B (LiveCodeBench v6 = 65.6 row, no settings stated)
- https://arxiv.org/abs/2503.19786 / https://ar5iv.labs.arxiv.org/html/2503.19786 (Gemma 3 Technical Report, Table 18 = 32.0 LCB / 85.4 HumanEval / 73.0 MBPP for 12B-IT; Table 21 = eval methodology "avg over 8 samples, sampling, 0-shot, COT=Yes")
- Vacant repo: `ops/gain/build_lcb_bank.py`, `ops/gain/data/lcb_bank_v2.jsonl`, `ops/gain/data/lcb_probe_solutions.json` (read directly, not fetched)
- `scratchpad/evalrun/ledger/summary.json` (cost/token ledger, read post-run)
