# NOW（r1278・2026-11-08）

## 現在在哪
- 全部工作項被人類決策阻塞：vq-el4 32/32 全閉、0 open；唯一 ready＝vq-1zf（G3）待 `--fire` 核准（12 格已凍結、g3gate 離線釘住、不點火）。
- 本輪＝實質修復輪（r1278、vq-el4.31）：freeze_check bk_state 截斷假綠燈（截斷鏡像仍是 byte 前綴→舊碼判 OK）——TDD 負控制 (f)(g) RED→GREEN；0 代碼改動限 freeze_check.py＋其測試、0 model calls。
- 待人類決策（2 項）：① G3 `--fire` 核准 ② CI 通道裁決（auto-ci.yml disabled_manually；不翻開關、不重複診斷）。
- G2.5 數字仍以 filing `out/all/phase3.json` 7/2 為準；不引舊 6/3 單測檔。
- CI：state.json running auto/qwen27b@2649cd66（現 HEAD）、一次讀取、不 poll。

## 下一步
1. 每輪先跑 `python3 ops/reqloop/freeze_check.py`（9 項）；任何一項 BROKEN 先處理，不得自稱「已複核」。
2. 現 HEAD 的 ci/<sha>.json 出現即一次讀取（不 poll）：green 即記錄；red 且涉本輪改動才處理。
3. 人類核准 G3 `--fire` 後才點火、重讀收據＋評測、按 gate 紀律記錄（UNKNOWN 不升級）。
4. 人類裁決 CI 通道後按裁決執行。

## 紅線（本輪全守住）
0 model calls・無 push（迴圈自推）・.github/workflows/ 只讀・無 reset/rebase・
凍結四檔（repair/extract/checks/run_eval）＋filing 未改・未讀 hidden/scorer・無 sleep poll・
未核准不點 G3・不引舊 6/3 單測檔・不改文件充進度
