# NOW（r1287・2026-11-08）

## 現在在哪
- r1287 redo（審查點名接地）：6 檔全開——auto-ci.yml 63 行 blob 674b2c8f・1 job 4 步・檔內無 enabled 欄位；effects 60228 B sha a710f7e4・p30 w2r13(g7/l6)・o20 w2r11(g7/l4)・單 rep 不宣稱孰優；g25 filing 4681 B・三門 PASS(phase3 7/2、baseline 9/9・7/9)・6/6 sha MATCH；ci_contract 5857 B・2 測＋scipy 負控制；extract.py 1217 行 blob e757aec5 sha 51abfec3・4 不變量；repair.py 2795 行 blob 5147f8c3・8 不變量——依賴全成立、0 歷史條目更正（本輪初判「argon green 245/0/1」從未入條目；接地後實際 red 5070/2/74）。
- CI（一次讀、不 poll）：af255ece8（qwen27b HEAD）running（log 進行中、無 failed、5145 collected）；LATEST：qwen27b@88e7a3f86 green 5072/0/74、worker@e9e8f53d green 5072/0/74（係 worker HEAD 之祖先）、argon@103960577 **RED 5070/2/74**（2 failed＝freeze_check cover+verdict 兩測；記錄事實、不重診斷）。
- freeze_check 9 OK・FROZEN_STATE_OK（輪首 10:57:13Z＋收輪複跑）；vq-el4 36/36 全閉；G3 待人類 --fire。

## 下一步
1. 每輪先跑 python3 ops/reqloop/freeze_check.py（9 項）；審查點名檔須開啟後才可寫其依賴聲明。
2. ci/af255ece8*.json 收口即一次讀取（不 poll）：green 即記錄；red 且涉本輪改動才處理。
3. 人類裁決 CI 通道前不重診斷（argon red 已記錄）；人類核准 G3 --fire 後才點火、按 gate 紀律記錄。

## 紅線（本輪全守住）
0 model calls（glm 未用）・無 push（迴圈自推）・.github/workflows/ 只讀・無 reset/rebase・
凍結四檔（repair 2795 行／extract 1217 行／checks c7589c61／run_eval 332cd324）＋filing 未改・
未讀 hidden/scorer・無 sleep poll・未核准不點 G3
