# STATE.md — Vacant 現況（人類可讀；保持 ≤ 5 行）

## Current State
（2026-11-08 r1271：G2.5 主線完結、全綠（數字以 filing `out/all/phase3.json` 7/2 為準）；工作隊列空（vq-el4 28/28 閉）；唯一待辦＝兩項人類決策：① G3 `--fire` 核准（vq-1zf、12 格已備、g3gate NOT FIRED、0 model calls，未核准前禁點火／入 queue）② CI 通道裁決（auto-ci.yml 仍 disabled_manually；現 HEAD e4e7be1c/184f48bb/894d67b3 無 ci/<sha>.json、runner idle，不 poll、不翻開關）。本輪實質修復（vq-el4.28）：freeze_check 新增 bk_state／bk_now 兩項簿記鏡像檢查（TDD：先寫漂移負控制再實作；另修測試自身假綠燈——`"OK"⊂"BROKEN"` 子串誤判）——實測抓到並修復 r1266 以來的真實漂移（canonical Current State 停 r1265、mirror 停 r1270、互不一致、此前無任何機械檢查可偵測＝假綠燈），兩側更新為同一 r1271 文字、三分支對齊（in-scope diff 0×2）。驗收：freeze_check 9 項全 OK、VERDICT: FROZEN_STATE_OK rc=0；test_reqloop_freeze_check 3 passed＋anchors 5 passed＋ci-contract 2 passed。0 model calls、無 push、未讀 hidden/scorer、凍結檔未改。）
