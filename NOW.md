# NOW.md — Vacant 現況（≤3KB；本檔每輪覆寫、歷史見 STATE.md）

## 現況（r1533、2026-11-12、0 model calls）
- 本輪實質＝CI 紅燈例外通道收斂：三分支 CI 紅燈根因＝diff_worker（gemma worker r128 WIP f550ad900、e007 兩檔）；讀 log 定位、不猜。
- 判定：該 WIP 是已結案票（R20261112_2133-1 已 done/、qwen 正典綠；doing/、open/ 皆空、worker worktree clean、非在途票工作）上的自相矛盾草稿（同調 selftest(None×4) 一測期 0 一測期 1、必紅）→依 r1530 先例（結案時同款取代 r125 WIP 舊稿）同步正典 2 檔至 auto/worker（4eb72a025、與 qwen 同 blob）。
- 驗收（本輪新測）：worker 樹 pytest tests/test_e007_closure_check.py 紅→綠（1 failed→3 passed）；--selftest VERDICT: E007_CLOSURE_OK RC=0；freeze_check 11/12→12/12（VERDICT: FROZEN_STATE_OK、diff_worker 0 in-scope differ）；tests/test_reqloop_freeze_check.py＋test_reqloop_now_redline.py 32 passed（CI 紅燈兩檔轉綠）。
- CI（輪首＋輪末各一次、不 poll）：舊在途 qwen run（4784859e）23:14 落地 RED 2 failed＝freeze_check 2 測試（該 run 讀到 sync 前之 worker HEAD 850aa073、與預測一致）；新三分支 HEAD（qwen 75fc36e3／argon 4e9efc5f／worker 412cec59）CI 在途/未跑（不再讀）；auto/argon merge 條件（該 sha 🟢 且 test count≥qwen HEAD）未滿足、未執行。
- 披露：gemma worker 若在後續輪次重寫該 2 檔（票已結案），依 r1496 先例 bounce 回該分支處理。
- vq-el4 全閉；下一票候點名或真產品 bug（CI 紅燈為例外通道）；G 系列維持停止態、0 呼叫。

## 紅線
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- NOW.md ≤3KB；ops/loop/NOW.md cp 鏡像 byte-identical。
- 不以文書改動充實進度：本輪實質＝CI 紅燈根因收斂（sync 已結案票正典 2 檔）＋驗收新跑＋簿記三分支同步（全可機械複核）。

## 下一步
1. 下輪輪首 CI 三分支一次讀（不 poll）：argon 🟢 且 test count≥qwen HEAD→merge＋驗收；紅→讀 log 根因、不猜。
2. 若 CI 仍紅且根因再指向 worker 檔→讀 log 後按 r1496/本輪先例判定（在途票 vs 已結案票）。
3. vq-el4 全閉；下一票候點名或真 bug（CI 紅燈為例外通道）；G 系列維持停止態、0 呼叫。
