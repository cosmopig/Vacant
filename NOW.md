# NOW（r1282・2026-11-08）

## 現在在哪
- 實質修復輪（vq-el4.34 開→關，非簿記輪）：freeze_check bk_state「零條目鏡像」假綠燈（鏡像只有標題＋表頭、無條目行，舊守衛仍判「同步」，r1282 實測）——TDD RED→GREEN：鏡像末行須＝canonical 最新條目行＋負控制。13 passed（freeze 6／anchors 5／ci_contract 2）；freeze_check 9 項 OK、FROZEN_STATE_OK rc=0；三分支同步後 in-scope diff 0×2。
- 其餘工作項仍被人類決策阻塞：vq-el4 35/35 全閉；唯一 ready＝vq-1zf（G3）待 `--fire` 核准（12 格已凍結、g3gate 離線釘住、不點火、不入 queue）。
- 待人類決策（2 項）：① G3 `--fire` 核准 ② CI 通道裁決（auto-ci.yml disabled_manually；不翻開關、不重複診斷）。
- G2.5 數字仍以 filing `out/all/phase3.json` 7/2 為準；不引舊 6/3 單測檔。
- 無新人類指示（ops/ 最新仍 11-07）、tickets/open 空、/srv/vlab/queue 空、/srv/vlab/done 不變（最新 16_e016・11-04）。

## 下一步
1. 每輪先跑 `python3 ops/reqloop/freeze_check.py`（9 項）；任何一項 BROKEN 先處理，不得自稱「已複核」。
2. 現 HEAD 的 ci/<sha>.json 出現即一次讀取（不 poll）：green 即記錄；red 且涉本輪改動才處理。
3. 人類核准 G3 `--fire` 後才點火、重讀收據＋評測、按 gate 紀律記錄（UNKNOWN 不升級）。
4. 人類裁決 CI 通道後按裁決執行。

## 紅線（本輪全守住）
0 model calls・無 push（迴圈自推）・.github/workflows/ 只讀・無 reset/rebase・
凍結四檔（repair/extract/checks/run_eval）＋filing 未改・未讀 hidden/scorer・無 sleep poll・
未核准不點 G3・不引舊 6/3 單測檔・不改文件充進度
