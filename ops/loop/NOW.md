# NOW（r1283・2026-11-08）

## 現在在哪
- 驗證＋簿記輪（非實質）：vq-el4 35/35 全閉、0 open；唯一 open＝vq-1zf（G3）待人類 `--fire` 核准（12 格已凍結、g3gate 離線釘住、不點火、不入 queue）。
- 本輪新跑皆綠：freeze_check 9 項 OK（FROZEN_STATE_OK rc=0、簿記後末次複跑同綠）；13 passed（freeze 6／anchors 5／ci_contract 2）＋g3gate 22 passed；凍結四檔（repair 2795 行 blob 5147f8c3、extract 1217 行 blob e757aec5、checks sha c7589c61、run_eval sha 332cd324）直接重驗吻合釘值；in-scope diff 0×2。
- CI 一次讀取（不 poll）：qwen27b@f6e435ce5（r1281）收口 green（5071/0/74）；LATEST argon@401c0e18、worker@0ce81258 皆 green（5071/0/74）；現 HEAD（a5f812fa／4f0b89c5 僅 log 在跑／de6f2d60）無 ci/<sha>.json。
- 無新人類指示（ops/ 最新仍 11-07）、tickets/open 空、/srv/vlab/queue 空、done 不變（最新 16_e016・11-04）。
- G2.5 數字仍以 filing `out/all/phase3.json` 7/2 為準；不引舊 6/3 單測檔。

## 下一步
1. 每輪先跑 `python3 ops/reqloop/freeze_check.py`（9 項）；任何一項 BROKEN 先處理，不得自稱「已複核」。
2. 現 HEAD 的 ci/<sha>.json 出現即一次讀取（不 poll）：green 即記錄；red 且涉本輪改動才處理。
3. 人類核准 G3 `--fire` 後才點火、重讀收據＋評測、按 gate 紀律記錄（UNKNOWN 不升級）。
4. 人類裁決 CI 通道後按裁決執行（不翻 auto-ci.yml 開關、不重複診斷）。

## 紅線（本輪全守住）
0 model calls（glm CLI 未使用）・無 push（迴圈自推）・.github/workflows/ 只讀・無 reset/rebase・
凍結四檔（repair/extract/checks/run_eval）＋filing 未改・未讀 hidden/scorer・無 sleep poll・
未核准不點 G3・不引舊 6/3 單測檔・不為有 commit 改文件（不新增局部處方）
