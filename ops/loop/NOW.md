# NOW.md — r1264＋redo（2026-11-08，第 1264 輪）

## 本輪結論（一句）
CI 紅燈根因定案：`auto-ci.yml` state=**disabled_manually**（人工禁用）——26/26 紅跑（11-07 07:27–13:22）全早於 scipy 修復 3db4a7f3（11-07 13:49、在 HEAD 2bb2d306 樹內）；**紅燈修復已在樹、但從未在 GitHub 跑過**。升級人類：re-enable 見綠燈，或明示本地 CI 為正統通道。

## 事實（證據，本輪全部直接開啟/重算）
- `GET /repos/cosmopig/Vacant/actions/workflows`（公開 API、單調用）：auto-ci.yml（id 410149973）state=disabled_manually；ci.yml／publish.yml 皆 active →「Actions 不觸發」＝人工禁用、非基建故障。
- runs：26 全 failure；首 fd167eaf 11-07T07:27:05Z、末 f03d1177 11-07T13:22:41Z；scipy 修復 3db4a7f3 commit 11-07T13:49:22Z；`git merge-base --is-ancestor 3db4a7f3 2bb2d306`→YES；`test_pin_survives_venv_symlink`（tests/test_reqloop_repair.py:1185）函式體 0 處 scipy，`pytest -k venv_symlink`→1 passed。
- 本地 CI（本輪重算自 ~/dev/ops/ci/<sha>.json，code 載入＋head 抽驗；vacant-ci active）：qwen27b 與 argon 最新完成 CI @ **2bb2d306** 🟢 **5066 passed／74 skipped／5139 collected**（0 failed；現 HEAD c6810bb7/d697673c 跑中）；worker 最新完成 @ **ce4c16c2** 🟢 **5064 passed／5137 collected**（0 failed；HEAD 27d0f9b4 跑中）。
- effects 審計（**ops/audits/effects_20261105_summary.json 本輪開啟**；blob 856c2c71／file sha256 a710f7e4）：policy30 30 cells w2r 13(g7/l6)・r2w 0・pg 10・sw 7；once20 20 cells w2r 11(g7/l4)・r2w 0・sw 9；共 50 cells、**current-code 重驗 50/50 與獨立評分一致**、local(d38d2eb2 舊 checker) 45/50（5 分歧全歸因舊 checker）；scope_note＝開發選樣（已見題）、非未見任務效力、單 rep。
- anchors 釘值（**extract.py／repair.py 本輪直接開啟**：head＋wc -l＋git hash-object）：repair.py **2795 行／5147f8c3**ea1b…、extract.py **1217 行／e757aec5**0c16…；anchors 5 passed×3 分支；in-scope diff qwen27b↔worker 0、↔argon 0；g3gate --plan RC 0 NOT FIRED（0 model calls）。
- bd：vq-el4 全 25 項 closed；vq-1zf（G3）open 等人類核准；vq-el4.25（r1264）closed、vq-el4.26（本 redo）closed。

## 下一輪先做
1. Actions 一次檢查（API 單調用）：有新跑（綠/紅）→記燈；仍無新跑→維持「等人類」、不重複診斷。
2. G2.5 等工單（vq-el4 全關）；G3 等 RLOOP_PLAN.md 明確人批（核准前禁 --fire、queue 不放新任務）。
3. 每輪守：in-scope diff 0（簿記鏡像同輪同步 worker/argon）＋三分支 anchors 5 passed＋本地 CI 綠燈。

## 紅線（本輪全守）
0 model calls（queue 空）・本輪無 git push（迴圈自動推 qwen27b）・.github/workflows/ 只讀・無 reset/rebase/branch -f・repair.py／extract.py（本輪直接開啟重算、未變）／checks.py／run_eval.py／filing 未改・未讀 /srv/eval hidden 與 scorer.py・無 sleep 輪詢。
