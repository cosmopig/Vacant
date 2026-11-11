# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-11 r1461：審查指示 #1/#2/#4 驗核＋diff_argon 修復＋1843-1 審查＝bounce）
- 審查 redo 4 檔已開並重核：effects summary 數字＝11-06 人類記錄（僅參考）；l007 selftest 本輪新跑→L007_CLOSURE_OK rc=0；extract.py 1217 行／repair.py 2795 行＝凍結契約相符（anchors 5 passed、本輪未改）。
- diff_argon（r1460 後唯一紅）已修：argon worktree 06d1d2d41 簿記同步→本輪 freeze_check diff_argon OK（實測 10/12，兩紅如下，非 argon）。
- 1843-1 審查＝**bounce（未升上）**：worker de75f2d87 測試 9 passed，但實測 live 路徑 regressed——真 labd（pid 1734）在跑、`check_labd_instances()` 回 0（pgrep 只回 pid 字串→is_labd 全 False＝假陰性；票面要求 live 用 /proc＋is_labd 未做到）；且檔案有 2 個同名 def（行 8 死碼引用未定義 cmdlines）。證據：ops/audits/labd_fp_live_20261111.json（修前假陽性 count 2）＋本輪 live 復測（假陰性 count 0）。票仍在 doing/（worker 現正做 1843-2、同檔，下輪先修 1843-1 再串行 1843-2）。

## 紅線（契約，不改）
- 不 push（loop 自動 push auto/qwen27b）、不 main、不 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不變；g3.py 僅依核准工單改動。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值＝UNKNOWN 不 0；hidden_after=UNKNOWN。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交下輪）
1. 1843-1 重修（票 doing/、票尾已附 bounce 證據）：live 路徑改 /proc＋is_labd、刪重複 def；驗收＝pytest 全綠＋live 復測（真 1→count 1 rc 0；雙實例→rc 1）＋升上 mainline＋三分支 sync＋freeze_check 12/12。
2. 1843-2（audit_run_dir/--audit-e016）：worker 在進（round 起 19:20）；須在 1843-1 收斂後串行審查（同檔）。
3. CI 三分支核＝python3 /home/user1/dev/ops/ci_status.py（不 poll）。另：G3.1 H2.0 重發待人類裁決（H2_0_REFUTED r1447a 仍有效）。

## 下輪入口（≤3）
- bd ready＋tickets/doing（1843-1 bounce 重修優先）；open＝1843-2。
- 守衛基線（r1461 實測）：freeze_check 10/12（兩紅＝diff_worker 如實（worker 領先 2 in-scope 檔、含 1843-2 WIP）＋now_redline 已修待下輪複核）；anchors 5 passed；worker 側 test_labd 9 passed（含 3 新測）。
- worker 系統性問題（記）：WIP auto-commit 可能再收 root 層 mock_* 雜訊（out-of-scope）；需 worker prompt 加 selftest 後清理。
