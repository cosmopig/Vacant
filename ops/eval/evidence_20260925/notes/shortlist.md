# shortlist notes (2026-09-25)

Checked locally (harbor clone at 6cb9ff3167596c456e0b24622d473b59fc9ab6c7, 2026-09-24):
- registry.json has: terminal-bench-sample 2.0 (10), terminal-bench 2.0 (89), aider-polyglot 1.0 (225),
  spreadsheetbench-verified 1.0 (400), dabstep 1.0 (450), gaia 1.0 (165), livecodebench 6.0 (100), swebench-verified (500).
- adapters/spreadsheetbench-verified/parity_experiment.json: claude-code@2.1.80 + claude-haiku-4-5, 400 tasks x3,
  original 68.83+/-0.79 vs harbor 68.25+/-1.09; LibreOffice recalculation; adapter fixes 11 grader bugs in the original.
- adapters/dabstep: default 450 answers are EXTRACTED from public task_scores (shortest score=True submission), not official
  hidden grading; dev 10 has real gold. Parity claude-code@2.1.39+haiku-4-5 on 130 stratified tasks x4: 37.69 vs 36.92 (easy 84.52 both).
- adapters/aider_polyglot: parity TB-adapter vs original (claude_code v1.0.92 + claude-3-7-sonnet) 34.2 vs 35.3;
  tests copied into tests/ at verify time (hidden from agent) -> differs from aider's own harness (test file visible, 2 tries with test output).
- pi.py uses access.configured_base_url; opencode.py sets baseURL only for provider in {anthropic, google, openai}.
Web (2026-09-25):
- https://huggingface.co/Qwen/Qwen3.5-9B : LiveCodeBench v6 65.6 (thinking mode default; window/settings not stated), BFCL-V4 66.1, TAU2 79.1. No SWE-bench/TB2 row.
- https://huggingface.co/google/gemma-3-12b-it : card page fetch showed PT table only (HumanEval 45.7, MBPP 60.4 PT);
  IT numbers (LiveCodeBench 24.6, HumanEval 85.4, MBPP 73.0) are from Gemma 3 tech report arXiv 2503.19786 -- recalled, UNVERIFIED this pass.
- https://huggingface.co/datasets/openai/gdpval : 220 rows, fields include reference_files, deliverable_files (gold), rubric_json, rubric_pretty.
Model context: MODELS.md update -- paid qwen/qwen3.5-9b darkbloom/fp4 via recording proxy :18900, 4.80 USD cap.
