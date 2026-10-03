# plan — working notes (2026-09-25)

Inputs read (all under scratchpad/study unless noted):
- MODELS.md (owner update 09:30 UTC: 5 USD paid; free cap stays 50/day because <10 USD purchased; chosen paid models qwen/qwen3.5-9b darkbloom/fp4 0.08/0.13 USD per M, google/gemma-3-12b-it deepinfra/bf16 0.05/0.15; proxy ops/eval/orproxy.py on :18900, cap 4.80 USD).
- scratchpad/evalrun/ledger/summary.json: total spent 0.02414057 USD of 4.80 across 41 requests, all qwen/qwen3.5-9b. Per-tag numbers used in the plan:
  live-dabstep-5 4 calls 0.00120645; live-dabstep-70 8 calls 0.00673689; live-sbv-10452 7 calls 0.00740026 (85116 prompt tok);
  live-tb2-regex-log 1 call 16384 reasoning tok 0.00226728; live-lcb-* 8000/10000 reasoning tok, no answer; live-aider go_hexadecimal 2000 reasoning tok no answer; live-gdpval 8 calls 0.00207216.
- orq/*.json endpoint snapshots: gemma-3-12b-it DeepInfra bf16 ctx 131072 max_out 16384 params incl. tools, no `reasoning`; qwen3.5-9b Darkbloom fp4 has `reasoning`+`include_reasoning`+tools; gpt-oss-20b fp4 (AkashML 0.02/0.10, CoreWeave 0.03/0.13) has reasoning param + tools; gemma-4-26b-a4b-it:free Google AI Studio quant unknown, tools yes.
- arch/NOTES.md + partial_result.json['arch'] (design_markdown, new_pieces with sizes, harness_install, logging_spec, risks).
- env/RECIPE.md: docker --network host + HTTPS_PROXY + CA bundle recipe; npm installs of the 4 agents OK; apt on Ubuntu mirrors NOT reachable (Aider deep-dive: archive.ubuntu.com 405 through proxy). Debian-based python:3.11-slim builds worked (SBV oracle 2/2).
- deep-*/NOTES.md and the verify blocks in the task JSON (LCB, TB2, Aider, SBV, DABstep, GDPval).
- scout-selfcheck/NOTES.md: Huang et al. ICLR 2024 arXiv:2310.01798; Tyen et al. Findings ACL 2024 aclanthology 2024.findings-acl.826; Kamoi et al. TACL 2024 arXiv:2406.01297; CRITIC ICLR 2024 arXiv:2305.11738.
- vacant_network/research.py: mcnemar_exact, boot_ci, holm_bonferroni, tost_equiv_boot, wilcoxon_signed_rank_exact, mcnemar_power, mcnemar_n_required, stratified_mcnemar_exact.
- vacant_network/memory.py KS1_FORBIDDEN (7 phrases zh/en).

Computed here with the repo's own functions (.venv, 2026-09-25):
  mcnemar_n_required(alpha=.05, power=.8): p_disc=.3 psi=.8 (Δ=+18pp) n=77; .3/.75 (+15pp) n=112; .3/.7 (+12pp) n=172; .4/.75 (+20pp) n=84; .4/.7 (+16pp) n=129; .2/.8 (+12pp) n=115; .2/.75 (+10pp) n=168; .5/.7 (+20pp) n=103; .3/.667 (+10pp) n=248.
  mcnemar_power at p_disc=.3 psi=.8: n=10 0.012, n=20 0.151, n=30 0.315, n=50 0.582, n=100 0.904.

Decisions taken in the plan (with reasons in the plan text):
1. First wave = DABstep (10 dev true-gold + 72 easy) via Harbor with pi, and SpreadsheetBench-Verified 40-task stratified subset via Harbor with pi. Both graded deterministically, both have "given materials", both cheap (<0.01 USD/task measured), both run here with the CA-bundle workaround (DABstep image needs a hand-patched Dockerfile here because its base is Ubuntu; on the owner's machine the stock adapter should build).
2. TB2 sample (8 of 10 tasks, qemu tasks excluded) = second wave, only after the reasoning-token blowup is solved (thinking off / gemma-3-12b-it).
3. Aider Polyglot = owner's machine only (apt blocked here); Harbor adapter n_attempts=1 vs aider 2-try recorded as deviation.
4. LCB v6 = model-validity anchor only (gemma-3-12b-it, official lcb_runner custom_evaluator path, published 32.0 Table 18 arXiv:2503.19786, 8-sample average per Table 21); not a Vacant benchmark (single-shot).
5. GDPval dropped for this round (license unstated, official grader unreachable, official image 5-8 GB, no agent-process hook point without a retrofit).
6. Primary model recommendation: google/gemma-3-12b-it (deepinfra/bf16) because it is non-reasoning (no token blowups seen on qwen3.5-9b in 4 of 6 benchmarks) and matches the owner's "12B gemma like local" wish in weights (not in quantization — flagged). qwen3.5-9b kept as second model only if `reasoning: {effort: low}` (untested) stops the blowups.
7. Free models: pilot only (50 calls/day ≈ 1 DABstep task × 3 arms per day).
