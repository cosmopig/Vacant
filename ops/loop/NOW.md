# NOW — r1296・2026-11-09

## 現在在哪
- r1296（實質修復，vq-el4.38 開→關）：freeze_check filing 覆蓋集身份假綠燈——filing key 未守：key 被替換成另一條真條目（檔存在、sha 真）後凍結檔失覆蓋、舊碼仍判 3/3 MATCH（RED 實證：run_eval.py→decoy.py 判 OK、phase3→phaseX 判 OK；r1273 同型；H-0；I-4）。
- 修復（TDD：負控制 RED → 守衛 → GREEN）：check_filing_code/check_filing_sources 加三層 COVERAGE 身份守衛——code key 集＝恰 3 份凍結檔；sources key 集＝phase1/2/3；派生 tail 集＝3 份互異 phase 檔——＋負控制 test_filing_key_substitution_negative_control（a key 替換／b key 改名／c 路徑重指→BROKEN；正控制 canonical＋真 sha→OK）；2 舊 null-sha fixture 改 canonical key（語義保持）。
- 驗收（本輪新跑）：16 passed（freeze_check 9 含新負控制／anchors 5／ci_contract 2）＋freeze_check 9 項全 OK、VERDICT: FROZEN_STATE_OK rc=0。
- CI：worker@32a6a010 進行中、qwen27b@3716a100 排隊（本輪未 poll、未新讀 artifact）；LATEST 三分支皆綠（qwen27b@4c207cc2 5074/0/74、worker@72652457 5073/0/74、argon@e392be8a 5074/0/74）。
- 隊列：vq-el4 39/39 全閉（含本輪 vq-el4.38 關）；唯一 open＝vq-1zf G3 待人類 --fire 核准（不點火、不入 queue）；無新人類指示、tickets/open 空、/srv/vlab/queue 空。

## 下一步
1. 下輪：一次讀 worker@32a6a010／qwen27b@3716a100（現 HEAD）之 CI（仍無 artifact＝記錄在跑、不 poll）；本輪 commit 新 HEAD 亦同（下輪一次讀）。
2. 人類未裁決前不重診斷 CI 通道（auto-ci.yml disabled_manually、不翻開關）；人類未核准前不點 G3 --fire、不入 queue。
3. 每輪結束前跑 `python3 ops/reqloop/freeze_check.py`（9 項）確認 FROZEN_STATE_OK（rc=0）。

## 紅線（本輪皆守住）
0 model calls・無 push（迴圈自推）・.github/workflows/ 只讀・無 reset/rebase・
凍結四檔＋filing 未改・未讀 hidden/scorer・無 sleep poll・未核准不點 G3・未以改文件湊進展
（本輪指令輸出優於上輪：上輪 key 替換的削弱備案判「3/3 MATCH」OK、本輪起判 BROKEN）
