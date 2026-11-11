# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-11 r1461：審查指示 #1/#2/#4 驗核＋diff_argon 修復＋1843-1 之前證據）
- 審查 redo 4 檔已開並重核：effects summary 數字＝11-06 人類記錄（僅參考）；l007_closure_check 本輪新跑 --selftest→L007_CLOSURE_OK rc=0；extract.py 1217 行／repair.py 2795 行＝凍結契約相符（anchors 5 passed、本輪未改）。
- diff_argon（r1460 後唯一紅）：4 簿記檔已同步進 argon worktree＋commit；freeze_check 本輪新跑＝12/12 VERDICT: FROZEN_STATE_OK rc=0（若紅即修再同步，如實記）。
- 1843-1：worker（gemma，18:58:50 發射、~19:43 前收束）正在執行；本輪 DECISION: 不重做同檔（保守）；live 之前證據＝本機 pgrep -f 誤配 1（worker pi session 提示詞）＋真 1（pid 1734）→修前 check_labd_instances() exit 1 誤報（ops/audits/labd_fp_live_20261111.json）。

## 紅線（契約，逐字保留）
- 不 push（loop 自動 push auto/qwen27b）、不 main、不 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不得修改：repair.py 2795 行/blob 5147f8c3…，extract.py 1217 行/blob e757aec5…，checks.py 2823 行/blob f3525b01…，run_eval.py 1298 行/blob b6d2f37f…；g25 filing（6 個 sha256）不變；g3.py 只經核准工單修改。
- 不讀 /srv/eval/hidden/ 與 scorer.py；缺值＝UNKNOWN 不填 0；hidden_after=UNKNOWN。
- 不寫 /srv/vlab/queue；不 poll CI；不跑全量 pytest。

## 未完成（≤3，交接下輪）
1. 1843-1：worker commit 後審查（pytest tests/test_labd_instance_and_env_audit.py 全綠＋負控制＋live 復測＝count 1 rc 0）→升上 mainline＋票尾 3 行＋mv done/。
2. 1843-2（audit_run_dir/--audit-e016）：下輪入口票，須在 1843-1 升上後串行（同檔）。
3. CI 三分支核＝python3 /home/user1/dev/ops/ci_status.py（待新 tip 跑完；不 poll）。另：G3.1 H2.0 重發＝待人類裁決（H2_0_REFUTED r1447a 仍有效）。

## 下輪入口（≤3）
- bd ready＋tickets/open（1843-2）；doing/＝1843-1（worker）。
- 守衛基線（r1461 實測）：freeze_check 12/12 FROZEN_STATE_OK、anchors 5 passed、test_labd 6 passed（mainline 基線，worker 升上後改全綠＋2 新測）。
- worker 系統性問題（記）：WIP auto-commit 可能再收 root 層 mock_* 雜訊（out-of-scope）；需 worker prompt 加 selftest 後清理。
