# NOW（r1285・2026-11-08）

## 現在在哪
- 實質修復輪（vq-el4.35 開→關）：freeze_check 計數守衛 skip 假綠燈（守衛檔 @pytest.mark.skip 禁用守衛測試＋補足量測試時「5 passed, 1 skipped」舊碼判 OK）修復＋負控制 (e) TDD RED→GREEN；35 passed、freeze_check 9 OK、VERDICT: FROZEN_STATE_OK、commit f5adfe8ab。
- vq-el4 36 項（.35 本輪 close）；唯一 open＝vq-1zf（G3）待人類 --fire（12 格已凍結、g3gate 離線釘住、不點火、不入 queue）。
- 審查點名 6 檔本輪全數開啟核對（auto-ci.yml／effects／g25 filing／ci_contract／extract／repair），依賴聲明全數成立、0 數字需更正（effects 未引數字）。
- CI 一次讀取（不 poll）：state.json running qwen27b@88e7a3f8（r1284 redo、在跑）；LATEST 三分支皆 green（qwen27b@f6e435ce5 5071/0、argon@4f0b89c5 5072/0、worker@05203065 5072/0）；本輪新 HEAD 無 ci/<sha>.json。
- G2.5 數字仍以 filing out/all/phase3.json 7/2 為準；不引舊 6/3 單測檔。

## 下一步
1. 每輪先跑 python3 ops/reqloop/freeze_check.py（9 項）；任何一項 BROKEN 先處理，不得自稱「已複核」；審查點名檔須開啟（cat／程式載入）後才可寫其依賴聲明。
2. 現 HEAD（qwen27b f5adfe8ab／argon、worker 同步後之 sha）的 ci/<sha>.json 出現即一次讀取（不 poll）：green 即記錄；red 且涉本輪改動才處理。
3. 人類核准 G3 --fire 後才點火、重讀收據＋評測、按 gate 紀律記錄（UNKNOWN 不升級）。
4. 人類裁決 CI 通道後按裁決執行（不翻 auto-ci.yml 開關、不重複診斷）。

## 紅線（本輪全守住）
0 model calls（glm CLI 未使用）・無 push（迴圈自推）・.github/workflows/ 只讀・無 reset/rebase・
凍結四檔（repair/extract/checks/run_eval）＋filing 未改・未讀 hidden/scorer・無 sleep poll・
未核准不點 G3・不引舊 6/3 單測檔・不為有 commit 改文件（不新增局部處方）
