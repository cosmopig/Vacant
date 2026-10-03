# scout-data — NOTES (read 2026-09-25)

Scope: data/spreadsheet/document benchmarks with deterministic grading, "did it
actually use my data or invent numbers" failure mode, file-workspace coding agent
fit, feasibility under 50 free OpenRouter calls/UTC-day.

Local clones (code/configs only, large data blobs deleted to respect the >1GB
heavy-download limit and the shared 18GB disk budget):
`/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/study/src/{SpreadsheetBench,InfiAgent,da-code,DSBench,BLADE,financebench,DABstep_space,discoverybench}`
Total ~1.8GB, disk still at 16GB avail after cleanup (checked `df -h /tmp`, 2026-09-25).

## 1. SpreadsheetBench (NeurIPS 2024 D&B, spotlight)
- Repo: https://github.com/RUCKBReasoning/SpreadsheetBench (cloned, HEAD read 2026-09-25)
- Paper: arXiv:2406.14991 (https://arxiv.org/abs/2406.14991)
- Data: 912 real Excel-forum questions, 2,729 test cases (~3/question). Public
  tarballs in-repo: `data/sample_data_200.tar.gz` (200), `data/spreadsheetbench_912_v0.1.tar.gz`
  (full 912, released 2025/04), `data/spreadsheetbench_verified_400.tar.gz` (expert-annotated
  400-subset, released 2025/12 with Shortcut.AI/Fundamental Research Labs). **All
  answers public** — input/answer `.xlsx` pairs ship in the repo, no held-out split.
- Task shape: instruction (NL) + input spreadsheet(s); agent must produce an output
  spreadsheet with cell values/formats matching the answer file. Read from `evaluation/README`
  + `evaluation/evaluation.py` (read 2026-09-25).
- Grading: **fully deterministic, OJ-style**. `evaluation/evaluation.py` does per-cell
  value comparison (`compare_cell_value`, numeric round-to-2dp, datetime→Excel-serial
  normalization) plus fill/font color comparison; a solution passes an instance only if
  it matches **all** ~3 test-case spreadsheets for that question. No LLM judge.
- Official harness: LLM writes Python (openpyxl/pandas-style) code, executed inside a
  provided Docker image (`code_exec_docker/`) against a Jupyter kernel server
  (`start_jupyter_server.sh`); output workbook is saved then scored by `evaluation.py`.
  Two inference modes: **single-round** (1 model call/task, code executed once, no
  feedback) and **multi-round ReAct** (`inference_multiple.py`, `--max_turn_num` default
  **5** → up to 5 model calls/task with code-exec feedback each turn). Confirmed in
  `inference/inference_multiple.py:138` and `inference_multiple_row_react_exec.sh`.
  `open_spreadsheet.py` needs LibreOffice 7.5+ (`soffice`) or win32com to force formula
  recalculation before scoring — an extra local dependency, not just Python packages.
- Requirements: Docker (for code exec), LibreOffice (for eval recalculation), Python
  deps in `requirements.txt` (openpyxl, pandas, tqdm...). No GPU. No external API needed
  beyond whatever model serves inference.
- Fit for file-workspace coding agent: **very good** — task is literally "read the
  xlsx files I gave you, write/execute code, produce an output xlsx"; exactly the
  do-not-invent-numbers failure mode Vacant targets. A coding agent (pi/OpenCode/Claude
  Code) with a bash tool can do this without any bespoke harness tool beyond
  openpyxl/pandas, which any Python env has.
- Cost/calls: 1 call/task (single-round) up to 5 calls/task (multi-round ReAct). At
  912 full-set or even the 200-sample subset, a single-round pass on ~50 items fits
  one day's 50-call free-model budget; multi-round (5x) caps a same-day run at ~10 items.
- Risks: xlsx cell-format comparison can be brittle to library formula-recalc quirks
  (why they built `open_spreadsheet.py`/LibreOffice recalculation step); needs LibreOffice
  installed in the container (not confirmed present — must check `soffice --version`).

## 2. DABstep (Adyen + Hugging Face, 2025)
- HF blog: https://huggingface.co/blog/dabstep (read 2026-09-25)
- HF dataset: https://huggingface.co/datasets/adyen/DABstep (read 2026-09-25)
- HF Space (baseline + scorer, cloned): https://huggingface.co/spaces/adyen/DABstep
  commit `d4431c2e4a695cbe43c33aab2adaa304a37ae64a` (2026-07-22), file
  `dabstep_benchmark/evaluation/scorer.py` (read 2026-09-25).
- Data: 450+ tasks split "easy" (single structured dataset, warm-up) / "hard"
  (multi-dataset, multi-step, needs `manual.md` business-knowledge doc + CSV/JSON
  payments data). `tasks` split has a **10-row `dev` sub-split with public gold
  answers** for local iteration; the **450-row `default` sub-split's answers are
  withheld** — the public leaderboard grades against a hidden gold set (per HF blog
  "leaderboard test set remains hidden for broad generalization").
- Grading: **fully deterministic**, no LLM judge — confirmed by reading
  `scorer.py` directly: `question_scorer()` does numeric extraction + tolerance
  compare (`math.isclose(rel_tol=1e-4, abs_tol=1e-4)` for small/percentage values,
  decimal-place-aware compare for larger numbers), list compare (split on `,`/`;`),
  and fuzzy string compare (`difflib.SequenceMatcher`) as fallback. Binary
  correct/incorrect per task.
- Official harness: baseline is `smolagents` `CodeAgent` (Hugging Face), local
  Python-sandbox code execution; HF gives free users "1k free LLM requests/day"
  via Inference API for baseline runs (separate from OpenRouter's 50/day cap).
  Agent gets a data-files directory to iteratively query/compute over (files-based,
  no external DB).
- Fit for file-workspace coding agent: **very good** — pure "here are CSVs/JSON +
  a manual.md, answer factoid questions with numbers/lists derived from them";
  the exact "invented numbers vs sourced numbers" test.
- Cost/calls: agentic multi-step (open step budget in smolagents CodeAgent, not a
  fixed cap found in this pass — unverified exact default max_steps for the
  baseline; the HF blog reports **total dollar cost per full 450-task run**
  ($2–$435 depending on commercial model), not calls/task — treat per-task call
  count as **unverified**, plan to budget conservatively, e.g. cap at 5–8 steps/task
  and run only the `dev` 10-item split or a handful of `easy` items from `default`
  (whose task text is visible even though the final gold answer isn't, so a
  small self-scored subset needs the `dev` split specifically).
- Risks: for the "installed vs not" comparison to be graded automatically without
  emailing/HF leaderboard submission, must use the **10-task `dev` split** (public
  answers) rather than submitting to the real leaderboard, since the 450-task
  gold is hidden. That's a small but genuine deterministic set.

## 3. InfiAgent-DABench (ICML 2024)
- Repo: https://github.com/InfiAgent/InfiAgent (cloned, read 2026-09-25), dataset
  subfolder `examples/DA-Agent`. Paper: arXiv:2401.05507. HF:
  huggingface.co/infiagent (released 2024/02/21, per repo README News section).
- Data: DAEval — 603 data-analysis questions over 124 CSV files total; publicly
  released **validation set = 400 questions / 72 CSV files** (`README_eval.md`,
  read 2026-09-25); a held-out **test set exists specifically "to avoid data
  leakage"** (per repo README) and its answers are not shipped in this repo —
  status of the test set beyond that line is **unverified** in this pass (need to
  check the HF `infiagent` org page for whether it's downloadable elsewhere).
- Grading: **fully deterministic**. `eval_closed_form.py` (read 2026-09-25) uses a
  "format-prompting" trick: the agent must emit its final answer as
  `@AnswerName[value]` tags; the evaluator regex-extracts (`extract_format`) and
  does exact string match or float compare within `1e-6` (`is_equal`). Multiple
  named sub-answers per question are each scored independently (their PSAQ/ABQ/UASQ
  metrics are aggregates over these booleans). No LLM judge.
- Official harness: ReAct-style pipeline in `pipeline/` (Docker-based Python
  sandbox, `pipeline/activities/eval.py`), or the simpler DA-Agent
  (`examples/DA-Agent`). Typically **1 inference call per question** in the
  single-shot closed-form setting used for `eval_closed_form.py`; the ReAct
  pipeline variant would use more (exact default steps not found in this pass —
  unverified).
- Fit for file-workspace coding agent: **good** — CSV files + a closed-form NL
  question about them (e.g. correlation, mean, categorical count); a coding agent
  can pandas its way to the tagged answer without special tooling.
- Cost/calls: as low as 1 call/task if the closed-form single-shot setting is used;
  400 public validation questions comfortably fit under 50 calls/day sampled in
  small batches over multiple days, or ~40–50 in a single day.
- Risks: license is **CC BY-NC 4.0** on the data (per repo README badge) — a
  research/demo use is fine, but note the non-commercial restriction if the
  exhibition materials get redistributed.

## 4. DA-Code (EMNLP 2024)
- Repo: https://github.com/yiyihum/da-code (cloned, read 2026-09-25). Paper:
  arXiv:2410.07331 / ACL Anthology 2024.emnlp-main.748. Site: da-code-bench.github.io.
- Data: in-repo `da_code/source` ships a **100-example sample**; the **full
  dataset (per paper, hundreds of examples)** requires downloading `source.zip`
  and a separate **`gold` directory** from two Google Drive links (public,
  `gdown`-fetchable, read from README 2026-09-25) — so gold answers are not
  literally hidden, just off-repo. Both links are public Google Drive shares, not
  gated.
- Grading: task-type-dependent via `da_agent/evaluators/evaluation.py`'s
  `Evaluator` class (`evaluate.py`, read 2026-09-25) — produces a `total_score`
  per task and a `result_type` bucket that includes "plot" (chart output) as one
  category, meaning **some tasks are graded by comparing generated
  charts/files against gold artifacts**, not purely numeric string compare;
  exact per-type metric logic (`da_agent/evaluators/`) was not read in this pass
  (weight budget) — **the plot/report-type grading mechanics are unverified**,
  everything else (data manipulation, ML metrics) is file/value diffing and looks
  deterministic from the CLI surface (`--gold_dir`, `--eval_json`, `--timeout_seconds`).
- Official harness: **requires Docker** — "agent and experiments need to run in a
  sandbox environment using Docker" (README, confirmed). Runner is `run.py`
  (agentic loop, ReAct-like), with **`--max_steps` default 20** (confirmed:
  `run.py:54`) and `--max_memory_length` default 15. Up to **20 model calls per
  task** by default.
- Fit for file-workspace coding agent: good conceptually (data wrangling/EDA/ML/
  visualization over provided files) but the **Docker sandbox + up to 20-step
  agent loop is heavier than SpreadsheetBench/InfiAgent-DABench** — better suited
  to a smaller sampled subset given the call budget.
- Cost/calls: up to 20 calls/task by default; with 50 free calls/day that's only
  **~2 tasks/day** if run to the step cap, or fewer if `--max_steps` is reduced
  (feasible to lower it — CLI-exposed).
- Risks: needs Docker (available per environment facts) but also two external
  Google Drive downloads (>100MB for full gold), and its own agent framework
  (`da_agent/`) rather than a bring-your-own-agent adapter — would need either a
  thin shim to route calls through OpenRouter or reuse da-code's own agent loop
  pointed at the OpenRouter endpoint (it already supports `AZURE_API_KEY`/
  `OPENAI_API_KEY`/`GEMINI_API_KEY` env vars — OpenAI-compatible client swap to
  OpenRouter's base_url is the natural path, needs to be confirmed against
  `da_agent`'s LLM client code, not yet read).

## 5. DSBench (ICLR 2025) — two sub-benchmarks, different determinism
- Repo: https://github.com/LiqiangJing/DSBench (cloned, read 2026-09-25). Paper:
  arXiv:2409.07703. Noted (2025/07/17) as used for OpenAI's ChatGPT-agent eval blog post.
- **5a. data_analysis** (466 tasks from ModelOff, open-ended NL/table/image tasks):
  grading in `compute_answer.py` (read 2026-09-25) is an **LLM-judge**
  (`gpt-4o-2024-05-13` prompted "output True or False") — **not deterministic**,
  fails the task's "deterministic grading" requirement even though the
  underlying task (read files, compute) is the right shape.
- **5b. data_modeling** (74 tasks from real Kaggle competitions): grading is
  **per-competition metric scripts** — repo ships 70+ files like
  `evaluation/titanic_eval.py`, `spaceship-titanic_eval.py`,
  `commonlitreadabilityprize_eval.py` etc. (listed, read 2026-09-25), each
  presumably computing the competition's own metric (accuracy/AUC/RMSE/etc. —
  not individually opened, but this is the standard Kaggle-eval pattern) via
  `score4each_com.py`. This arm **is deterministic**, closer to standard ML
  scoring, no LLM judge needed for the score itself.
- Data acquisition is the friction point: data_analysis requires downloading
  competition files from a third-party site (eloquens.com) OR a pre-packaged
  Google Drive / HuggingFace zip (`liqiang888/DSBench`); data_modeling requires
  the **Kaggle API** (needs a Kaggle account/credentials) OR the same pre-packaged
  mirrors. Both have HF mirrors that avoid needing new accounts.
- Fit for file-workspace coding agent: **data_modeling arm is a strong fit**
  (train.csv/test.csv + "beat this Kaggle metric" is exactly a read-and-compute
  task) but heavier — a full Kaggle-style pipeline (train a model) is not a
  quick few-tool-call task; realistically many tool calls (data load, EDA,
  feature eng, train, predict, submit) — no fixed step cap found in this pass
  (**unverified**), likely tens of calls per task, which would blow the 50/day
  budget on more than 1-2 tasks unless capped tightly by the calling harness (a
  wrapper agent with an explicit low max-turns would be needed).
- Cost/calls: data_analysis likely 1-3 calls/task for inference + 1 GPT-4o judge
  call (extra cost, extra dependency on a paid model for grading — inconsistent
  with the "keep everything comparable, log everything" requirement since the
  judge model differs from the agent model and is not free). data_modeling likely
  higher call count, **unverified** exact figure.

## 6. BLADE (EMNLP 2024 Findings)
- Repo: https://github.com/behavioral-data/BLADE (cloned, read 2026-09-25). Paper:
  arXiv:2408.09667. PyPI pkg `blade-bench`.
- Data: 12 dataset+research-question pairs (small; X datasets/Y MCQs per repo's
  own placeholder text, meaning the README hasn't been filled in with the final
  numeric N — from the paper it's **12 case studies**, consistent with the earlier
  websearch summary). README explicitly states **"We are working on a hold-out
  test set. Details soon!"** — as of the commit read, **the full ground truth is
  public**, no hidden test set yet.
- Grading: **hybrid, partly LLM-based** — `blade_bench/eval/llm/
  conceptual_var_similarity.py` and `model_similarity.py` (found via directory
  listing, read 2026-09-25) show the evaluator uses an LLM to match the agent's
  chosen conceptual variables/statistical model against ground truth (open-ended
  analysis choices don't reduce to exact string match), plus a separate
  deterministic `eval/metrics/calc_metrics.py` for downstream numeric metrics.
  **Not purely deterministic** — same class of concern as DSBench-data_analysis
  and DiscoveryBench.
- Official harness: `pip install blade-bench`; needs API keys for OpenAI/Gemini/
  Anthropic for the LLM parts of evaluation itself (not just the agent under
  test) — an extra paid-model dependency for grading.
- Fit for file-workspace coding agent: **moderate** — task is "given a dataset +
  open research question, write a statistically justified analysis," which is
  richer than "compute one number" and partly rewards the LLM-judged nuance
  Vacant is not meant to be grading (open-ended science judgment, not
  "did you use the file"). Less on-target than DABstep/SpreadsheetBench/
  InfiAgent-DABench for the specific "invented numbers" failure mode.

## 7. DiscoveryBench (ICLR 2025, AllenAI)
- Repo: https://github.com/allenai/discoverybench (cloned, read 2026-09-25).
  Paper: arXiv:2407.01725.
- Data: DB-REAL (hypotheses/workflows from published papers, multiple domains)
  + DB-SYNTH (synthetic). Both ship in-repo under `discoverybench/`.
- Grading: **LLM-judge**, confirmed by reading `eval/eval.py` directly — it
  imports `openai.OpenAI` and `run_chatgpt_query_multi_turn`, and
  `get_score_from_answer()` computes an F1-style score for the "var" (variable
  match) type from a **GPT-parsed JSON** (`sizeA`/`sizeB`/`intersection` fields
  the judge model itself produces) plus a binary "context" score from a
  GPT multiple-choice-style answer (`A)`/`B)`). **Not deterministic** — grading
  requires an LLM call per scored item, on top of the agent's own calls.
- Fit for file-workspace coding agent: **poor fit for the deterministic-grading
  requirement** (same reason as BLADE) even though the underlying "read data,
  derive a hypothesis" task shape is on-topic. Best treated as a "no" for this
  slate unless the study accepts LLM-judged benchmarks — the task brief says
  "deterministic grading" as the defining trait, so this is a soft exclude.

## 8. FinanceBench (2023, Patronus AI)
- Repo: https://github.com/patronus-ai/financebench (cloned, then large `pdfs/`
  dir removed locally to stay under the disk budget — the repo's own listed
  contents were still read from README/`data/` before deletion). Paper:
  arXiv:2311.11944.
- Data: **10,231 total questions**, but the open-source repo ships only a
  **150-question sample** (`data/financebench_open_source.jsonl`) with gold
  `answer` + `evidence` strings; the remaining ~10,081 questions'
  answers are **not public** (a "CLOSED_SOURCE" `dataset_subset_label` value
  exists in the schema, confirming a held-back split, per README schema section
  read 2026-09-25). Source financial PDFs (10-K/10-Q/8-K/earnings) for the 150
  questions are shipped as raw filings (was in `/pdfs/`, removed locally).
- Grading: **the paper's own methodology is human review** ("manually review
  their answers (n=2,400)" — repo README abstract, read 2026-09-25); no
  official automatic scorer.py/exact-match harness was found in the cloned repo
  (only `evaluation_playground.ipynb`, a notebook for exploring model outputs
  against gold, not a scoring pipeline) and no held-out answer-grading script —
  **this benchmark is not deterministically self-gradable out of the box**,
  which disqualifies it against this task's core requirement even though it's a
  clean "read PDFs, extract/compute a financial figure" task shape. Third-party
  repos (`VectifyAI/Mafin2.5-FinanceBench`, `aquib8112/FinanceBench_RAG`) build
  their own automatic graders (often LLM-judge) on top, which would be an
  unofficial harness, not "run exactly the way the paper/official repo runs it."
- Fit for file-workspace coding agent: task shape is a strong fit for the
  "unsourced specifics" failure mode (open financial-QA over provided 10-Ks,
  easy to hallucinate a number instead of reading the filing), but the missing
  official deterministic grader means it fails the harness requirement as
  currently released. **Exclude or deprioritize** unless the study is willing to
  build/validate its own exact-match-on-150-gold-answers scorer (feasible since
  many answers are short numeric/short-text and gold strings are public) —
  that would technically deviate from "run exactly the way the official harness
  runs it," so flag this explicitly if chosen.

## 9. Spider 2.0-lite (ICLR 2025 Oral) — checked for completeness, weak fit
- Repo: https://github.com/xlang-ai/Spider2 (not cloned — determined unsuitable
  before spending clone budget). Site: spider2-sql.github.io.
- Per README (via websearch, read 2026-09-25): full dataset access requires
  **signing up for a BigQuery account and obtaining credentials** (two required
  setup steps); recommended harness is `spider-agent-lite`/`spider-agent-snow`,
  which execute SQL against **live BigQuery/Snowflake warehouses**, not local
  files. Ground-truth tables for spider2-lite/snow are available for offline
  scoring, but running the *task* itself needs a live DB connection.
- Explicitly excluded per the task's own environment constraint ("no web forms,
  no sign-ups", "no real model API calls" plus here also "no cloud DB
  credentials") and the "file-workspace coding agent without extra tools"
  criterion — Spider2-lite needs a BigQuery/Snowflake client + account, which is
  an "extra tool" and an extra credential, not just files in a folder. **Exclude.**

## Cross-candidate summary (deterministic-grading + file-only + call-budget fit)

| Benchmark | Deterministic? | Answers hidden? | File-only (no extra creds)? | Calls/task (official default) |
|---|---|---|---|---|
| SpreadsheetBench | Yes (per-cell OJ diff) | No, all public | Yes (Docker+LibreOffice locally) | 1 (single) or ≤5 (react) |
| DABstep | Yes (scorer.py, no LLM) | Yes for 450-task `default` split; `dev`(10) public | Yes (CSV/JSON/manual.md) | unverified exact cap; budget-limit it |
| InfiAgent-DABench | Yes (`@Tag[value]` exact/1e-6) | Test set withheld ("avoid leakage"); 400-Q val set public | Yes (CSV) | ~1 (closed-form single-shot) |
| DA-Code | Mostly yes, plot-type unverified | No (gold on public Drive link) | Needs Docker sandbox | ≤20 (default max_steps) |
| DSBench-data_modeling | Yes (Kaggle metric scripts) | No | Needs Kaggle API or HF mirror | unverified, likely many (full ML pipeline) |
| DSBench-data_analysis | **No** (GPT-4o judge) | No | Needs 3rd-party/HF data mirror | ~1-3 + 1 judge call |
| BLADE | **Partly** (LLM similarity match) | No (hold-out "coming soon") | Yes, but needs judge-model API key | unverified |
| DiscoveryBench | **No** (GPT-judge in eval.py) | No | Yes (data ships in repo) | unverified + judge calls |
| FinanceBench | **No official auto-scorer** (human review) | Partial (150/10231 public) | Yes (PDFs) but no deterministic harness | n/a |
| Spider2.0-lite | Yes (SQL result diff) but needs live DB | N/A | **No** — needs BigQuery/Snowflake account | n/a |

**Recommendation ranking for the study, given "deterministic grading" +
"file-workspace agent, no extra tools" + "≤50 calls/day":**
1. **InfiAgent-DABench** — cheapest (≈1 call/task), fully deterministic, pure CSV
   files, 400 public questions to sample from.
2. **SpreadsheetBench** — deterministic OJ-style grading, all-public, cheap
   (1–5 calls/task), but needs Docker + LibreOffice in the container (must
   verify `soffice` availability before committing).
3. **DABstep** — best "realistic enterprise" flavor and genuinely hidden answers
   for the 450-task set (integrity property InfiAgent/SpreadsheetBench lack),
   deterministic scorer confirmed by reading source, but per-task call budget is
   the least well-pinned-down (unverified) — restrict to the public 10-item
   `dev` split for self-graded runs, or a hard step-cap wrapper.
4. **DA-Code** — good task diversity but Docker-sandbox + up to 20 calls/task is
   expensive against the 50/day cap; usable only at small N or with
   `--max_steps` turned down.
5. **DSBench data_modeling arm** — deterministic and on-topic but likely the
   most expensive per task (full modeling pipeline) and needs Kaggle
   credentials or a large data mirror download.
Deprioritized/exclude: DSBench-data_analysis, BLADE, DiscoveryBench (LLM-judge
grading breaks "deterministic"), FinanceBench (no official deterministic
scorer), Spider2.0-lite (needs a live cloud DB + signup, violates "file
workspace, no extra tools / no sign-ups").

## Addendum 2026-09-25 (later pass): published small-open-model (<=35B) scores

Sourced via WebFetch on arXiv HTML mirrors + WebSearch, read 2026-09-25.

- **InfiAgent-DABench** (arXiv:2401.05507, Table 6, agent framework w/ format-reformatting
  step enabled — closed-form eval): Qwen-72B-Chat 59.92% / Qwen-14B-Chat 37.50% /
  Qwen-7B-Chat 27.27% / Mistral-7B-Instruct-v0.2 38.67% / Baichuan2-13B-Chat 9.34% /
  Baichuan2-7B-Chat 8.95% / CodeLlama-34B-Instruct 31.13% / CodeLlama-13B-Instruct
  26.67% / CodeLlama-7B-Instruct 24.61% / DeepSeek-Coder-33B-Instruct 46.09% /
  Phind-CodeLlama-34B-v2 43.87%. Everything ≤35B here is well below GPT-4's 78.99%
  quoted elsewhere in the paper — the smallest local-like sizes (7-14B) land 27-46%.
- **DA-Code** (arXiv:2410.07331, Table 3): the only ≤35B rows are Deepseek-Coder-33B
  (overall 10.8%, completion rate 31.9%, DW 9.1% / ML 22.1% / EDA 7.6%) and
  Mixtral-8x22B (overall 15.4%, completion 67.2%). Qwen2.5-72B-Instruct (22.6% overall)
  and Deepseek-Coder-V2.5 (20.7%) are both >35B/MoE-large, included for contrast only.
  Confirms small local-like models complete under a third of DA-Code tasks at all.
- **DABstep** (arXiv:2506.23719, "Table 1: Performance of baseline models... (Hidden
  Test Set)"): only two Llama rows appear — Llama 3.3 70B (Hard 3.70%, Easy 68.06%,
  >35B, included for contrast) and **Llama 3.2 1B (Hard 0.00%, Easy 1.39%)**, i.e. the
  one truly small open model tested scores essentially zero on Hard and near-zero on
  Easy. No Qwen/Gemma/Mistral row found in this table — **unverified whether other
  small open models were benchmarked**; the official leaderboard Space
  (huggingface.co/spaces/adyen/DABstep) may have community submissions not captured
  by this pass (page loaded but did not render a static results table via WebFetch).
- **SpreadsheetBench**: the *original* NeurIPS'24 paper's own results table for
  open-source ≤35B models was **not confirmed in this pass** (WebFetch only returned
  the arXiv abstract, not full table text) — treat GitHub `README`/paper Table numbers
  as unverified pending a direct read of the PDF/HTML body. A **separate, newer** paper,
  Spreadsheet-RL (arXiv:2605.22642, 2026), reports baseline Pass@1 for open Qwen3
  models — **Qwen3-4B-Instruct-2507 / Qwen3-4B / Qwen3-8B / Qwen3-14B / Qwen3-32B in the
  9.3-17.6% Pass@1 range**, and shows RL post-training moving Qwen3-4B-Thinking-2507
  from 12.0% to 23.4%. **Caveat, unverified**: this may be scored on SpreadsheetBench-2
  (arXiv:2606.29955, the harder successor benchmark also from 2026) rather than the
  original SpreadsheetBench this candidate targets — the two benchmarks were not
  cross-checked in this pass; do not cite the 9.3-17.6% figures as "the same benchmark"
  without confirming which paper's harness produced them.
- **DSBench, BLADE, DiscoveryBench, FinanceBench, Spider2.0-lite**: no small-open-model
  (≤35B) published score table was located in this pass — **unverified / not found**,
  consistent with these being the deprioritized/excluded candidates (LLM-judge grading
  or missing official scorer or needs a live DB), so no further search budget was spent
  chasing their leaderboards.
