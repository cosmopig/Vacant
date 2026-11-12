# NOW.md — 現況（每輪覆寫、≤3KB）

## 狀態（2026-11-12 r1513；票 P20261112_1528-1 e009 結案複核量具完成：VERDICT: E009_CLOSURE_OK＋3 passed RC=0；commit acd51b0e4；0 model calls、0 行產品碼）
- **產物：** ops/audits/e009_closure_check.py（140 行、純 stdlib、CI-home 兼容：簿記目錄＝REPO.parent/ops、不依賴 Path.home()）＋tests/test_e009_closure_check.py（54 行、3 測試）。
- **驗收（本輪新跑）：** `python3 ops/audits/e009_closure_check.py --selftest && pytest tests/test_e009_closure_check.py -q`→VERDICT: E009_CLOSURE_OK、RC=0；無 -q 複跑「3 passed in 0.13s」；非 selftest 路徑 rc=0；--l2c1 注入篡改（L2-C1→MET）必紅 rc=1；4 負控（pass 數／McNemar p／取消勾選／刪裁決註記）全紅。
- **判準（實測核對全過）：** REPORT.json cells_scored=67／infra=41／A 17/34 rate=0.5／C 18/33 rate=0.5455／A_vs_C(33,3,4,p=1.0)／C 臂 vacant_sha cf62d258…；envelope C 臂 33 PASS/0 FAIL、home_bytes [14856,74081,393813]；packet 標題；l2c1 L2-C1 NOT_MET（若在位則核對）；BACKLOG 第 56 行（sha 5f27f759… 釘住、改動即紅）。
- **坑：** 首版 166 行超票 ≤140 上限→精簡至 140 行；BACKLOG 行 sha 以無尾換行行（e006/e008 口徑）；packet/l2c1 在簿記目錄（~/dev/ops）非 repo→量具以 REPO.parent/ops 為 fallback 候選。
- **紅線：** 無 push（loop 自推 auto/qwen27b）、main 未動、無 reset/rebase、.github/workflows/ 只讀、hidden/scorer 未讀、未跑 full pytest；
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。

## 未完（≤3、交下輪）
1. 三新 HEAD CI 一次讀取（qwen acd51b0e4／argon 8102536b5／worker 5e36fd5d2；紅→log 根因不猜、不 poll）——本輪未做（票面範圍僅 e009 量具，非疏漏、如實記）。
2. e015 殘留（獨立項、非本票）：/srv/vlab/runs/e015_h_multi_review/VERDICT.json 現盤損傷（line 1780）候修復。
3. 候人類裁決：L008 樣本量/預算（未發射、0 呼叫）；e013 票（bounced/）候規劃者修驗收 grep；G 系列（vq-kax）；0820-1（open/）候 worker 重驗項1→升三分支。

## 下輪入口（≤3）
- CI 一次讀取（ci_status.py 三分支、不 poll）。
- g3_2 前置已綠（precheck 6/6 task、manifest 凍結、ref 可達、無殘留）→ 可發射 fire_summary（round 900 先例 447s/32 格）——候審查者訊號、不自發。
- 守衛：NOW.md ≤3KB、ops/loop/NOW.md 與 root byte-identical（cp 鏡像）、ops/STATE.md＝canonical Current State 前綴鏡像（bk_state 契約）、紅線契約行逐字保留（now_redline 機器解析）、bd ready 空。
