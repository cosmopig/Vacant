# NOW（r1269・2026-11-08）

## 現在在哪
- G2.5 主線完結、全綠（數字以 filing `out/all/phase3.json` 7/2 為準；standalone 6/3 舊檔不得引用）。
- r1269（本輪）：單一複核指令 `python3 ops/reqloop/freeze_check.py` 新跑 → VERDICT: FROZEN_STATE_OK rc=0
  （anchors 5／ci-contract 2／diff 0×2／filing 6 sha MATCH／g3gate NOT FIRED）；
  CI 一次讀取：三分支最後完成皆 green（5066/5139・0 failed）；新 SHA（c7a08ebe/3327e413/320419c3）在跑、不 poll。
- 工作隊列為空：vq-el4 28 項全閉；唯一 ready＝vq-1zf（G3），待人類核准。
- 唯一未閉＝兩項人類決策：① G3 `--fire` 核准（12 格已備、g3gate --plan EXIT 0、0 model calls）；
  ② CI 通道裁決（auto-ci.yml 重啟 vs local vacant-ci 為權威）——按指示不重複診斷、不翻開關。

## 下一步
1. 每輪先跑 `python3 ops/reqloop/freeze_check.py`；任一項 BROKEN 即調查該項。
2. 人類核准 G3 `--fire` → 點火後回讀 receipt＋scoring，按 gate 紀律記錄（UNKNOWN 不升級）。
3. 人類裁決 CI 通道 → 新 SHA 的 ci/<sha>.json 到檔後一次讀取（不 poll），照裁決執行。

## 紅線（本輪全守）
0 model calls・無 push（迴圈自推 qwen27b）・`.github/workflows/` 只讀・無 reset/rebase/branch -f・
repair.py／extract.py／checks.py／run_eval.py／filing 未改（freeze_check FROZEN_STATE_OK）・
未讀 /srv/eval hidden 與 scorer.py・無 sleep 輪詢・G3 未核准不點火・standalone 6/3 舊檔不引用。
