# P9 線 V：`enclose=on`＋`require_tier=B` 的真跑（2026-10-02，舊 VM，bwrap 圍牆）

- `e1`–`e6`：6 組合成特質各 1 跑（最終版）；`e7`：預算探針（`VACANT_TWIN_RUN_BUDGET_S=40`、`MIN_ATTEMPT_S=30`）。
- `first_attempt_no_gate_rows/`：第一次跑（修好前）的 6 跑：圍牆、級別 B、驗收沙箱都正常，但 **`gate_ran` 沒有 `checks`**——
  圍牆裡的 `prepare` 寫不到圍牆外的旁註檔與事件檔。已修（旁註改寫 run-dir，主機側 `twinenclose.EventForwarder` 先於 lifecycle 轉出）。
- 環境坑：`AF_UNIX path too long`——門的 socket 路徑 `<TMPDIR>/…agentruns/doors/<32 字>/relay.sock` 超過 108 字元時 `run_enclosed` 以 OSError 退化。
  測試環境用短的 TMPDIR（`/tmp/ve`）；展場的 `VACANT_TWIN_DB` 路徑要夠短。
