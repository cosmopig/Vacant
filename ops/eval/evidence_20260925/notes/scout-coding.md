# scout-coding — coding-agent benchmarks (read 2026-09-25)

Repos cloned --depth 1 into scratchpad/study/src/: harbor, mini-swe-agent, SWE-bench,
multi-swe-bench, evalplus, polyglot-benchmark, LiveCodeBench. All read locally, no
downloads >1GB (du -sh: harbor 141M, SWE-bench 9.6M, mini-swe-agent 3.2M,
multi-swe-bench 31M, evalplus 2.1M, polyglot-benchmark 36M, LiveCodeBench 8.2M).

## Big finding: Harbor (harbor-framework/harbor, cloned) is a single harness that
already wraps pi, OpenCode, Claude Code AND Codex as first-class "installed agents"
(src/harbor/agents/installed/{pi,opencode,claude_code,codex}.py all exist and are
real, non-stub implementations — confirmed by reading pi.py: wraps
`@earendil-works/pi-coding-agent` npm package with MCP adapter support, ModelRun
config injection etc.) — plus aider.py, mini_swe_agent.py, swe_agent.py,
gemini_cli.py and ~30 more. registry.json (80 published datasets, read locally)
already includes ready-to-run rehosted copies of: swebench-verified (500),
swebench_multilingual (300), swebenchpro (731), terminal-bench 2.0 (89),
terminal-bench-sample 2.0 (10), terminal-bench-pro (200), aider-polyglot (225),
livecodebench v6.0 (100-task subset), humanevalfix (164, not EvalPlus). Source:
harbor-framework/harbor repo root, files `registry.json`, `src/harbor/agents/installed/*.py`,
read 2026-09-25 (git commit at clone time, see `harbor/.git`).

---

## 1. SWE-bench Verified / Lite (official, SWE-bench/SWE-bench repo, cloned)
- Official harness: `python -m swebench.harness.run_evaluation`, Docker-based,
  3-layer images (base / ~60 env images / one instance image per task).
  Source: SWE-bench/README.md lines 39-126 (read locally).
- Official disk/RAM/CPU recommendation, verbatim from README.md line 123:
  "We recommend running on an x86_64 machine with at least 120GB of free storage,
  16GB of RAM, and 8 CPU cores." We have 15GB RAM / 4 CPU / ~18GB disk shared —
  fails the disk requirement outright even before any other agent's usage.
- Image size: originally ~2000GB for all 2294 images; Epoch AI's layer-cache
  optimization brought the registry to 67GiB (all 2290) / 30GiB (500 Verified only).
  Source: Epoch AI, "How to run SWE-bench Verified in one hour on one machine",
  https://epoch.ai/latest/swebench-docker (read via WebSearch snippet 2026-09-25).
  Even optimized, 30GiB > our whole disk budget; a hand-picked 5-10 instance subset
  from 1-2 repos (sharing base+env layers) could plausibly fit in a few GB but
  this needs a real trial, not assumed.
