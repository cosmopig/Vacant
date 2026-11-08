# NOW.md — r1264（2026-11-08，第 1264 輪）

## 本輪結論（一句）
CI 紅燈根因定案：`auto-ci.yml` state=**disabled_manually**（人工禁用）——26/26 紅跑（11-07 07:27–13:22）全早於 scipy 修復 3db4a7f3（11-07 13:49、在 HEAD 2bb2d306 樹內）；**紅燈修復已在樹、但從未在 GitHub 跑過**。升級人類：re-enable 見綠燈，或明示本地 CI 為正統通道。

## 事實（證據）
- `GET /repos/cosmopig/Vacant/actions/workflows`（公開 API、單調用、無輪詢）：auto-ci.yml（id 410149973）state=disabled_manually；ci.yml／publish.yml 等皆 active → r1260–1263「Actions 不觸發」＝人工禁用、非基建故障。
- runs：26 全 failure；首 fd167eaf 11-07T07:27:05Z、末 f03d1177 11-07T13:22:41Z；scipy 修復 3db4a7f3 commit 11-07T13:49:22Z；`git merge-base --is-ancestor 3db4a7f3 2bb2d306`→YES（在 HEAD）。
- 修復驗收（票 P20261107_0000-1）：`test_pin_survives_venv_symlink`（tests/test_reqloop_repair.py:1185）函式體 0 處 scipy；`pytest -k venv_symlink`→1 passed。
- 本地 CI（vacant-ci active、跑中）：qwen27b 70926581 🟢 5056/5129・argon 69b62a9b 🟢 5064/5137・worker ce4c16c2 🟢 5064/5137；2bb2d306 跑中（與最後綠 SHA 之 diff 僅簿記）。
- in-scope diff：qwen27b↔worker 0、qwen27b↔argon 0；anchors 5 passed（本輪重跑）；g3gate --plan RC 0 NOT FIRED（0 model calls）。
- bd：vq-el4.25 建→關（本輪）；vq-el4 全 25 項 closed；vq-1zf（G3）open、等人類核准。

## 下一輪先做
1. Actions 一次檢查（API 單調用）：有新跑（綠/紅）→記燈；仍無新跑→維持「等人類」、不重複診斷。
2. G2.5 等工單（vq-el4 全關）；G3 等 RLOOP_PLAN.md 明確人批（核准前禁 --fire、queue 不放新任務）。
3. 每輪守：in-scope diff 0（簿記鏡像同輪同步 worker/argon）＋三分支 anchors 5 passed＋本地 CI 綠燈。

## 紅線（本輪全守）
0 model calls（queue 空）・本輪無 git push（迴圈自動推 qwen27b）・.github/workflows/ 只讀・無 reset/rebase/branch -f・repair.py／extract.py／checks.py／run_eval.py／filing 未改・未讀 /srv/eval hidden 與 scorer.py・無 sleep 輪詢。
