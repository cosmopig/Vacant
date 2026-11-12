# NOW.md — 現況（每輪覆寫、≤3KB）

## 狀態（2026-11-12 r1522；senior review §3 完成：e013 結案量具入 qwen27b、驗收全綠；§1 merge 延後（CI pending）；0 model calls）
- **產物：** e013 完賽結案機械複核量具（票 R20261112_1821-1、資深審查§3）：ops/audits/e013_closure_check.py（138 行；複核 auto/worker 990581ebc 腳本 byte 採用、對齊 e009 架構）＋tests/test_e013_closure_check.py（53 行；worker 版負控制測試為空 pass＝假綠燈→改實測 4 負控制）。數值本輪全新核對：REPORT 60 格 A 28/30 [0.9333]、C 27/30 [0.9]、p=1.0、A_only 2/C_only 1、vacant_sha c8167271…；envelope C 30 PASS/0 FAIL、home_bytes [26151,54408,165414]；packet 標題；BACKLOG 第 60 行 [x]＋裁決註記＋sha256 3e5969ac…。
- **驗收（本輪新跑）：** `python3 ops/audits/e013_closure_check.py --selftest`→VERDICT: E013_CLOSURE_OK RC=0＋`pytest tests/test_e013_closure_check.py`→3 passed；CI 模擬（git archive 異位＋空 HOME）同綠。commit 996d40561、bd vq-el4.101 closed；三分支簿記已同步、freeze_check 12/12 OK（含清除 worker WIP 殘留絕對路徑符號連結 2 個）。
- **延後（DECISION）：** §1 merge auto/argon（bcc805143）——ASSIGNMENT 合併規則要求該 sha CI🟢；三分支 CI 全 pending（本輪一次讀、不 poll）。qwen 側已有同效 bk_now 修復 269a930de，CI 綠後直接 merge 收斂。
- **紅線：** 無 push（loop 自推 auto/qwen27b）、main 未動、無 reset/rebase、.github/workflows/ 只讀、hidden/scorer 未讀、未跑 full pytest、0 行產品碼（2 新增檔）；
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。

## 未完成（≤3、交下輪）
1. CI 三分支驗收（vq-fd0）：本輪一次讀＝qwen cc2be2eb/argon d7a902a0/worker 06c68633 全 pending（非紅）；下輪頭複讀新 SHA（996d40561…）一次（不 poll），紅則讀 log 定根因。
2. e015 殘留：/srv/vlab/runs/e015_h_multi_review/VERDICT.json 第 1780 行磁盤損傷（量具已釘 repo 內快照 d0e29884…；磁盤修復另立工單，未做）。
3. 候人類裁決（不進 vq-el4 順序）：L008 樣本量／預算（未發射、0 調用）；G 系列重發（vq-kax）。（e013 本輪已結案移出等待；0820-1 已於 r1502 結案。）

## 下輪入口（≤3）
- CI 三分支一次讀（ci_status.py、不 poll）→vq-fd0 驗收；argon d7a902a0 若🟢且測試數不少於 qwen HEAD 即按 §1 `git merge --no-edit auto/argon`。
- bd list --parent vq-el4 --all 依序取下一張票（bd ready 現為空；planner 只配 vq-el4 順序下一未結）。
- 簿記守衛：NOW.md ≤3KB、ops/loop/NOW.md＝cp 鏡像（byte-identical、bk_now）；ops/STATE.md＝root STATE.md byte 前綴（bk_state）；紅線契約行逐字保留（now_redline 機械解析）。
（MEMORY 上限 6 KB、NOW 上限 3 KB）
