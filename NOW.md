# NOW — r1369 (2026-11-10)

## Current State
- vq-el4 全數任務已關（65/65、含本輪 vq-el4.65）；全庫唯一 open＝vq-1zf（G3、待人類 --fire）。
- CI：qwen27b@c02588db6 GREEN（5107 passed/0 failed/74 skipped，本輪收口 r1368 之 UNKNOWN）；worker@08790f95b 未跑；argon@1cd8805d5 running（不 poll）。
- 驗收全綠（本輪全數新跑）：freeze_check 11/11 OK rc0；ves 7/7 OK rc0；守衛 48 passed；in-scope diff 0×2；queue 空（含隱藏）；g3gate NOT_FIRED；凍結 4 檔＋filing 未改（filing 6/6）。
- 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決。

## Next Step (r1370)
1. CI 一次讀取：worker@08790f95b・argon@1cd8805d5 per-sha → 記 GREEN/RED（不 poll、不等待）。
2. 維持驗收：freeze_check 11/11 OK；ves 7/7 OK；守衛 48 passed；in-scope diff 0×2；queue 空（含隱藏）；g3gate NOT_FIRED；凍結 4 檔＋filing 未改。
3. 待人類：G3 --fire（vq-1zf）。

## Red lines
- 無 push；.github/workflows/ 只讀；不讀 /srv/eval/hidden/ 或 scorer.py；G3 未經人類核准不得發射（不代發 --fire、不入 queue）；/srv/vlab/queue/ 不放任務；無 reset/rebase；凍結檔（repair.py 2795 行、extract.py 1217 行、checks.py、run_eval.py）與 filing 不改；只跑相關測試、不自啟 full pytest；無 sleep poll CI。