- Official/canonical scaffold: SWE-bench's own **mini-swe-agent**
  (SWE-agent/mini-swe-agent, cloned) — "100-line" bash-only agent, no tool-calling
  API needed, works with literally any model via a linear message history. This is
  the harness behind the "SWE-bench (bash only)" leaderboard, where the scaffold is
  held fixed and only the model varies. Source: github.com/SWE-agent/mini-swe-agent
  README (cloned; also stated in WebSearch result for "mini-swe-agent SWE-bench
  bash-only leaderboard", 2026-09-25). Does NOT natively run pi/OpenCode/Claude
  Code/Codex as themselves — only via Harbor's rehosted `swebench-verified` dataset
  (500 tasks, parity-checked: mini-swe-agent@2.1.0+gpt-5-mini matches official on a
  10-task seed-42 subsample per harbor/adapters/swebench/adapter_metadata.json,
  read locally 2026-09-25).
- Small open-weight scores (aggregator, NOT independently verified against
  swebench.com's own leaderboard page — flagging as unverified-but-directionally
  useful): Qwen3-Coder-30B-A3B-Instruct 60.4% ("best on the efficiency frontier at
  its size"), IBM Granite 4.2 8B 47.7%. Source: BenchLM.ai SWE-bench Verified
  leaderboard, via WebSearch snippet dated Sept 2026, read 2026-09-25 — could not
  open the live page directly in the time budget, treat as secondary source.
- Caveat found in passing: OpenAI's Frontier Evals team reportedly stopped
  reporting SWE-bench Verified in Feb 2026 over contamination concerns (WebSearch
  snippet, unverified primary source — flag as "unverified" per instructions).

## 2. SWE-bench-Live (microsoft/SWE-bench-Live, NOT cloned — read via WebSearch only)
- Auto-updating, decontaminated (issues sourced after model release dates),
  multi-language + multi-OS. As of the snippets read: MultiLang split 1077
  instances / 431 repos / 8 languages; Windows split 66 instances / 48 repos.
  Source: github.com/microsoft/SWE-bench-Live + swe-bench-live.github.io, read via
  WebSearch 2026-09-25 (dates "08/03/2026" Windows release, "10/01/2026" MultiLang
  release as stated on the project's own site — note the MultiLang date is in the
  future relative to today 2026-09-25 per the site's own copy, so treat that
  specific split as "announced/rolling out", not necessarily runnable today;
  flagging the inconsistency rather than resolving it).
- Same per-instance-Docker-image lineage as SWE-bench (a fork, SWE-rebench/
  SWE-bench-fork, is used to build/run its instances) — same disk-size risk profile
  as #1, not independently measured for this dataset.
- Not present in Harbor's registry.json (checked programmatically: no name
  containing "live"). Would need a custom pi/OpenCode/Claude Code/Codex wrapper
  (e.g. adapt mini-swe-agent) — no ready-made installed-agent integration found.

## 3. SWE-rebench (Nebius, nebius/SWE-rebench on HF, NOT cloned — WebSearch only)
- Continuously refreshed with fresh GitHub issues per model's release date
  specifically to prevent contamination; leaderboard marks pre-release-date issues
  as "potentially contaminated". This directly matches the repo's own concern
  ("不能對觀眾說錯話" / must not misstate novelty or correctness to a lay
  audience) — SWE-rebench's contamination bookkeeping is the most rigorous of the
  candidates found. Source: swe-rebench.com/about + nebius.com blog "Behind
  SWE-rebench", read via WebSearch 2026-09-25.
- Leaderboard snapshot (2026-09-22, aggregator BenchLM, unverified against
  swe-rebench.com directly): Claude Opus 4.6 65.3%, GLM-5 62.8%, GLM-5.1 62.7%.
  Models evaluated 5x per problem under a **fixed ReAct scaffold**; did not find a
  small-open-weight (<35B) row in the time available — unverified for our target
  model class.
- Uses the **stock SWE-bench harness** (`python -m swebench.harness.run_evaluation`)
  against nebius/SWE-rebench's own dataset, with 7500 **prebuilt** Docker images
  hosted on Docker Hub (swerebench org) — no local image build needed, but still
  per-instance pull, same disk profile risk as #1/#2. Official example scaffold:
  mini-swe-agent 1.14.4 (comparable results to SWE-Agent for some models). Source:
  HF discussion "How to build docker image for each instance?" on
  nebius/SWE-rebench, + nebius/SWE-rebench-leaderboard README, read via WebSearch
  2026-09-25.
- A Harbor adapter PR exists (harbor-framework/harbor#1347, "Adapter: swe-rebench"
  by delphikettle) but is NOT yet in the registry.json we read locally (80 names
  checked programmatically, none match "rebench") — treat as "in review", not
  runnable via `harbor run --dataset` today.

## 4. Multi-SWE-bench (mini / flash) — ByteDance-Seed, multi-swe-bench/multi-swe-bench
(cloned, 31M)
- Docker-based, own per-instance images, downloadable via
  `scripts/download_images.sh` with a choice of "mini and verified" or "RL" image
  sets (README.md lines 61-179, read locally) — same category of disk risk as
  SWE-bench, size of the "mini" image set not established in the time budget
  (would need to actually run download_images.sh --dry or read the script, not
  done — flag as unmeasured, not "small").
- Multi-SWE-bench_mini (HF dataset, ByteDance-Seed): 400 instances, 50 per language
  across 8 languages (Python, Java, TS, JS, Go, Rust, C, C++), easy/medium/hard
  split. Source: huggingface.co/datasets/ByteDance-Seed/Multi-SWE-bench_mini card,
  read via WebSearch 2026-09-25.
- Harbor HAS an adapter directory for it (`harbor/adapters/multi-swe-bench/`, read
  locally) but it is NOT in registry.json's 80 published datasets — so it exists as
  in-repo adapter code (full split 1632 tasks; parity subset 70 tasks, 10/language)
  but isn't a one-command `harbor run --dataset` yet. Its own supported agents per
  the adapter metadata are reimplementations ("mopenhands", "msweagent", "mcodex" —
  "Agent mcodex wraps the OpenAI Codex CLI"), not pi/OpenCode/Claude Code natively.
  Source: harbor/adapters/multi-swe-bench/adapter_metadata.json, read locally
  2026-09-25.
- No small-open-weight-model published scores found for Multi-SWE-bench mini/flash
  specifically in the time budget — unverified, not claiming a number.

## 5. SWE-bench Pro (Scale AI, scaleapi/SWE-bench_Pro-os) — NOT cloned, WebSearch +
Harbor registry read locally
- Long-horizon, harder-than-Verified tasks in a "locked protocol" (offline agent
  phase, fresh-sandbox re-grading) meant to resist the grading leakage seen on
  Verified/Pro v1. V2 (2026-09-22) has 642 validated tasks (go 256, python 237,
  js 145, ts 4) under Harbor format, plus a HARD-51 subset. Source:
  morphllm.com/swe-bench-pro (Sept 2026 aggregator) + arxiv 2609.08149 "SWE-Bench
  Pro Verified: A Reliable Benchmark for Software Engineering Agents" (title read
  via WebSearch, not the PDF itself — flag as title-only, unread).
