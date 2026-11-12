# NOW.md — 現況（每輪覆寫、≤3KB）

## 狀態（2026-11-12 r1521；senior review §1–§3 驗收全數本輪新跑綠＋bk_now 鏡像漂移閉環→worker worktree freeze_check 12/12 VERDICT: FROZEN_STATE_OK RC=0；0 model calls）
- **產物：** ① §1–§3 驗收（本輪新跑、非引用上輪）：e002（65bc806cd）selftest→VERDICT: E002_CLOSURE_OK RC=0＋pytest tests/test_e002_closure_check.py 3 passed；e014/e015/l008 三 selftest→VERDICT 全 OK、l008 報告 selftest 前後 sha256 不變（41a5c9b8…，§1(b) 不覆寫成立）＋pytest（e014 4＋e015 3＋l008 2）RC=0。② bk_now 唯一紅燈閉環：根因 r1519（bafd438f7）簿記只更 repo 根 NOW.md、ops/loop/NOW.md 鏡像遺留 2969B 舊版（argon 側 bcc805143 已自修、qwen27b/worker 未修）→本輪覆寫本檔（≤3KB）＋cp 鏡像 byte-identical＋三分支收斂。
- **驗收：** cd /home/user1/dev/wt/worker && python3 ops/reqloop/freeze_check.py→12/12 全 OK、VERDICT: FROZEN_STATE_OK、RC=0（anchors 5 passed、ci_contract 2 passed、diff 0、filing 6/6 MATCH、now_redline、bk_state、bk_now）。
- **紅線：** 無 push（loop 自推 auto/qwen27b）、main 未動、無 reset/rebase、.github/workflows/ 只讀、hidden/scorer 未讀、未跑 full pytest、0 行產品碼（純簿記）；
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。

## 未完成（≤3、交下輪）
1. CI 三分支驗收（vq-fd0）：現一次讀＝qwen 4104c851/argon 85e18f163/worker 2aa9f48cf 全 pending 非紅；下輪頭複讀一次（不 poll），紅則讀 log 定根因。
2. e015 殘留：/srv/vlab/runs/e015_h_multi_review/VERDICT.json 第 1780 行磁盤損傷（量具已釘 repo 內快照 d0e29884…；磁盤修復另立工單，未做）。
3. 候人類裁決（不進 vq-el4 順序）：L008 樣本量／預算（未發射、0 調用）；G 系列重發（vq-kax）；e013 票（bounced/）候 planner 修驗收 grep；0820-1（open/）候 worker 重驗 item 1。

## 下輪入口（≤3）
- CI 三分支一次讀（ci_status.py、不 poll）→紅則 log 定根因（vq-fd0 驗收）。
- bd list --parent vq-el4 --all 依序取下一張票（bd ready 現為空；planner 只配 vq-el4 順序下一未結）。
- 簿記守衛：NOW.md ≤3KB、ops/loop/NOW.md＝cp 鏡像（byte-identical、bk_now）；ops/STATE.md＝root STATE.md byte 前綴（bk_state）；紅線契約行逐字保留（now_redline 機械解析）。
