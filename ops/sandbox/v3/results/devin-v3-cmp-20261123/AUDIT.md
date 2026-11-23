# v3 comparison contamination / outside-help audit (lead, session event search)
- All 72 sessions: 0 browser events; 0 pr_created events (PE: no PR opened by any cell).
- No hits for swe-bench/swebench/huggingface/princeton-nlp outside the dispatch prompt's own prohibition text.
- Upstream-org URL hits only in repo-local files or the problem statement: astropy-13236 (5 cells) issue-template comment in prompt; sympy-21612 plain2 s1/s2 codecov badge in README; sklearn-25747 plain-s1 README "everyone is welcome to". None is the upstream fix/issue page.
- Verdict: contaminated=false, outside_help=false for all 72. Raw: audit_raw.json.
