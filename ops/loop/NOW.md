# NOW（r1291 redo・2026-11-08）

## 現在在哪
- r1291 redo（審查點名 5 檔在 r1291 條目未開啟）：本輪全數開啟並重做依賴聲明——**0 需更正**。
  ① auto-ci.yml（63 行/2695 B、無 enabled/disabled 欄位、最後 commit r1025）：「未動」接地；disabled_manually 為平台端狀態、待人類裁決。
  ② effects_20261105_summary.json（60228 B、50 格、w2r 7/6・7/4、單 rep、current 50/50）：r1291 未引其數字→無依賴。
  ③ g25_all_gates_filing.json（4681 B）：code 3＋sources 3 sha 獨立重算＝6/6 MATCH→「filing 未改」接地。
  ④ extract.py（1217 行、blob e757aec5）⑤ repair.py（2795 行、blob 5147f8c3）：凍結行數/blob 與 r1291 條目一致。
- 狀態不變：vq-el4 37/37 全閉、0 open；freeze_check FROZEN_STATE_OK rc=0（9 項）；14 passed；G3 待人類 --fire。

## 下一步
1. 本輪新 HEAD（r1291＋本 redo）之 CI 收口一次讀取（不 poll）；確認兩分支紅燈消解。
2. 人類裁決 CI 通道前不重診斷；人類核准 G3 --fire 前不點火、不入 queue。
3. 每輪先跑 python3 ops/reqloop/freeze_check.py（9 項）確認 FROZEN_STATE_OK。

## 紅線（本輪全守住）
0 model calls・無 push（迴圈自推）・.github/workflows/ 只讀（只讀、未翻開關）・無 reset/rebase・
凍結四檔＋filing 未改・未讀 hidden/scorer・無 sleep poll・未核准不點 G3
