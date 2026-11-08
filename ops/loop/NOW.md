# NOW（r1272・2026-11-08）

## 現在在哪
- G2.5 主線完結、全綠（數字以 filing `out/all/phase3.json` 7/2 為準；不引舊的單測 6/3 檔）。
- 工作隊列空：vq-el4.29 本輪已閉（bk_now 空檔假綠燈修復）；唯一 ready＝vq-1zf（G3）待人類核准；/srv/vlab/queue 空、無新工單。
- 待人類決策（2 項）：① G3 `--fire` 核准 ② CI 通道裁決（auto-ci.yml disabled_manually；現 HEAD qwen27b 8269746d／argon c0e808af 無 ci/<sha>.json、runner idle、不 poll；worker c4c83e61 green 5069）。
- 本輪實質修復（vq-el4.29）：freeze_check bk_now 非空守衛＋負控制——兩份 NOW.md 皆 0B 時舊碼仍判 OK（空集測量、I-4「未測量不是通過」），現任一侧 0B→BROKEN。

## 下一步
1. 每輪先跑 `python3 ops/reqloop/freeze_check.py`（9 項）；任何一項 BROKEN 先處理，不得自稱「已複核」。
2. 現 HEAD 的 ci/<sha>.json 一旦出現，一次讀取（不 poll）：green 即記錄；red 且涉本輪改動才處理。
3. 人類核准 G3 `--fire` 後：點火、重讀收據＋評測、按 gate 紀律記錄（UNKNOWN 不升級）。
4. 人類裁決 CI 通道後：按裁決執行（不重複診斷、不翻 auto-ci.yml 開關）。

## 紅線（本輪全守住）
0 model calls・無 push（迴圈自推 qwen27b）・.github/workflows/ 只讀・無 reset/rebase/branch -f・
repair.py/extract.py/checks.py/run_eval.py/filing 未改・未讀 /srv/eval hidden 或 scorer.py・無 sleep poll・
未核准不點 G3・不引舊 6/3 單測檔・不改文件充進度
（本輪＝1 檔 freeze_check.py＋1 新負控制測試＋1 條指令輸出由假綠變真綠）
