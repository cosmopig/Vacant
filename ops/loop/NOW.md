# NOW.md — Vacant 現況（≤3KB；本檔每輪覆寫，歷史入 STATE.md）

## 現況（r1523，2026-11-12，0 model calls）
- 本輪實質＝HEAD 紅燈閉環（vq-el4.102，產品真 bug 例外）：r1522 超時（rc=124）殘留改動被 569df0b74 自動提交——e013_closure_check.py n4 訊息「缺裁決註記」→「缺票面要求內容」＋BACKLOG 行加 vacant_sha 要求（票面未要求、e002/e006/e008/e009 同族皆「缺裁決註記」）→ `pytest tests/test_e013_closure_check.py` HEAD 1 failed。
- 修法＝byte 還原已驗收 996d40561 blob（commit ffa970cae）：`--selftest`→VERDICT: E013_CLOSURE_OK RC=0；pytest 1 failed→3 passed；freeze_check 12/12 FROZEN_STATE_OK RC=0（diff_worker/diff_argon in-scope 0 檔、wt_clean 3/3、anchors 5 passed、filing 6 sha MATCH）。
- §1（merge auto/argon bcc805143）延後：輪首 CI 三分支一次讀全「還沒跑完」（qwen 569df0b7/argon 944b553b/worker 9ed92055，不 poll）；ASSIGNMENT 合併規則要求該 sha CI🟢。
- bd：vq-el4 全票 closed（0 open）；本輪票 vq-el4.102 驗收後結案；bd ready 空。

## 紅線
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑 full pytest。
- NOW.md ≤3KB；ops/loop/NOW.md cp 鏡像 byte-identical；ops/STATE.md＝root STATE.md byte 前綴（bk_state）。
- 不以文書改動充實進度：本輪實質＝1 檔還原＋3 指令重驗（selftest/pytest/freeze_check 全綠），全可機械複核。

## 下一步
1. 下輪頭 CI 三分支一次讀（ci_status.py，不 poll）：argon 🟢 且測試數≥qwen HEAD → 執行 §1 `git merge --no-edit auto/argon`；紅→讀 log 根因不猜。
2. bd list --parent vq-el4 --all → 依序下一票（產品真 bug／CI 紅燈為例外）。
3. 簿記守衛：NOW.md ≤3KB＋鏡像＋STATE 追加＋freeze_check 12/12。
