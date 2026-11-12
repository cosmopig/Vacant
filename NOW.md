# NOW.md — 現況（每輪覆寫、≤3KB）

## 狀態（2026-11-12 r1518；票 P20261112_1728-1 done：CI 紅燈修復 e001 審計報告路徑候選，驗收 CI 模擬 3 passed＋VERDICT: E001_CLOSURE_OK RC=0；0 model calls）
- **產物：** ops/audits/e001_closure_check.py::audit_default() 候選 3 路徑（repo→REPO.parent/ops→/home/user1/dev/ops/audits/e001_pi_AC_baseline.md，取首個存在）；140 行不增。commit b7cc57148；票移 done/。
- **驗收（本輪新跑）：** 票面 CI 模擬指令（copytree ops/tests 至 /var/tmp＋pytest）改前重現 2 failed, 1 passed（missing file 審計報告: /var/tmp/ops/audits/…）；改後同指令 3 passed in 0.14s＋assert 成功；`python3 ops/audits/e001_closure_check.py --selftest`→VERDICT: E001_CLOSURE_OK、RC=0；本機 repo pytest 該檔 3 passed。
- **範圍：** 只修 e001（票面）；e009 與 reqloop_freeze_check 兩組紅燈不屬本票、待對應工單。
- **紅線：** 無 push（loop 自推 auto/qwen27b）、main 未動、無 reset/rebase、.github/workflows/ 只讀、hidden/scorer 未讀、未跑 full pytest；
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。

## 未完（≤3、交下輪）
1. 四 HEAD CI 一次讀取（qwen b7cc57148〔auto 收簿記〕／argon 8102536b5／worker 5e36fd5d2；紅→log 根因不猜、不 poll）。
2. e015 殘留（獨立項、非本票）：/srv/vlab/runs/e015_h_multi_review/VERDICT.json 現盤損傷（line 1780）候修復。
3. 候人類裁決：L008 樣本量/預算（未發射、0 呼叫）；e013 票（bounced/）候規劃者修驗收 grep；G 系列（vq-kax）；0820-1（open/）候 worker 重驗項1→升三分支。

## 下輪入口（≤3）
- CI 一次讀取（ci_status.py 三分支、不 poll）。
- bd list --parent vq-el4 --all 照順序下一票。
- 守衛：NOW.md ≤3KB、ops/loop/NOW.md 為 symlink（同一檔案）、ops/STATE.md→repo 根 STATE.md symlink、紅線契約行逐字保留（now_redline 機器解析）、bd ready 空。
