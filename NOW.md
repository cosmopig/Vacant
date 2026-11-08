# NOW（r1270・2026-11-08）

## 現在在哪
- G2.5 主線完結、全綠（數字以 filing `out/all/phase3.json` 7/2 為準；standalone 6/3 舊檔不得引用）。
- 本輪 r1270（新跑）：freeze_check → VERDICT: FROZEN_STATE_OK rc=0
  （anchors 5／ci-contract 2／diff 0×2／filing 6 sha MATCH／g3gate NOT FIRED＋PLAN OK）。
- CI 一次讀取：LATEST 三分支皆 green（5066/5139・0 failed・74 skipped，@8c82ff24/876f4927/d5d6f2af）；
  現 HEAD f7627783/1760ae14/cf1b939f 在跑（state.json：worker running），不 poll。
- 工作隊列空：vq-el4 28/28 閉；唯一 ready＝vq-1zf（G3）待人類核准；/srv/vlab/queue 空。
- 衛生修復（指示#3）：ops/STATE.md＋ops/loop/NOW.md 簿記鏡像自 r1265 後未同步（r1266–1269 跳過）——
  本輪同步至 r1270 狀態並對齊三分支，in-scope diff 0×2。

## 下一步
1. 每輪先跑 `python3 ops/reqloop/freeze_check.py`；任一項 BROKEN 即調查該項。
2. 現 HEAD（f7627783/1760ae14/cf1b939f）ci/<sha>.json 到檔後一次讀取（不 poll）：綠則記錄；紅且屬本次變更相關才修。
3. 人類核准 G3 `--fire` → 點火後回讀 receipt＋scoring，按 gate 紀律記錄（UNKNOWN 不升級）。
4. 人類裁決 CI 通道 → 照裁決執行（不重複診斷、不翻 auto-ci.yml 開關）。

## 紅線（本輪全守）
0 model calls・無 push（迴圈自推 qwen27b）・.github/workflows/ 只讀・無 reset/rebase/branch -f・
repair.py/extract.py/checks.py/run_eval.py/filing 未改（freeze_check FROZEN_STATE_OK）・
未讀 /srv/eval hidden 與 scorer.py・無 sleep 輪詢・G3 未核准不點火・standalone 6/3 舊檔不引用。
