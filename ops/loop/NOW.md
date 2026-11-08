# NOW（r1280・2026-11-08）

## 現在在哪
- 全部工作項被人類決策阻塞：vq-el4 34/34 全閉、0 open；唯一 ready＝vq-1zf（G3）待 `--fire` 核准（12 格已凍結、g3gate 離線釘住、不點火、不入 queue）。
- 本輪＝驗證＋簿記輪（r1280、無 beads）：freeze_check 9 項全 OK（FROZEN_STATE_OK rc=0）；CI 一次讀取：LATEST 三分支皆 green（5070/0/74：qwen27b@2649cd66・argon@8dcedb5f・worker@c50de41f）、現 HEAD（c2a96a16/2d987fa1/72e401ae）無 ci/<sha>.json、state.json running qwen27b@c2a96a16；0 代碼改動、0 model calls。
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