- Harbor's own registry.json (read locally) lists `swebenchpro` v1.0 with 731
  tasks — a different count than the "642 V2" figure from the aggregator; this is
  a real discrepancy between sources found, not resolved (could be v1 vs v2
  snapshots) — flagging rather than picking one.
- **Grading-quality risk, important for a public "installed vs not" comparison**:
  a third-party audit (Datacurve, cited by morphllm.com, "May 2026 DeepSWE audit")
  reportedly found SWE-bench Pro's automatic graders mis-scored ~1/3 of trials
  (8.5% false accepts, 24% false rejects) and that some frontier models were
  flagged "CHEATED" on >12% of reviewed tasks for reading gold solutions out of
  the repo's own .git history. This is a single aggregator's summary of a claimed
  third-party audit — NOT independently verified in the time budget — but if true
  it would undermine using SWE-bench Pro for a rigorous "no difference except
  Vacant" comparison, since grader noise could swamp any Vacant effect. Flag as a
  real risk to check before committing to this benchmark.
- Published small-open-weight score: "Qwen3.8-Flash-Next leads open weights at
  62.5%" per morphllm.com — parameter count for "Qwen3.8-Flash-Next" not stated in
  the snippet, unverified whether it is small enough to match our free-tier class.

## 6. Terminal-Bench 2.0 (via Harbor — harbor-framework/harbor, cloned; also
harbor-framework/terminal-bench-2, laude-institute/terminal-bench-2-0-sample, NOT
cloned separately, read via Harbor's registry.json task-list pointers)
- Harbor **is** the current official framework/harness for Terminal-Bench 2.0 (the
  Terminal-Bench team built Harbor specifically for this; tbench.ai/news/
  announcement-2-0, read via WebSearch 2026-09-25). Harbor's registry.json (read
  locally) has three ready datasets: `terminal-bench` v2.0 (89 tasks),
  `terminal-bench-sample` v2.0 (10 tasks — good fit for the 50-call/day budget),
  `terminal-bench-pro` v1.0 (200 tasks).
- **Confirmed native adapters for ALL FOUR target agents** — this is the
  candidate with the best harness/agent fit for Vacant's four-agent scope. Ready
  command form per harbor docs: `harbor run --dataset terminal-bench@2.0
  --agent claude-code --model <id>`; same `--agent` flag accepts `pi`, `opencode`,
  `codex` per the installed-agent files read locally (src/harbor/agents/installed/
  {pi,opencode,codex,claude_code}.py all exist and are fully implemented, not
  stubs — pi.py alone is >150 lines wiring `@earendil-works/pi-coding-agent`,
  MCP adapter injection, and a max-turns extension). Source: files read locally
  2026-09-25 + harborframework.com/docs/adapters (WebSearch, "Adapters (Agent
  Guide) - Harbor").
- Small-open-weight scores are near-floor: Qwen3-8B ~2.5%, GPT-OSS-20B ~3.1%
  (BenchLM.ai Terminal-Bench 2.0 leaderboard, Sept 2026 — unverified against
  llm-stats.com/benchmarks/terminal-bench-2 directly, only read via WebSearch
  snippet). Top model GPT-5.5 at 82% for scale. **Implication for Vacant's own
  claim** (not a benchmark fact, a design note): Terminal-Bench 2.0 tasks are hard
  enough that our free-tier ~2-30B models will resolve very few of them outright —
  but Vacant's claim is about catching *unjustified intermediate steps / false
  "done" claims*, which should if anything be MORE frequent on a benchmark this
  hard for a weak model, not less. A near-floor resolve-rate does not by itself
  disqualify Terminal-Bench 2.0 for Vacant's purpose, but it does mean "resolved
  rate with vs without Vacant" will likely show near-zero on both arms and any
  visible improvement will have to be shown some other way (e.g. rate of caught
  ungrounded claims, or step-count to a correctly-flagged failure).

