# NOW.md — 現況（每輪覆寫、≤3KB）

## 狀態（2026-11-12 r1510；票 P20261112_1326-2 完成：e008 DABench 60 格結案機械複核量具＋單測，commit aa236e93d；r1507 態仍有效：g3_2 合併 832732a0a、e015 BOUNCE、freeze_check 唯 diff_* 在途）
- **較上輪好的命令：** `python3 ops/audits/e008_closure_check.py --selftest`→VERDICT: E008_CLOSURE_OK（正控制＋4 負控制全過）＋`pytest tests/test_e008_closure_check.py`→3 passed RC=0（票驗收全綠）；e008 完賽裁決（60 格、A 29/30、C 27/30、p=0.5、C 臂 30 格封頂 PASS、通用任務無可測影響）今由量具＋單測永久鎖定。
- **承 r1507（仍有效）：** g3_2 修復合併＋worker 同步＋f1-f4 假檔 32 清出（wt_clean 3/3 clean）；e015 票 BOUNCE（done/→open/、票內證據＋修法）；freeze_check 11/12、唯 diff_worker＝e015 WIP 3 檔。
- **紅線：** 無 push（loop 自推 auto/qwen27b）、main 未動、無 reset/rebase、.github/workflows/ 只讀、hidden/scorer 未讀、未跑 full pytest；
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。

## 未完（≤3、交下輪）
1. 三分支新 HEAD CI 一次讀取（qwen 現 aa236e93d＋簿記；紅→log 根因不猜）。
2. e015 重做（worker）：改載 REPORT.json（或 e015 專用 verdict 管線）＋BACKLOG CLOSURE_NOTE→selftest E015_CLOSURE_OK＋pytest 全綠→升三分支→freeze_check 12/12。
3. 候人類裁決：L008 樣本量/預算（未發射、0 呼叫）；e013 票（bounced/）候規劃者修驗收 grep；G 系列（vq-kax）。

## 下輪入口（≤3）
- CI 一次讀取；紅→log 根因。
- `bd list --parent vq-el4 --all` 照順序；呼叫 GLM／DeepSeek 一律用 `glm` 指令。
- 守衛：NOW.md ≤3KB、ops/loop/NOW.md 與 root byte-identical（cp 鏡像）、ops/STATE.md＝canonical Current State 前綴鏡像（bk_state 契約）、紅線契約行逐字保留（now_redline 機器解析）。
