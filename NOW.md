# NOW.md — r1263＋redo（2026-11-08，第 1263 輪）

## 本輪結論（一句）
[redo] 審查點名 extract.py／g3gate.py／repair.py 在記錄中未開啟 → 三檔全部開啟（head＋ast 載入）並逐項重驗依賴項：舊簿記「extract.py(901)」更正為實核 1217 行／blob e757aec5（與 anchor 釘值、審查點名一致）；g3gate --plan RC 0「NOT FIRED」（G3 未發機械化重驗）；filing 3 sha256 MATCH。
[原 r1263] Actions 停擺實證（remote 6b19961d 已達、26 跑無新跑 → Actions 基建需人工）；三分支對齊清零（worker 補守門測試檔 → in-scope diff 1→0、argon ff 同 HEAD、7 passed×3 分支）。

## 事實（證據）
- 三檔開啟＋載入（ast.parse OK）：extract.py 1217 行／28 defs／blob e757aec5；g3gate.py 340 行／11 defs／blob 0d90f166；repair.py 2795 行／56 defs／blob 5147f8c3。
- anchor 測試對照（tests/test_reqloop_frozen_anchors.py）：repair 5147f8c3・2795 與 extract e757aec5・1217＝審查指示#1 點名值，全吻合；**舊簿記「extract.py(901)」誤載（r1260–1262 相傳），本 redo 更正 1217**。
- g3gate.py 無 subprocess／模型呼叫（僅預算欄位 model_entry="glm" 校驗）→ --plan 純離線：`python -m vacant_network.reqloop.g3gate --plan` → RC 0、「NOT FIRED（無核准信號；0 model calls）」、verify_frozen OK（4 題×4 輸入檔 sha256 全核）、budget gate OK。
- filing code 3 sha256 重核：extract 51abfec3／checks c7589c61／run_eval 332cd324 全 MATCH。
- [原] GitHub API：auto-ci.yml 26 跑、最後 f03d1177 11-07 13:22 failure；remote auto/qwen27b＝6b19961d＝local HEAD → push 到達未觸發＝Actions 端問題。PAT 讀通道 401（改公開免-auth API）；迴圈 push 通道正常。
- [原] worker 補 tests/test_reqloop_ci_contract.py（sha256 一致）→ in-scope diff 0；argon ff-only 同 HEAD；7 passed×3 分支。
- 工單 vq-el4.23（建→關）、vq-el4.24 redo（建→關）。

## 下一輪先做
1. Actions 一次檢查（API 單調用，別 sleep 輪詢）：新跑綠→紅解除；新跑紅→乾淨 venv 複現修；仍無新跑→升級人工（已二次實證非本地可修）。
2. 主線 G2.5（vq-el4）子項全關；queue 空、0 model calls、等工單。G3（vq-1zf）未發——等 RLOOP_PLAN.md 人批；核准前禁 --fire。
3. 每輪守：in-scope diff 0（含簿記鏡像，新檔進 qwen27b 須同輪同步 worker）＋三分支 7 passed。

## 紅線（本輪全守）
0 model calls（queue 空；g3gate --plan 為離線前置門、非發射）・本輪無 git push（迴圈自動推 qwen27b）・無 reset/rebase/branch -f（argon 僅 ff-only）・未讀 /srv/eval hidden 與 scorer.py・repair.py／extract.py／g3gate.py／checks.py／run_eval.py／filing 未改（本輪只讀驗證）・.github/workflows/ 未改・無 sleep 輪詢。
