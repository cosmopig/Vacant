# scout-knowledge — knowledge-work / office benchmarks (read 2026-09-25)

Goal: closest public analogue of "agent given files (logo, schedule, data) and must
produce a deliverable that uses them" — for testing Vacant's zero-config
accountability loop with FREE OpenRouter models (50 free-model calls/UTC-day cap,
per scratchpad/study/MODELS.md) against pi/OpenCode/Claude Code/Codex.

No repo >1GB cloned. deep_research_bench cloned --depth 1 (200M, code+results only,
no big media). All others read via WebSearch/WebFetch (primary sources: paper PDF,
official repo README, HF dataset page, leaderboard site), dates as read 2026-09-25.

---

## 1. GDPval (OpenAI) — most literal match to the prompt's own example, but grading is NOT local
- Paper: https://cdn.openai.com/pdf/d5eb7428-c4e9-4a33-bd86-86dd4bcf12ce/GDPval.pdf ,
  also arXiv:2510.04374. Dataset: https://huggingface.co/datasets/openai/gdpval
  (2.29 GB, "Release GDPval v2 (rubrics + deliverables)", org page + commit log,
  read 2026-09-25).
- Task shape: 220 "gold subset" tasks (5 per occupation × 44 occupations, top 9
  GDP-contributing sectors), each = realistic prompt + reference files (spreadsheets,
  PDFs, slide decks, audio/video, CAD) + context, reflecting real deliverables from
  experienced professionals. 17 reference files in gold subset / 38 in full set
  (per gdpval.pro/gdpval-resources, read 2026-09-25) — this is the single closest
  public analogue to "logo + schedule + data in a folder, write the plan."
- Grading: PRIMARY metric is blind human-expert pairwise comparison (same-occupation
  professionals). An experimental "automated grader" exists but is a HOSTED SERVICE,
  not local code: per the community harness (UKGovernmentBEIS/inspect_evals gdpval
  page, https://ukgovernmentbeis.github.io/inspect_evals/evals/gdpval/, read
  2026-09-25) — "pairwise comparisons against a golden set of human solutions, using
  **GPT-5** with a variety of tools," graded 3x for variance, 95% CI via bootstrap —
  results must be **uploaded to HuggingFace and submitted through OpenAI's website**
  (evals.openai.com/gdpval/grading) to get a score; there is no offline/local
  grading path. Agreement with human raters on gold subset ≈66% (within 5pp of
  human inter-rater agreement) per OpenAI's own gdpval.pro resources page.
- Official/community harness: `inspect-evals[gdpval]` (Inspect AI). Supports
  arbitrary tool-calling `Solver`s (bash+python tools, Docker sandbox), agent step
  count unbounded/agent-driven. Docker image build ~10 min; ran fine on a
  t3.2xlarge (8 vCPU/32GB) — no number given for our 4CPU/15GB box.
- Feasibility verdict for this study: **poor fit despite being the best conceptual
  match.** (a) grading judge is GPT-5, not free/open, not reachable without an
  OpenAI-side submission step — cannot be run offline/air-gapped for the exhibition
  or for a same-day free-tier study; (b) agent-side call count per task is
  unbounded (tool-calling loop over multi-file, multi-MB deliverables) — a handful
  of tasks could burn the whole 50-calls/day free budget; (c) even reference files
  alone are large (audio/video/CAD) — not something a 2.6B–31B free model would
  meaningfully consume. Could still be **read for task design** (their prompt
  style) without running it.

## 2. TheAgentCompany (TAC) — best "digital worker in a company" analogue, but Docker-heavy
- Paper: NeurIPS 2025 D&B track, https://papers.nips.cc/paper_files/paper/2025/file/0d744742f6fac4d1134c019b7cef3c8a-Paper-Datasets_and_Benchmarks_Track.pdf .
  Repo: https://github.com/TheAgentCompany/TheAgentCompany (README read 2026-09-25
  via WebFetch).
- Task shape: 175 tasks across 6 roles (SWE, PM, Data Scientist, HR, Finance,
  Admin) inside a simulated company: local workspace + intranet running real
  GitLab, ownCloud, Plane, RocketChat instances the agent must browse/use/message
  through. This is the closest analogue to "office environment with real
  data/tools," not just files in a folder.
- Grading: per-task Docker image, `/utils/eval.py` runs both deterministic checks
  and encrypted (`.enc`, key-gated) LLM-based sub-checkpoint evaluators; dual-layer
  (final-result + partial-credit subcheckpoints).
