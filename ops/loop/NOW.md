# NOW（r1289 redo・2026-11-08）

## 現在在哪
- r1289 redo（審查點名 3 檔在 r1289 記錄步驟未開啟）：本輪全數開啟並逐項複核 r1289 條目之依賴聲明——**0 需更正**。
  ① auto-ci.yml（63 行/2695 B、sha 3f1e05e9、三分支同 blob 674b2c8f）：紅線「.github/workflows/ 只讀」成立（未改、無檔內開關、disabled_manually 待人類裁決、未翻開關）。
  ② test_reqloop_ci_contract.py（131 行/5857 B、恰 2 測、未弱化）：freeze_check「ci_contract 2 passed」接地成立。
  ③ effects_20261105_summary.json（60228 B、50 格、policy30 w2r g7/l6・once20 w2r g7/l4、單 rep 不宣稱較好、current 50/50）：r1289 條目未引 effects 數字→無依賴需重改。
- 狀態不變：vq-el4 37/37 全閉、0 open；freeze_check FROZEN_STATE_OK rc=0；test_reqloop_freeze_check 7 passed；G3 待人類 --fire。

## 下一步
1. 每輪先跑 python3 ops/reqloop/freeze_check.py（9 項）；審查點名檔須開啟後才可寫其依賴聲明。
2. 本輪新 commit 之 ci/<sha>.json 收口即一次讀取（不 poll）；red 且涉本輪改動才處理。
3. 人類裁決 CI 通道前不重診斷；人類核准 G3 --fire 後才點火、按 gate 紀律記錄。

## 紅線（本輪全守住）
0 model calls・無 push（迴圈自推）・.github/workflows/ 只讀・無 reset/rebase・
凍結四檔＋filing 未改・未讀 hidden/scorer・無 sleep poll・未核准不點 G3
