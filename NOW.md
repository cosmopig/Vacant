# NOW.md — 現況（每輪覆寫、≤3KB）

## 狀態（2026-11-12 r1515；票 P20261112_1528-2 done：e001 120 格基準結案機械複核量具＋單測，驗收 VERDICT: E001_CLOSURE_OK＋3 passed RC=0；0 model calls、0 行產品碼）
- **產物：** ops/audits/e001_closure_check.py（140 行、純 stdlib、CI-home 兼容、對齊 e008 架構）＋tests/test_e001_closure_check.py（54 行、3 測試）。commit 26c2b14af；票已移 done/。
- **驗收（本輪新跑）：** `python3 ops/audits/e001_closure_check.py --selftest && pytest tests/test_e001_closure_check.py`→VERDICT: E001_CLOSURE_OK、RC=0；「3 passed in 0.14s」；非 selftest 路徑 rc=0；4 負控（pass 數／McNemar p／封包標題／審計報告關聯字）全紅。
- **判準（實測核對全過）：** REPORT.json cells_scored=120／infra=14／A 28/60 rate=0.4667／C 34/60 rate=0.5667／C 臂 vacant_sha dd2c6746…／A_vs_C(60,2,8,p=0.1094)；envelope C 臂 60 PASS/0 FAIL、home_bytes [27611,333481,1146648]；packet 標題；審計報告 Total Cells Scored 120＋McNemar p=0.1094（實位 ~/dev/ops/audits/）；BACKLOG 第 16 行（sha b71e9f07… 釘住、改動即紅）。
- **坑：** 審計報告不在 repo、只在簿記目錄→量具 repo 路徑優先、否則 REPO.parent/ops 候選（e009 口徑）；首版 151 行超票 ≤140 上限→精簡至 140 行；審計報告 `**Total Cells Scored**` markdown 粗體→剝 * 後匹配票面字串。
- **紅線：** 無 push（loop 自推 auto/qwen27b）、main 未動、無 reset/rebase、.github/workflows/ 只讀、hidden/scorer 未讀、未跑 full pytest；
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。

## 未完（≤3、交下輪）
1. 三新 HEAD CI 一次讀取（qwen 26c2b14af〔auto 收簿記〕／argon 8102536b5／worker 5e36fd5d2；紅→log 根因不猜、不 poll）。
2. e015 殘留（獨立項、非本票）：/srv/vlab/runs/e015_h_multi_review/VERDICT.json 現盤損傷（line 1780）候修復。
3. 候人類裁決：L008 樣本量/預算（未發射、0 呼叫）；e013 票（bounced/）候規劃者修驗收 grep；G 系列（vq-kax）；0820-1（open/）候 worker 重驗項1→升三分支。

## 下輪入口（≤3）
- CI 一次讀取（ci_status.py 三分支、不 poll）。
- bd list --parent vq-el4 --all 照順序下一票。
- 守衛：NOW.md ≤3KB、ops/loop/NOW.md 與 root byte-identical（cp 鏡像）、ops/STATE.md＝canonical Current State 前綴鏡像（bk_state 契約）、紅線契約行逐字保留（now_redline 機器解析）、bd ready 空。