- Requirements (from README, verbatim): "30+ GB of free disk space," baseline
  tested on EC2 t3.2xlarge. Docker + docker-compose mandatory for the 4 intranet
  services. **30GB alone exceeds our ~18GB total shared disk budget** — a
  full run is out; a hand-picked 1-3 task subset (skipping services a given task
  doesn't touch) would need to be measured, not assumed.
- Agent compatibility: first-class OpenHands integration; framework is
  container-based so in principle any CLI agent that can reach the intranet's
  exposed ports could be pointed at it, but there is no documented pi/OpenCode/
  Claude Code/Codex adapter (would need to write one, similar to what Harbor does
  for coding benchmarks per scout-coding notes).
- Feasibility verdict: strong conceptual fit (multi-app, real data, a company
  environment) but disk budget is the hard blocker as scoped; only viable with a
  radically pruned custom subset and non-trivial adapter work.

## 3. OfficeBench — lighter, fully local, deterministic grading (best budget fit)
- Repo: https://github.com/zlwang-cs/OfficeBench (read 2026-09-25). Paper:
  arXiv:2407.19056 ("OfficeBench: Benchmarking Language Agents across Multiple
  Applications for Office Automation").
- Task shape: 300 tasks (single/two/three-application scenarios) across Word,
  Excel, PDF, email, calendar; agent must chain operations across apps to satisfy
  a workflow (closest thing here to "use the logo file, the schedule file, and the
  data file together").
- Grading: **no LLM judge** — Exact Matching / Fuzzy Matching / Execution-based
  Evaluation only, fully local/deterministic. Best-known baseline: GPT-4o at
  47.00% pass rate (their own paper's headline number, i.e. hard even for a
  frontier model — leaves visible headroom for a free small model to be worse,
  which is exactly what a "no Vacant vs with Vacant" comparison wants).
- Requirements: repo README doesn't give explicit disk size; setup is
  conda + config files (OpenAI/Gemini/vLLM) + Docker for the app sandboxes; not
  confirmed whether it accepts an arbitrary CLI agent vs. requiring a specific
  agent-loop scaffold (README language: "operations from multiple applications"
  within a "transition system" suggests it drives the agent action-by-action
  itself, i.e. it is closer to an evaluation harness the agent's actions get
  fed into, not a place where you drop in pi/OpenCode as a subprocess). **Needs a
  closer read of the actual agent-interface code before assuming pi/OpenCode/
  Claude Code/Codex can be wired in as-is** — flagging as unverified, not
  confirmed compatible.
- Feasibility verdict: best grading-cost fit of the group (zero judge-model calls
  needed at all — the whole 50/day free-model budget goes to the agent under
  test, none of it to grading) but agent-interface compatibility with our 4 target
  harnesses is unverified and needs code-level confirmation, not just README.

## 4. OdysseyBench (microsoft/OdysseyBench) — OfficeBench's long-horizon sequel
- Repo: https://github.com/microsoft/OdysseyBench . Paper: arXiv:2508.09124
  ("OdysseyBench: Evaluating LLM Agents on Long-Horizon Complex Office Application
  Workflows"); OpenReview: https://openreview.net/forum?id=tMbmBCfSTz . Read via
  WebSearch snippets 2026-09-25 (not independently WebFetched in depth this pass).
- Task shape: two splits — OdysseyBench+ (300 tasks from real use cases) and
  OdysseyBench-Neo (302 newly synthesized) — same app surface as OfficeBench
  (Word/Excel/PDF/Email/Calendar) but requiring the agent to pull essential
  context out of a **long-horizon interaction history** (i.e. simulates a worker
  who has to remember earlier context, not just a single fresh file drop). Builds
  directly on OfficeBench's codebase per its own description.
- Grading / requirements: not independently verified this pass (would need the
  same code-level read as OfficeBench above — flag as unverified).
- Relevance to Vacant: this is the one candidate whose stated angle (agent memory
  across a long-horizon workflow) most directly overlaps with Vacant's own
  cross-step trace/accountability concept — worth a second pass if OfficeBench's
  agent-interface turns out to be usable, since Odyssey is literally "OfficeBench
  + the part Vacant cares about (did you actually use what came before)."

## 5. GAIA (Meta/HuggingFace/AutoGPT team) — deterministic grading, well-known, gated dataset
- Paper: arXiv:2311.12983. Dataset: https://huggingface.co/datasets/gaia-benchmark/GAIA
  (110MB total per HF page, read 2026-09-25). Leaderboard:
  https://huggingface.co/spaces/gaia-benchmark/leaderboard .
- Task shape: 466 questions across 3 difficulty levels (166 validation + 300 test);
  many require opening an attached file (PDF, CSV, audio, image, zip) plus
  web/tool use to answer a short factual question — "easy for a competent human,
  hard for an AI that must actually use tools." This is a real "given materials,
  produce a grounded answer" task, though the deliverable is a short answer string,
  not a document — a weaker analogue to "write the marketing plan" than GDPval/
  OfficeBench/TAC, but far cheaper to grade.
- Grading: **quasi exact-match, fully deterministic, no judge model at all.**
  Validation split (166) has public answers, usable for local scoring; test split
  (300) is leaderboard-only with hidden answers.
- Requirements: 110MB total, one dataset download — trivially within budget. Access
  is **gated on HuggingFace** — user must accept a "don't reshare outside a gated
  private repo" agreement before downloading. This brushes against the task's "no
  sign-ups" constraint; flagging as a process risk to raise with the lead rather
  than something to click through unilaterally.
- Agent compatibility: any tool-using agent works (no fixed scaffold); this is the
  candidate best suited to pi/OpenCode/Claude Code/Codex with zero adapter work,
  since it's just "give the agent the attached file + question, read the answer
  string back."
- Feasibility verdict: strong budget/complexity fit (deterministic grading = zero
  judge cost, small download, no scaffold lock-in); main open item is the HF gating
  agreement and that answers are short strings rather than rich deliverables (less
  visually compelling for an exhibition side-by-side than a document/plan would be).

## 6. AssistantBench — closed-form web-agent answers, held-out test set
- Site: https://assistantbench.github.io/ . Paper: arXiv:2407.15711 /
  ACL 2024 Findings (aclanthology.org/2024.emnlp-main.505). Read via WebFetch +
  WebSearch 2026-09-25.
- Task shape: 214 tasks (33 dev / 181 test) — realistic, time-consuming web tasks
  (e.g. monitor a real-estate market, find nearby businesses) requiring live
  browsing, not local files — this is the weakest match to "materials given in a
  folder" of the group; it's closer to open-web research than office-document work.
- Grading: closed-form answers, automated scoring (accuracy/answer-rate/precision/
  exact-match), but **test-set answers are held out**; only the 33-task dev split
  has public answers for local scoring. No model has topped 26% accuracy per the
  paper's own headline (i.e., hard even for frontier systems — same "visible
  headroom" property as OfficeBench).
- Requirements: needs live internet access (through our HTTPS proxy) to real,
  changing websites — time-consuming tasks by design, so wall-clock and free-model
  call budget per task are both a concern; not independently measured this pass.
- Feasibility verdict: usable only on the small 33-task dev split; not a strong
  match for "materials in a folder," better filed as a stretch/secondary candidate.

## 7. FACTS Grounding (Google DeepMind) — single-turn document grounding, closed judges
- Blog: https://deepmind.google/blog/facts-grounding-a-new-benchmark-for-evaluating-the-factuality-of-large-language-models/ .
  Leaderboard paper: arXiv:2501.03200. Public dataset:
  https://huggingface.co/datasets/google/FACTS-grounding-public . Kaggle
  leaderboard: https://www.kaggle.com/benchmarks/google/facts-grounding . Read via
  WebSearch 2026-09-25.
- Task shape: single-turn — (user request + long document, ≤32k tokens) →
  long-form grounded response. No multi-step agent workflow, no tool use, no
  multi-file workspace — this is a QA/generation task, not an agentic one. Weak
  match to "coding agent operates in a workspace"; would only test the underlying
  model's grounding behavior, not Vacant's step-level accountability loop (there
  are no steps to trace).
- Grading: **3 closed frontier LLM judges** — originally Gemini 1.5 Pro, GPT-4o,
  Claude 3.5 Sonnet (per arXiv:2501.03200); final score = average across judges'
  scores across all examples. Not free, not open-weight, not something we can run
  with the free OpenRouter tier's local-like models.
- Feasibility verdict: **poor fit for this study** — no agentic/workspace shape to
  exercise Vacant's hook-and-trace loop, and grading needs 3 paid frontier judges.
  Only relevant as background reading on "how do people define grounding," which
  is conceptually close to what accountability-checking is trying to verify.

## 8. DeepResearch Bench (RACE + FACT) — open-web deep-research reports, judge now GPT-5.5
- Repo (cloned --depth 1, 200MB, code+results only):
  https://github.com/Ayanami0730/deep_research_bench . Paper: arXiv:2506.11763.
  Dataset: https://huggingface.co/datasets/muset-ai/DeepResearch-Bench-Dataset .
  Leaderboard: https://huggingface.co/spaces/muset-ai/DeepResearch-Bench-Leaderboard .
  README's own "News" section read directly from the cloned repo 2026-09-25.
- Task shape: 100 PhD-level research tasks (50 en/50 zh) across 22 domains, agent
  produces one long research report from open-web research (not from attached
  local files) — single deliverable, no fixed materials folder.
- Grading: two pipelines — **RACE** (report-quality, reference-based, 4-dimension
  rubric: comprehensiveness/insight/instruction-following/readability) and
  **FACT** (citation/claim verification against sources). Per the repo's own
  2026-05-11 changelog entry (read directly from the cloned README, not a
  secondary source): the official evaluator was just switched from Gemini-2.5-Pro
  to **GPT-5.5** for RACE and **GPT-5.4-mini** for FACT, after a bake-off against
  Gemini-3.1-Pro and Claude-Opus-4-7 on a 200-article human-annotated subset
  (human inter-annotator baseline 68.78%; GPT-5.5 scored 71.82% overall, highest of
  the three). A dual-acceptance window (old+new evaluator) was open only until
  31 May 2026 — **as of today 2026-09-25 only the GPT-5.5/GPT-5.4-mini path is
  current**, and neither is a free/open-weight model.
- Requirements: repo itself is light (200MB, mostly code+cached results, safely
  cloned this pass); running the harness for real needs paid GPT-5.5/GPT-5.4-mini
  API access, not covered by the free OpenRouter tier.
- Feasibility verdict: poor fit for local/free judging (same problem as GDPval:
  paid frontier judge, no offline path); also not file-grounded (open web
  research, no materials folder) so it's a weaker analogue to the prompt's own
  marketing-plan example than OfficeBench/TAC/GDPval.

## 9. WritingBench — the one candidate with a genuinely free, locally-hostable judge
- Repo: https://github.com/X-PLUG/WritingBench (read 2026-09-25). Paper:
  arXiv:2503.05244. Critic model on HF:
  https://huggingface.co/AQuarterMile/WritingBench-Critic-Model-Qwen-7B (confirmed
  via WebSearch 2026-09-25 — fine-tuned from Qwen2.5-7B-Instruct on a 50K SFT
  set; GGUF quantized builds also exist, e.g.
  mradermacher/WritingBench-Critic-Model-Qwen-7B-i1-GGUF, which would run on CPU
  on this container, unlike every other judge model found in this scout).
- Task shape: 1,000 real-world writing queries across 6 domains/100 subdomains;
  each query is paired with **5 instance-specific criteria** and, notably, many
  queries include attached "open-source materials (e.g., public financial
  statements or legal templates)" the response is expected to use — this is a
  genuine "given materials, produce a grounded write-up" shape, just single-turn
  (no multi-step tool/workspace loop — the "agent" here is really just a
  prompt-in/response-out call, so it would exercise Vacant's materials-grounding
  check but not its multi-step trace/rerun machinery).
- Grading: per-criterion 1-10 score + justification, either via an LLM evaluator
  (repo docs recommend Claude-3-7-Sonnet) or via the **open-weight 7B critic
  model above**; critic reaches 83% agreement with human preference per the
  README's own reported number (not independently re-verified this pass).
- Requirements: light — no Docker/company simulation, just prompt+materials in,
  text out, score via the 7B critic (locally hostable, no external calls needed
  for grading at all, which sidesteps the 50-calls/day cap entirely for the
  judging side of the comparison).
- Feasibility verdict: **best cost profile of the whole set** for a same-day study
  — free/local judge, file-grounded tasks, no heavyweight environment — but the
  task shape (single prompt→response, no tool-using workspace) under-exercises
  what Vacant's hook actually watches (file reads, tool calls, multi-step
  self-correction). Good as a controlled "materials-grounding" sub-experiment,
  not a full analogue of the marketing-plan example on its own.

## 10. ResearchRubrics (Scale AI) — rubric-graded deep-research, paid judge
- Repo: https://github.com/scaleapi/researchrubrics (read 2026-09-25, ICLR 2026).
  Paper: arXiv:2511.07685. Dataset: HF `ScaleAI/researchrubrics` (per repo docs).
- Task shape: domain-diverse open-ended research prompts (not file-grounded, no
  local materials) paired with **2,500+ expert-written rubrics** (~2,800 human
  labor-hours) scored across 6 axes (synthesis, explicit requirements,
  communication quality, etc.) — even frontier DR agents (Gemini DR, OpenAI DR)
  score <68% average rubric compliance, i.e. lots of visible headroom.
- Grading: default judge is **"Gemini 2.5 Pro via LiteLLM"**
  (`litellm_proxy/gemini/gemini-2.5-pro-preview-06-05` in the repo config),
  documented as swappable but not free/open by default; grading runs via API
  (LiteLLM), not locally, with configurable concurrency + retry.
- Requirements: repo itself is small; dataset download separate from HF, size
  unconfirmed this pass.
- Feasibility verdict: rubric-per-requirement grading is conceptually the closest
  thing here to Vacant's own "which steps were justified" check (a rubric item is
  basically a located accountability point), but paid Gemini-2.5-Pro judge and no
  file-grounded materials make it a design reference more than a runnable
  candidate under the free-tier constraint.

