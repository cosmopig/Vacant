# NOW.md — 現況（每輪覆寫、≤3KB）

## 狀態（2026-11-12 r1507；senior review 指示：Step 1 argon g3_2 修復合併 832732a0a＋worker 同步 46e4dc25f＋f1-f4 假檔 32 檔清出（wt_clean 3/3 clean）；Step 2 e015 票驗收未達門→BOUNCE（done/→open/、票內證據＋修法）；freeze_check 11/12、唯 diff_worker＝e015 WIP 3 檔）
- **較上輪好的命令：** `python3 ops/audits/g3_2_precheck.py --selftest`→VERDICT: G3_2_PRECHECK_OK（top-level seen_set＋fail-closed 恢復）＋`g3_2_fire_summary.py --selftest`→VERDICT: G3_2_FIRE_SUMMARY_SELFTEST_OK（6 負控制）＋pytest g3_2 12 passed（qwen＋worker 雙樹皆綠）；`freeze_check.py` wt_clean 由 DIRTY（worker f1-f4 殘留）→3/3 clean。
- **e015 驗收（門未達、BOUNCE）：** selftest rc=1 正控制 FAIL；根因 e015_closure_check.py:64 把 VERDICT.json 當 REPORT.json 輸入傳 e004 量具（e004_verdict.py:104 必拋「缺 paired 區塊」；r1507 實證兩路）＋pytest 3 failed＋BACKLOG 缺 CLOSURE_NOTE（舊註記裁決候 planner）；票內「All tests passed」與實測不符；票 bounced（worker 46e4dc25f；~/dev/ops/tickets/open/ 存影）、不代修。
- **收斂同步：** qwen 832732a0a（merge argon）→worker 46e4dc25f（g3_2 4＋l008 3 檔入、f1-f4 16 git rm、票 bounce）→argon 54d55fb10（l008 3）＋d736928e6（e014 2）；ref 目錄側 16 f1-f4 亦 rm（共 32 清出）。
- **誠實記帳：** 0 model calls；freeze_check 11/12（唯 diff_worker＝e015 WIP 3 檔，worker 在途重做＝12/12 唯一阻擋）；CI 未 poll（9a61b624d 2 failed＝freeze_check 狀態測試、綁 worker 在途態非 g3_2 修復本身；新 HEAD CI 候下輪一次讀取）；已知缺陷：l008 selftest 重寫 report generated_at（位元差、內容不變）、本輪已還原。
- **紅線：** 無 push（loop 自推 auto/qwen27b）、main 未動、無 reset/rebase、.github/workflows/ 只讀、hidden/scorer 未讀、未跑 full pytest。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史不改。

## 未完（≤3、交下輪）
1. 三分支新 HEAD CI 一次讀取（qwen 832732a0a＋簿記／worker 46e4dc25f＋簿記／argon d736928e6＋簿記；紅→log 根因不猜）。
2. e015 重做（worker）：load_verdict 改載 REPORT.json（或改 e015 專用 verdict 管線）＋BACKLOG CLOSURE_NOTE（舊註記裁決後）→selftest E015_CLOSURE_OK＋pytest 全綠→升三分支→freeze_check 12/12。
3. 候人類裁決：L008 樣本量/預算（未發射、0 呼叫）；e013 票（bounced/）候規劃者修驗收 grep；G 系列（vq-kax）。

## 下輪入口（≤3）
- CI 一次讀取；紅→log 根因。
- `bd list --parent vq-el4 --all` 照順序；呼叫 GLM／DeepSeek 一律用 `glm` 指令。
- 守衛：NOW.md ≤3KB、ops/loop/NOW.md 與 root byte-identical、ops/STATE.md＝canonical Current State 最新條目（bk_state 契約）。
