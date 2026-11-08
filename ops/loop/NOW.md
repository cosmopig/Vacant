# NOW（r1286・2026-11-08）

## 現在在哪
- r1286 redo（審查點名接地）：點名 6 檔全數開啟重驗——auto-ci.yml（63 行、sha 3f1e05e9、檔內無 enabled 欄位）、effects summary（60228 B、sha a710f7e4、phases 巢狀、p30 w2r13 g7/l6・o20 w11 g7/l4、current 50/50・local 45）、g25 filing（4681 B、sha 6e5afb46、code 3 sha＝51abfec3/c7589c61/332cd324）、ci_contract（5857 B、2 測＋scipy 負控制）、extract.py（1217 行 blob e757aec5 sha 51abfec3）、repair.py（2795 行 blob 5147f8c3）——依賴聲明全數成立、0 數字更正。
- r1286 主體：freeze_check 9 OK、VERDICT: FROZEN_STATE_OK；vq-el4 36/36 全閉、唯一 open＝vq-1zf（G3）待人類 --fire；CI 一次讀取（不 poll）：argon@103960577 在跑、LATEST qwen27b@88e7a3f8 green（5072/0/74）、worker@05203065 green；現 HEAD qwen27b@19368d43 無 ci/<sha>.json。
- 無新人類指示（ops/ 最新 11-07）、tickets/open 空、/srv/vlab/queue 空。

## 下一步
1. 每輪先跑 python3 ops/reqloop/freeze_check.py（9 項）；任何一項 BROKEN 先處理；審查點名檔須開啟（cat／程式載入）後才可寫其依賴聲明。
2. ci/19368d437*.json（或新 HEAD sha）出現即一次讀取（不 poll）：green 即記錄；red 且涉本輪改動才處理。
3. 人類核准 G3 --fire 後才點火、重讀收據＋評測、按 gate 紀律記錄（UNKNOWN 不升級）。
4. 人類裁決 CI 通道後按裁決執行（不翻 auto-ci.yml 開關、不重複診斷）。

## 紅線（本輪全守住）
0 model calls（glm CLI 未使用）・無 push（迴圈自推）・.github/workflows/ 只讀・無 reset/rebase・
凍結四檔（repair 2795 行／extract 1217 行／checks c7589c61／run_eval 332cd324）＋filing 未改・未讀 hidden/scorer・無 sleep poll・
未核准不點 G3・不引舊 6/3 單測檔・不為有 commit 改文件（本 redo＝依協議接地複核）
（MEMORY 上限 6 KB、NOW 上限 3 KB；超過的部分沒有附上，請先把它縮短）