## 11. Agent-as-a-Judge / DevAI (metauto-ai) — closest DESIGN analogue to Vacant's own trace/blame idea
- Repo: https://github.com/metauto-ai/agent-as-a-judge (README for DevAI read
  2026-09-25: benchmark/devai/README.md). Paper: arXiv:2410.10934 (ICML 2025).
- Task shape: 55 realistic AI-development (coding) tasks with **365 hierarchical
  requirements** organized as a DAG (some requirements depend on others being
  satisfied first, e.g. "visualize results" depends on "load data" succeeding).
  The system under test is any agentic coding system that can "receive a human
  query" and "output a workspace" — README explicitly names Devin, OpenHands,
  MetaGPT, GPT-Pilot as example systems; would need a small adapter to plug in
  pi/OpenCode/Claude Code/Codex (collect workspace + trajectory in their expected
  schema) — not done for any of the 4 out of the box, unverified how much adapter
  work that is.
- Grading: an **agent** (not a single LLM call) inspects the output workspace +
  execution trajectory and checks off each of the 365 requirements individually,
  reporting which passed/failed and why — this is architecturally very close to
  what Vacant's own `trace/blame.py` + `feedback.py` already do (locate → check →
  report, no single "vibes" score). Default judge model not stated in the README
  read this pass (flag as unverified); original paper reports agent-as-a-judge
  hitting 90-92% alignment with human consensus vs 60-71% for plain LLM-as-judge
  on this same benchmark — i.e. the paper's own headline finding is exactly
  Vacant's thesis (grounded/localized checking beats a single end-to-end judgment).
