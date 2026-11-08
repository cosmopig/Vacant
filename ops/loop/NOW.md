# NOW（r1273・2026-11-08）

## 現在在哪
- G2.5 主線完結、全綠（數字以 filing `out/all/phase3.json` 7/2 為準；不引舊的單測 6/3 檔）。
- vq-el4 30/30 全閉；唯一 ready＝vq-1zf（G3）待人類 --fire 核准（不點火、不入 queue）；/srv/vlab/queue 空、無新工單。
- 待人類決策（2 項）：① G3 `--fire` 核准 ② CI 通道裁決（auto-ci.yml disabled_manually；本輪 CI 一次讀取：state.json running@8269746d（現 HEAD 033953d2 之祖先）、不 poll）。
- 本輪實質修復（vq-el4.30）：freeze_check anchors/ci_contract 計數守衛——守衛檔被削、剩餘全綠時 rc=0 原判 OK（假綠燈），現要求 rc 0 且恰好 5/2 passed＋4 負控制。

## 下一步
1. 每輪先跑 `python3 ops/reqloop/freeze_check.py`（9 項）；任何一項 BROKEN 先處理，不得自稱「已複核」。
2. 現 HEAD 的 ci/<sha>.json 一旦出現，一次讀取（不 poll）：green 即記錄；red 且涉本輪改動才處理。
3. 人類核准 G3 `--fire` 後：點火、重讀收據＋評測、按 gate 紀律記錄（UNKNOWN 不升級）。
4. 人類裁決 CI 通道後：按裁決執行（不重複診斷、不翻 auto-ci.yml 開關）。

## 紅線（本輪全守住）
0 model calls・無 push（迴圈自推 qwen27b）・.github/workflows/ 只讀・無 reset/rebase/branch -f・
repair.py/extract.py/checks.py/run_eval.py/filing 未改・未讀 /srv/eval hidden 或 scorer.py・無 sleep poll・
未核准不點 G3・不引舊 6/3 單測檔・不改文件充進度
（本輪＝1 檔 freeze_check.py＋4 新負控制測試＋1 條指令輸出由假綠變真綠）