## 7. Aider Polyglot (Aider-AI/polyglot-benchmark data repo, cloned 36M; harness
itself lives in the separate Aider-AI/aider repo, not cloned)
- 225 hardest Exercism exercises across C++, Go, Java, JavaScript, Python, Rust.
  No Dockerfile in the data repo (verified: `find polyglot-benchmark -iname
  Dockerfile` → empty) — the official Aider benchmark script runs each language's
  native toolchain locally (needs go/rustc/javac/node/python installed, not just
  docker), or can be sandboxed manually; lighter disk footprint than SWE-bench
  (36MB for the whole task corpus).
- Also present as a **ready Harbor dataset**: `aider-polyglot` v1.0, 225 tasks,
  rehosted via harbor-datasets git repo (registry.json, read locally) — runnable
  through the same installed-agent adapters (pi/OpenCode/Claude Code/Codex) as
  Terminal-Bench 2.0 above, which is a second strong option for full four-agent
  coverage.
- Published small-open-weight numbers found: (a) official leaderboard — top
  open-source is DeepSeek-V3.2-Exp at 74.5% (not small, ~671B MoE); (b)
  **unofficial** self-reported run: "Qwen3.6-35B-A3B Q8 (Tongyi Lab, Apache 2.0)
  hit 62.2% on Aider Polyglot running locally on a MacBook Pro M5 Max" —
  llmkube.com blog post, NOT the official aider.chat leaderboard, flag as
  unverified/anecdotal but directionally useful since it is exactly our target
  model class (Apache-2.0, ~35B, local-quantized). Source: aider.chat/2024/12/21/
  polyglot.html (official leaderboard, superseded by newer entries per llm-stats.com/
  benchmarks/aider-polyglot, "last updated September 2026, 22 evaluated models")
  + llmkube.com/blog/m5-max-aider-polyglot-and-finops, both read via WebSearch
  2026-09-25.