- Feasibility verdict: **not a task-shape match** (55 tasks, all in the coding
  domain, not "knowledge work with materials") so it doesn't answer this scout's
  brief directly — but it is the strongest **conceptual precedent** found in this
  pass for "requirement-level, located feedback beats holistic self-review," which
  is worth citing when writing up why Vacant's approach should work, independent
  of whether DevAI itself gets run.

---

## Cross-cutting notes for the lead

- **Judge-model reachability via free OpenRouter, across all 11**: none of the
  official/default judges found (GPT-5, GPT-5.5/GPT-5.4-mini, Gemini-2.5-Pro,
  Claude-3.5-Sonnet, GPT-4o) are free-tier models, and none were found offered
  as ":free" on OpenRouter in scratchpad/orq/models_now.json (not re-checked
  exhaustively this pass — worth a grep by the lead). The **only** exception
  found is WritingBench's 7B critic, which is open-weight and can be self-hosted
  instead of called through OpenRouter at all.
- **Disk/network risk ranking** (least to most risky under our ~18GB shared /
  4CPU / no-GPU box): GAIA (110MB, deterministic, gated download) <
  WritingBench (light, local 7B judge, CPU-only inference will be slow) <
  OfficeBench/OdysseyBench (unconfirmed size, Docker, deterministic grading) <
  DeepResearch Bench (200MB code, but paid judge) < AssistantBench (needs live
  web, held-out test answers) < ResearchRubrics/FACTS Grounding (paid judges,
  no local materials) < GDPval (2.29GB dataset, unbounded agent steps, judge is
  an external paid submission service) < TheAgentCompany (30GB+ disk requirement
  alone exceeds our total budget).
- **Best match to the prompt's own worked example** ("logo, schedule, real data
  in the folder → agent should open them, not write a generic plan"), ranked:
  GDPval (files are real professional deliverable materials) ≈ TheAgentCompany
  (real company data + apps) > OfficeBench/OdysseyBench (multi-app office files,
  deterministic grading) > WritingBench (materials attached, but single-turn) >
  GAIA (attached files, but deliverable is a short answer not a document) >
  everything else (open-web research, no local materials folder).
- No candidate here cleanly satisfies *both* "file-grounded multi-step office
  task" *and* "free/local grading" *and* "fits our disk/CPU budget" at once —
  OfficeBench is the closest to a 3-way fit but its agent-interface compatibility
  with pi/OpenCode/Claude Code/Codex needs a code-level check (not done this
  pass, flagged above) before committing.
