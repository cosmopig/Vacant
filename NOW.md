# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-11 r1462：1918-1 done——labd 實例判定 /proc＋is_labd＋三向控制）
- check_labd_instances 重寫：live 用 stray_labd_ps_evidence.collect_processes＋is_labd（移除 pgrep -f 子字串路徑）；mock proc_list 逐項判定（list/dict["cmdline"]/bare string）；0→0 / 1→1 / >1→ERROR: MULTIPLE_LABD_INSTANCES Count N＋exit 1。
- 實測：驗收 RC=0（LIVE_COUNT_1_OK、pytest 10 passed）；live 三向（真 1→rc0；＋假第 2 實例→Count 2 rc1；假殘留 process 事後 kill、復測 1/rc0）；selftest×2 模式；stray_labd 6/6；anchors 5 passed；凍結 4 檔未動。
- 1843-1 bounce 兩缺陷皆閉：live 假陰性（is_labd 判定後不復現）；重複 def 本在 worker 未升上 de75f2d87，main 重寫後恰 1 個 def。

## 紅線（契約，不改）
- 不 push（loop 自動 push auto/qwen27b）、不 main、不 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不變；g3.py 僅依核准工單改動。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值＝UNKNOWN 不 0；hidden_after=UNKNOWN。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交下輪）
1. 1843-2（audit_run_dir/--audit-e016）：worker 在進（round 起 19:20）；收斂後串行審查（與 1918-1 同檔 ops/audits/labd_instance_and_env_audit.py；r1462 commit 為其新基線）。
2. 1215-1 收案狀態（diff_worker 殘留 3 檔，收案＋審查升上）。
3. CI 三分支核＝python3 /home/user1/dev/ops/ci_status.py（不 poll）。另：G3.1 H2.0 重發待人類裁決（H2_0_REFUTED r1447a 仍有效）。

## 下輪入口（≤3）
- bd ready＋tickets/doing（現空）；open＝1843-2。
- 守衛基線（r1462 實測）：labd 票驗收＋selftest×2＋stray_labd＋anchors 全綠；其餘 freeze_check 項不變、下輪複測。
- worker 系統性問題（記）：WIP auto-commit 可能再收 root 層 mock_* 雜訊（out-of-scope）；需 worker prompt 加 selftest 後清理。
