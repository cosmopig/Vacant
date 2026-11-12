# NOW.md — 現況（每輪覆寫、≤3KB）

## 狀態（2026-11-12 r1502；0820-1 驗收過＋5 檔三分支收斂（in-scope diff 0/0）＋worker round-110 WIP 回退（selftest BROKEN 實測）＋f1-f4 junk 清除；freeze_check 末值 11/12（唯 BROKEN 候選＝wt_clean worker 在途輪））
- **票 R20261112_0820-1 驗收過（驗收態 2b915a54f）：** 項1 `g3_2_precheck.py --selftest`→VERDICT: G3_2_PRECHECK_OK（正控制＋5 負控制 n1-n5）✓；項2 `g3_2_fire_summary.py --selftest`→VERDICT: G3_2_FIRE_SUMMARY_SELFTEST_OK RC=0 ✓；項3 pytest 3 測試檔 19 passed ✓。升上 qwen 84665f8a1（含 r1428 docstring 測試、函數體未動）→argon 1781caccf；in-scope diff_worker/diff_argon＝0 檔。票 open/→done/＋票尾註記。
- **worker WIP 回退（實質裁決、非文書）：** round-110 自動 commit 5f1be6ed9 接 check_fire_summary 進 selftest＋加 task-status 檢查，但真實 JSON tasks 無 status 欄位→selftest BROKEN＋test_selftest_success FAILED（本輪兩路實測）→回退 2b915a54f 版本（worker f23e50c32、worktree 同還原）；WIP 留痕 5f1be6ed9（git show 可重做）。另清 16 檔 f1-f4 佔位（aeb82b0b2，無引用、qwen/argon 從未存在）。
- **較上輪好的命令：** worker HEAD 5f1be6ed9 時 `g3_2_fire_summary.py --selftest`＝BROKEN、`test_reqloop_g3_2_fire_summary.py::test_selftest_success`＝FAILED→回退後三分支皆 VERDICT OK＋19 passed。
- **紅線：** 無 push（loop 自推）、main 未動、無 reset/rebase、.github/workflows/ 只讀、hidden/scorer 未讀、凍結 4 檔＋filing 未改（anchors 5 passed 本輪新跑）、0 model calls、未跑 full pytest、不以文書改動充實進度。

## 紅線（契約、不變）
- 不 push（loop 自推 auto/qwen27b）、不 main、不 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史不改。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN、不補 0。
- 不寫 /srv/vlab/queue；CI 不 poll；不跑 full pytest。

## 未完（≤3、交下輪）
1. CI 一次讀取（三分支新 HEAD：qwen 84665f8a1／argon 1781caccf／worker aeb82b0b2；不 poll；紅→讀 log 根因不猜）。
2. wt_clean：worker 在途輪（round 111）11:23 重建 f1-f4 scratch→不碰 live worktree；下輪觀其自動 commit 收斂或再清（r1502 已清一次、留痕 aeb82b0b2）。
3. e013 票（bounced/）候規劃者修驗收 grep（`grep -F -- "- [x]"`）；G 系列候人類裁決（vq-kax、0 呼叫）。

## 下輪入口（≤3）
- ci_status.py 一次讀取；紅→log 根因。
- worker 在途輪收斂檢查：樹 clean＋f1-f4 不再出現→freeze_check 12/12 複核。
- 守衛：anchors 5 passed、NOW.md ≤3KB、ops/loop/NOW.md 與 root byte-identical、ops/STATE.md＝canonical 前 5 行。
