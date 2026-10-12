# critic-plan working notes (2026-09-25)
Sources read (local clones, harbor @ 6cb9ff31):
- adapters/dabstep/README.md L11-13,58: 6 dev IDs overlap default split (5,49,70,1305,1681,1753)
- adapters/dabstep/README.md L144 + parity_experiment.json: parity "original" = fork (harvenstar/DABstep harbor-adapter) running claude -p / claude-code, not smolagents; README says Harbor side terminus-2, json says claude-code@2.1.39 (inconsistent)
- adapters/dabstep/template/instruction.md: already says twice to reference documentation in /app/data
- adapters/spreadsheetbench-verified/parity_experiment.json: original side = fork Rebabit/SpreadsheetBench harbor-parity running claude-code (agentic), not paper's single-round script; README L15 removes spreadsheet previews
- SBV tests/test.sh apt-get installs libreoffice-calc at every verify (floating Debian mirror)
- agents/installed/pi.py L179: default install @latest (version drift); thinking option L73; max_turns extension
- pi docs/extensions.md: agent_before_settle can request ONE continuation; print/json modes have no UI -> continuation in Harbor's print mode unverified
- orq/ep_google_gemma-3-12b-it.json: deepinfra/bf16, tools yes; never called live (ledger by_tag has only qwen tags)
- orq/ep_google_gemma-4-26b-a4b-it.json: paid deepinfra/fp8 0.07/0.34 with tools exists
- ledger summary: 41 req, $0.02414057; Appendix B rows omit smoke-proxy, try1-pi-qwen9b, live-test-ping ($0.00081486, 7 calls)
- research.py has mcnemar_exact, boot_ci, holm_bonferroni, tost_equiv_boot, mcnemar_power, mcnemar_n_required, stratified_mcnemar_exact (L142-444)
