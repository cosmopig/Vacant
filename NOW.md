# NOW（r1284・2026-11-08）

## 現在在哪
- 驗證＋簿記輪（非實質）：vq-el4 35/35 全閉、0 open；唯一 open＝vq-1zf（G3）待人類 `--fire` 核准（12 格已凍結、g3gate 離線釘住、不點火、不入 queue）。
- r1284 redo：審查點名五檔已開啟複核（auto-ci.yml 63 行 sha 3f1e05e9… 未變、無檔內開關、四步真測；effects summary 60228 B sha a710f7e4… 未變、本輪未引其數字；g25 filing 4681 B sha 6e5afb46… 未變、三門全 PASS、phase3 7/2、6 sha 獨立重算 6/6 MATCH；extract.py 1217 行 blob e757aec5 sha 51abfec3 未變；repair.py 2795 行 blob 5147f8c3 未變）；r1284 條目依賴聲明全數成立、0 數字需更正。
- 本輪新跑皆綠：freeze_check 9 項 OK（FROZEN_STATE_OK rc=0、簿記後末次複跑同綠）；35 passed（freeze 6／anchors 5／ci_contract 2／g3gate 22）；凍結四檔＋filing 由 anchors 5 passed＋filing 3/3 MATCH 機械化釘住（本輪新鮮）。
- CI 一次讀取（不 poll）：現 HEAD qwen27b@898f8f12／argon@84273567／worker@3e7f9518 無 ci/<sha>.json；LATEST qwen27b@f6e435ce5 green（5071/0/74）、argon@4f0b89c5 green（5072/0/74）、worker@0ce81258 green（5071/0/74）；state.json running worker@05203065（舊 commit＝worker HEAD 之父、在跑）。
- 無新人類指示（ops/ 最新仍 11-07）、reviews/ 最新 20261108_1735＝本輪 0 工單；tickets/open 空、/srv/vlab/queue 空、done 不變（最新 16_e016・11-04）。
- G2.5 數字仍以 filing `out/all/phase3.json` 7/2 為準；不引舊 6/3 單測檔。

## 下一步
1. 每輪先跑 `python3 ops/reqloop/freeze_check.py`（9 項）；任何一項 BROKEN 先處理，不得自稱「已複核」。審查點名的檔必須開啟（cat／程式載入）後才可寫其依賴聲明。
2. 現 HEAD（898f8f12／84273567／3e7f9518）的 ci/<sha>.json 出現即一次讀取（不 poll）：green 即記錄；red 且涉本輪改動才處理。
3. 人類核准 G3 `--fire` 後才點火、重讀收據＋評測、按 gate 紀律記錄（UNKNOWN 不升級）。
4. 人類裁決 CI 通道後按裁決執行（不翻 auto-ci.yml 開關、不重複診斷）。

## 紅線（本輪全守住）
0 model calls（glm CLI 未使用）・無 push（迴圈自推）・.github/workflows/ 只讀・無 reset/rebase・
凍結四檔（repair/extract/checks/run_eval）＋filing 未改・未讀 hidden/scorer・無 sleep poll・
未核准不點 G3・不引舊 6/3 單測檔・不為有 commit 改文件（不新增局部處方）
