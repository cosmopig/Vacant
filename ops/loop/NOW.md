# NOW.md — 現況（每輪更新，≤3KB）

## 狀態（2026-11-11 r1460 收案輪：1215-1＋L007 結案、三分支同步、守衛全綠）
- **1215-1（hidden_file_in_workspace 收緊）：已結案**——e3f6fe884 在 auto/qwen27b 祖先（r1459 升上）；驗收重核（本輪新跑）：tests/test_hidden_file_in_workspace_tighten.py 6 passed＋tighten --selftest VERDICT: HIDDEN_FILE_TIGHTEN_OK；票 done/。
- **L007（資料損失循環）：已結案**——loop/L007.md §8 結案段終態 CLOSED: NO_MECHANISM＋e016 數據（A 18/34、C 17/34、C-nf 16/34、McNemar p=1.0）；BACKLOG [x]＋「round 1459 結案」；l007_closure_check --selftest VERDICT: L007_CLOSURE_OK rc=0（本輪新跑）；票 R20261111_1516-1 done/。
- 簿記：bk_state 鏡像重建（head -5 慣例）、bk_now cp 同 blob；三分支 in-scope diff 0×2（worker：32 檔升上集同步＋ops/loop/L007.md 移除＋root mock 雜訊清；argon：簿記 4 檔同步）；freeze_check 12/12 FROZEN_STATE_OK（本輪新跑）。
- 前情：r1458（1716-2）bounced（期望值與數據矛盾）；r1450（1516-1 g3 contract wiring）done；H2.0=REFUTED（r1447a）維持。

## 紅線（契約，不改）
- 不 push（loop 自動 push auto/qwen27b）、不 main、不 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不變；g3.py 僅依核准工單改動。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值＝UNKNOWN 不 0；hidden_after=UNKNOWN。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交下輪）
1. 1516-2（G3 extract contract input gap audit，open/）：下輪入口票。
2. G3.1 H2.0 重發：預註冊停止規則＝不發完整批、裁決歸人類（待人類）。
3. hidden 計分：10 cells ok 有答案，人側/vlab 側；CI 三分支核＝python3 /home/user1/dev/ops/ci_status.py（新 tip 跑完後，不 poll）。

## 下輪入口（≤3）
- bd ready＋open/ 票（1516-2）；doing/ 現空。
- 守衛基線（r1460 量）：freeze_check 12/12、anchors 5 passed、tighten 6 passed。
- worker loop 注意：WIP auto-commit 會再收 root 層 mock_* 雜訊（非 in-scope）——需 worker prompt 加 selftest 後清理（系統性，已記錄）。