- Known Aider-specific caveat (not independently re-verified here, general
  knowledge of the benchmark's design): weak/small instruction-following models
  often fail Aider Polyglot on **edit-format compliance** (diff/SEARCH-REPLACE
  syntax) rather than on the underlying coding logic — worth watching for with
  2-30B free models, since a format failure would look like "model produced wrong
  code" when it is really "model can't emit the edit format", a different failure
  mode than what Vacant's accountability layer is built to catch.

## 8. LiveCodeBench (LiveCodeBench/LiveCodeBench, cloned 8.2M)
- Pure competitive-programming-style code generation + hidden-test execution,
  **not** an agent-in-a-repo benchmark — no multi-step tool use, no files to
  read, no terminal. Confirmed: pip-installable (`uv pip install -e .`, README.md
  line 39, read locally), no Docker requirement found in README. Also present as
  a Harbor dataset (`livecodebench` v6.0, 100-task subset, registry.json read
  locally) if agent-wrapped generation is wanted, but the benchmark's own design
  is single-turn.
- **Fit note**: because there's no repository to explore, no logo/schedule/data
  folder analog, LiveCodeBench structurally cannot exercise Vacant's core claim
  (catching steps not justified by materials in a task folder) — a single
  generate-and-test call has nothing to skip reading. Lower priority for Vacant's
  demonstration relative to Terminal-Bench 2.0 / Aider Polyglot / SWE-bench-family,
  though it's cheap and could serve as a "no Vacant advantage expected here"
  negative control if the study wants one.
- Version note: LiveCodeBench keeps rolling release windows to fight
  contamination (problems tagged by date); "v6.0" is Harbor's snapshot label, the
  live/official site continues to add releases — did not pin an exact release
  date for "the newest version" beyond what's in Harbor's registry.

## 9. EvalPlus / HumanEval+ / MBPP+ (evalplus/evalplus, cloned 2.1M) — already used
inside this repo
- **Already integrated into Vacant** at `vacant_network/codebench.py`
  (`EvalPlusMBPPLoader`, 378 questions sha256-pinned per this repo's own
  CLAUDE.md) — so this candidate has zero integration cost for pi/OpenCode/Claude
  Code/Codex wrapping questions, only for wiring the *harness's* grading into the
  Vacant accountability loop, since EvalPlus itself is not an "agent in a
  terminal" harness.
- Confirmed: pip-installable, Docker optional only for sandboxing generated-code
  execution (`docker run ... ganler/evalplus:latest`, README.md lines 92-134, read
  locally) — not required to run the benchmark, lightest disk footprint of all
  candidates here.
- Same structural fit issue as LiveCodeBench: single-turn function-completion,
  not a multi-file repo task — doesn't exercise "did the agent read the materials
  in the folder" the way a repo/terminal benchmark does, unless EvalPlus problems
  are wrapped in an agentic loop (open a file, run tests, iterate) rather than
  used as plain one-shot generation.
- Small-model numbers found in the repo's own README/docs are old-generation
  (Mistral-7B 23.8%/42.1% HumanEval+/MBPP+, Gemma-7B 20.1%/43.4%, Gemma-1.1-7B-
  Instruct 35.4%/45.0%, StarCoder2-7B, DeepSeek-Coder-6.7B) — these read as
  2023/2024-vintage entries, NOT current for 2026 model generations (our actual
  free-tier candidates like gemma-4-26b-a4b or qwen3.8-27b are not on this list).
  Did not fetch the live evalplus.github.io/leaderboard.html page in the time
  budget to get current 2026 rows — flag as a gap, not fabricating current numbers.

---

## Cross-cutting observations for the lead

- **Harbor is the strongest lead for "zero extra agent-wiring cost"**: it already
  ships working, non-stub adapters for pi, OpenCode, Claude Code AND Codex, plus
  ready-to-run rehosted datasets for Terminal-Bench 2.0 (full/sample/pro),
  Aider Polyglot, SWE-bench Verified, SWE-bench Multilingual, SWE-bench Pro, and
  LiveCodeBench — covering 6 of the 9 candidates scouted through one harness and
  one CLI (`harbor run --dataset <name> --agent <pi|opencode|claude-code|codex>
  --model <id>`). This does not remove the disk/Docker cost of the underlying
  per-instance environments (still real containers), but removes essentially all
  of the "does the harness know how to drive pi?" integration work.
- **Docker/disk is the binding constraint for the whole SWE-bench family**
  (Verified, Lite, -Live, -rebench, Multi-SWE-bench, Pro): every one of them uses
  per-instance repository Docker images, and the *official* SWE-bench README
  itself recommends 120GB free storage — 6-7x our entire ~18GB shared disk budget,
  before even accounting for other agents in this container sharing that budget.
  A hand-picked few-instance subset from 1-2 repos is the only way any of these
  runs locally here; that needs to be trialed, not assumed.
- **Terminal-Bench 2.0 sample split (10 tasks) and Aider Polyglot (225 tasks, no
  Docker) are the two most "runs today, in this container" candidates** given the
  4 CPU / 15GB RAM / ~18GB disk / no-GPU / 50-free-calls-per-day constraints —
  both have ready Harbor datasets and native pi/OpenCode/Claude Code/Codex
  adapters, and Aider Polyglot needs no Docker at all if run outside Harbor.
- **LiveCodeBench and EvalPlus are cheap but structurally the wrong shape** for
  demonstrating Vacant's specific claim (accountability for *steps*, grounding in
  *materials in a folder*) since both are single-turn code completion with no
  repo/terminal for an agent to explore — better suited as a "control" or a
  cheap smoke test than as the headline comparison.
- **SWE-bench Pro's grading-quality risk** (claimed ~1/3 mis-graded trials, claimed
  gold-solution leakage via .git history) is the single biggest red flag found
  for using any one benchmark as *the* "installed vs not" demonstration — if true
  of the version actually run, grader noise could dominate any Vacant-attributable
  effect. This was read from a secondary aggregator citing a third-party audit,
  not the primary audit report itself; verify against the primary source before
  relying on it.
- Number of candidates covered: 9 (SWE-bench Verified/Lite family, SWE-bench-Live,
  SWE-rebench, Multi-SWE-bench, SWE-bench Pro, Terminal-Bench 2.0, Aider Polyglot,
  LiveCodeBench, EvalPlus) — exceeds the "at least 6" ask.
- Everything above not explicitly marked "read locally" (repo files, registry.json,
  READMEs in the cloned repos under scratchpad/study/src/) came from WebSearch
  result snippets dated/read 2026-09-25; several of those snippets are themselves
  third-party aggregators (BenchLM.ai, morphllm.com, llm-stats.com, llmkube.com)
  rather than the primary leaderboard/paper pages — each such fact above is
  labeled "unverified" or "aggregator" inline. I did not fetch the primary
  leaderboard pages directly (evalplus.github.io/leaderboard.html,
  swebench.com, tbench.ai, aider.chat, swe-rebench.com) beyond what WebSearch's
  snippet tool returned — a follow-up pass with WebFetch on those specific pages
  would firm up the numbers flagged "unverified" here.
