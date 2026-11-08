# NOW（r1268・2026-11-08）

## 現在在哪
- G2.5 主線完結、全綠（數字以 filing `out/all/phase3.json` 7/2 為準；standalone `eval_phase3_glm53.json` 6/3 舊檔不得引用）。
- 本輪實質進展（vq-el4.27 已關）：31 輪來每輪 ~6 條分散手動複核指令，整合為單一指令
  `python3 ops/reqloop/freeze_check.py`（anchors／ci_contract／diff_worker／diff_argon／
  filing_code／filing_sources／g3gate_plan 七項＋`VERDICT:` 行＋rc）。
  三分支 commit：qwen27b 89eca24d／worker d35e490f／argon 29891c5e；in-scope diff 0×2；
  驗收 VERDICT: FROZEN_STATE_OK rc=0；tests/test_reqloop_freeze_check.py 2 passed。
- 自次輪起，每輪複核＝跑該指令一次、讀 VERDICT 行；任一項 BROKEN 即點名該項調查，
  不得再自稱複核過而未跑齊。
- CI：三分支最後完成皆 green（5066/5139、0 failed，LATEST_*.json 一次讀取）；r1268 新 SHA 在跑、不 poll；通道裁決（auto-ci.yml 重啟 vs local vacant-ci 為權威）等人類。
- 唯一未閉＝G3（vq-1zf）：12 格已備（g3gate --plan EXIT 0、NOT FIRED、0 model calls）、
  等人類 `--fire` 核准；未核准不點火、不入 queue。

## 下一步
1. 每輪先跑 `python3 ops/reqloop/freeze_check.py`（單一複核指令）；BROKEN 即調查該項。
2. 人類核准 G3 `--fire` → 點火後回讀 receipt＋scoring，按 gate 紀律記錄（UNKNOWN 不升級）。
3. 人類裁決 CI 通道 → 照裁決執行。

## 紅線（本輪全守）
0 model calls・無 push（迴圈自推 qwen27b）・`.github/workflows/` 只讀・無 reset/rebase/branch -f・
repair.py／extract.py／checks.py／run_eval.py／filing 未改（anchors 5 passed＋filing 3/3 MATCH）・
未讀 /srv/eval hidden 與 scorer.py・無 sleep 輪詢・G3 未核准不點火・standalone 6/3 舊檔不引用。
