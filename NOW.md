# NOW（r1288・2026-11-08）

## 現在在哪
- r1288（實質修復、vq-el4.36 開→關）：freeze_check filing 守衛 null-sha 假綠燈——備案 sha256 為 null（未 pin＝未測量）且檔不存在時，舊碼 `mine == meta["sha256"]` 變 None == None → True，「3/3 MATCH」假綠燈（RED 實測：六 sha 全 null 備案 filing_sources 判 OK）。TDD 負控制→RED→修（pin 與實算 sha 皆非 null 才 MATCH）→GREEN。驗收：36 passed（freeze 7 含新負控制／anchors 5／ci_contract 2／g3gate 22）＋freeze_check 9 OK・FROZEN_STATE_OK rc=0。
- CI（一次讀、不 poll）：LATEST qwen27b@af255ece8 green 5072/0/74（r1286 redo commit、現收口）；worker@e9e8f53d green 5072/0/74；argon@103960577 **RED 5070/2/74**（2 failed＝freeze_check cover+verdict 兩測；已記錄、不重診斷、待人類裁決）；state.json running argon@3a332768；現 qwen27b HEAD b34f28b8 無 ci artifact。
- vq-el4 37/37 全閉；vq-1zf G3 待人類 --fire（不點火、不入 queue）。

## 下一步
1. 每輪先跑 python3 ops/reqloop/freeze_check.py（9 項）；審查點名檔須開啟後才可寫其依賴聲明。
2. 本輪新 commit 之 ci/<sha>.json 收口即一次讀取（不 poll）：green 即記錄；red 且涉本輪改動才處理。
3. 人類裁決 CI 通道前不重診斷（argon red 已記錄）；人類核准 G3 --fire 後才點火、按 gate 紀律記錄。

## 紅線（本輪全守住）
0 model calls（glm 未用）・無 push（迴圈自推）・.github/workflows/ 只讀・無 reset/rebase・
凍結四檔（repair 2795 行／extract 1217 行／checks c7589c61／run_eval 332cd324）＋filing 未改・
未讀 hidden/scorer・無 sleep poll・未核准不點 G3
