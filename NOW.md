# NOW — r1375 (2026-11-10)

## Current State
- r1375 redo（審查點名 4 檔直接開啟＋依賴值獨立重算）：effects summary 60,228 B（a710f7e4…）聚合自 cells_detail 重算全 MATCH（50 cells、w2r 13+11、g7/l6 與 g7/l4、r2w 0、local 27/18、current 30/20、sess 35/20、api 915/457、tok 33.67M/19.50M、mismatch 3/2 格）；g25 filing 4,681 B 6 sha256 獨立重算全 MATCH＋三門 PASS（g1 39/39、real14 9/9、phase3 9 cells fixed 7 unresolved 2）；extract.py 1217 行 e757aec5、repair.py 2795 行 5147f8c3 實開＋docstring 規則確認——r1375 依賴值全成立、條目不改。
- r1375 維護驗證（NOW r1374 下一步全數執行＋審查 #5 核驗，0 產品改動）：CI 一次讀取 3 HEAD（qwen27b@dde6ea83b／worker@9feed7670／argon@39eb6a5f3）無 per-sha json→全 UNKNOWN（pending、不 poll）。
- 驗收全綠（本輪全數新跑）：freeze_check 11/11 OK VERDICT: FROZEN_STATE_OK rc=0（diff 0×2、wt 3/3、filing 6/6 MATCH、queue 空含隱藏、g3gate NOT_FIRED+PLAN_OK、bk 同步）；守衛 6 檔 86 passed（freeze 22／anchors 5／ci 2／ves 19／g3gate 22／g3 16）；ves 7/7 OK。
- 審查 #5：2dd0d4891（auto/argon）為 argon HEAD 祖先、662987424 亦祖先、in-scope diff 0×2→合併已完成、審查通過、無需動作。
- 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決。

## Next Step (r1376)
1. CI 一次讀取：三分支 HEAD per-sha（含本輪新 commit）→記 GREEN/RED/UNKNOWN（不 poll、不等待）。
2. 維持驗收：freeze_check 11/11 OK；守衛 86 passed；in-scope diff 0×2；queue 空（含隱藏）；g3gate NOT_FIRED。
3. 待人類：G3 --fire（vq-1zf）。

## Red lines
- 無 push；.github/workflows/ 只讀；不讀 /srv/eval/hidden/ 或 scorer.py；G3 未經人類核准不得發射（不代發 --fire、不入 queue）；/srv/vlab/queue/ 不放任務；無 reset/rebase；凍結檔（repair.py 2795 行、extract.py 1217 行、checks.py、run_eval.py）與 filing 不改；只跑相關測試、不自啟 full pytest；無 sleep poll CI；0 模型呼叫。
