# NOW.md — 現況唯一真源

## 位置
2026-11-09 r1311 redo：redo 審查點出 effects_20261105_summary.json 在任務點名、r1311 記錄步驟未實開；本輪實開＋獨立重算依賴數字全一致、0 更正；freeze_check 10/10 OK＋7 passed；跨分支已同步。0 模型呼叫。

## 數字（本輪實測著地）
- effects summary 實開（60228 B／sha a710f7e4 重算未變）：policy30 w2r g7/l6 r2w0、sessions 19+16=35／API 365+550=915／tokens 33670510；once20 w2r g7/l4 r2w0、sessions 10+10=20／API 165+292=457／tokens 19503953；scope_note＝開發選樣（e008/e013/e014 已見題）、單 rep 不宣稱 localized 優、不宣稱等 token、hidden_after 全 UNKNOWN、缺值 None 不填 0（與 11-06 指示逐項一致）
- freeze_check 10/10 OK VERDICT: FROZEN_STATE_OK rc=0（anchors 5／ci_contract 2／diff 0×2／filing code 3/3＋sources 3/3 MATCH／g3gate NOT_FIRED＋PLAN_OK／bk_state 同步／bk_now byte-identical／wt_clean 3/3 clean）
- 守衛測試 7 passed（test_reqloop_frozen_anchors.py 5＋test_reqloop_ci_contract.py 2）
- 凍結 4 檔：repair.py 2795 行／blob 5147f8c3、extract.py 1217 行／blob e757aec5、checks c7589c61、run_eval 332cd324（anchor pin 未變）
- g2.5 filing：code sha 51abfec3/c7589c61/332cd324＋sources 3c6fb35a/6b7cb831/ada235bb（3/3 MATCH、未改）
- CI 一次讀取（不 poll）：LATEST 三分支皆 green（qwen27b@31dbb6c11 5079/0/74、argon@0959f8560 5078/0/74、worker@d7d64fc48 5078/0/74）；現 HEAD（qwen27b@31dbb6c11 running、argon@89c378c83、worker@7443c8695）無 ci/<sha>.json

## 待辦（依序）
1. 待人類：G3 --fire（vq-1zf）——不點火、不入 queue
2. 待人類：CI 通道裁決（auto-ci.yml disabled_manually＝服務端狀態；不重診斷、不翻開關）
3. 下輪：三分支現 HEAD 之 CI 首一次讀取（qwen27b 31dbb6c11 本輪在跑／argon 89c378c83／worker 7443c8695）；維持審查指示（凍結錨守衛＋CI 合約、fail-closed、輪末 VERDICT: FROZEN_STATE_OK）
4. vq-el4 49/49 全閉；/srv/vlab/queue 空；無新人類指示（ops/ 最新仍 11-07＋附帶審查）

## 紅線
- 不碰 main；不自 push（loop 自推）；.github/workflows/ 只讀；不讀 /srv/eval hidden＋scorer
- 凍結 4 檔＋g2.5 filing 不改；/srv/vlab/queue 不放新任務
- 缺值＝UNKNOWN（None）不填 0；不宣稱 localized 優於 generic；不宣稱等 token
- G3 待人類 --fire；無 reset/rebase；無 sleep poll；0 模型呼叫；不以改文件湊進展
