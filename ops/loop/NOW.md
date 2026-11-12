# NOW.md — 現況（每輪覆寫、≤3KB）

## 狀態（2026-11-12 r1511；CI 紅燈例外輪：argon 🔴 2 failed 根因定案＋e006/e008 四檔＋簿記兩分支同步；freeze_check 9/12→10/12，唯餘 diff_worker＋wt_clean 皆＝worker e015 WIP 在途）
- **較上輪好的命令：** `python3 ops/reqloop/freeze_check.py` 9/12（3 BROKEN）→10/12（2 BROKEN：diff_worker＋wt_clean，皆＝worker e015 WIP 在途、票在 doing/）；`git diff --name-only auto/argon auto/qwen27b -- vacant_network tests ops` 6 檔→0（diff_argon BROKEN→OK）；e006/e008 selftest VERDICT OK＋6 passed 三樹全綠（argon 872155a16＋c51155bfd／worker 708b16c06＋09ec4a2b4）。
- **argon 紅燈根因（log 定案、非猜）：** 2 failed＝test_reqloop_freeze_check verdict 兩測←freeze_check diff_worker/diff_argon（r1510 簿記未同步兩分支）＋wt_clean（worker e015 WIP M＋??，票在 doing/、selftest RC=1 在途）；e015 官方版 qwen selftest RC=0 未動——不碰 WIP、不代修（r1496 先例）。
- **本輪同步（只收斂檔）：** e006/e008（2 量具＋2 測試）＋簿記 4 檔→argon/worker；worker WIP 兩檔（e015_closure_check.py M、e015_verdict_pipeline.py ??）未 commit 未觸、commit 後復核仍在。
- **紅線：** 無 push（loop 自推 auto/qwen27b）、main 未動、無 reset/rebase、.github/workflows/ 只讀、hidden/scorer 未讀、未跑 full pytest；
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。

## 未完（≤3、交下輪）
1. e015（worker doing/）：收斂（selftest E015_CLOSURE_OK＋pytest 全綠）→審查門驗收→升三分支→freeze_check 12/12→argon CI 紅轉綠。
2. 0820-1（open/）：worker 重驗項1（VERDICT 裁決行）→升三分支。
3. 候人類裁決：L008 樣本量/預算（未發射、0 呼叫）；e013 票（bounced/）候規劃者修驗收 grep；G 系列（vq-kax）。

## 下輪入口（≤3）
- 三新 HEAD CI 一次讀取（紅→log 根因不猜、不 poll）。
- e015 收斂檢查：worker 樹 `python3 ops/audits/e015_closure_check.py --selftest` RC=0 否？收斂即按審查門驗收→升三分支。
- 守衛：NOW.md ≤3KB、ops/loop/NOW.md 與 root byte-identical（cp 鏡像）、ops/STATE.md＝canonical Current State 前綴鏡像（bk_state 契約）、紅線契約行逐字保留（now_redline 機器解析）。
