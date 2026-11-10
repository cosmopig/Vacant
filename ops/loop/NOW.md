# NOW — r1370 (2026-11-10)

## Current State
- vq-el4 全數任務已關（65/65）；全庫唯一 open＝vq-1zf（G3、待人類 --fire）。
- 本輪 redo（審查點名 4 檔實際開檔核實、非引 tool 輸出代讀）：effects 50 格
  13w0r g7l6／11w0r g7l4（sha a710f7e4…）；filing 3 門 PASS＋6 sha 全在檔；
  extract.py 1217 行/blob e757aec5…（discard/白名單/fail-closed/required=True/
  hidden=False/GlmClient 只走 glm）；repair.py 2795 行/blob 5147f8c3…（原草稿保留/
  source_tampered→20/FAIL→UNKNOWN 不算修好/STOP_STALLED/缺口關閉＝全部必需項 PASS）
  ——record 所引全數有碼。
- 驗收全綠（本輪全數新跑）：freeze_check 11/11 OK rc0；ves 7/7 OK rc0；守衛 4 檔
  48 passed＋g3gate 22＝70 passed；GUARD_CONTENT_PIN 7 檔；in-scope diff 0×2；
  queue 空（含隱藏）；g3gate NOT_FIRED。
- CI：三分支最後完成（r1368）皆 GREEN 5107/0/74（qwen27b@c02588db6／worker@62010b70b／
  argon@1cd8805d5）；r1369 HEAD per-sha 未出→UNKNOWN、worker@ef5674e5 running（不 poll）。
- 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決。

## Next Step (r1371)
1. CI 一次讀取：r1369 HEAD（89d6650a/ef5674e5/8651ea64）per-sha → 記 GREEN/RED（不 poll、不等待）。
2. 維持驗收：freeze_check 11/11 OK；ves 7/7 OK；守衛 70 passed；in-scope diff 0×2；queue 空（含隱藏）；g3gate NOT_FIRED。
3. 待人類：G3 --fire（vq-1zf）。

## Red lines
- 無 push；.github/workflows/ 只讀；不讀 /srv/eval/hidden/ 或 scorer.py；G3 未經人類核准不得發射（不代發 --fire、不入 queue）；/srv/vlab/queue/ 不放任務；無 reset/rebase；凍結檔（repair.py 2795 行、extract.py 1217 行、checks.py、run_eval.py）與 filing 不改；只跑相關測試、不自啟 full pytest；無 sleep poll CI。
