# NOW.md — Vacant 現況（≤3KB；本檔每輪覆寫、歷史見 STATE.md）

## 現況（r1540、2026-11-13、0 model calls）
- 本輪實質＝票 P20261113_0132-1 done：smoke 初始冒煙（smoke 2 格 A/C 配對、pi 首發）完賽結案機械複核量具＋單測。
- 新增：ops/audits/smoke_closure_check.py 130 行（純 stdlib、CI-home 兼容、對齊 e002_smoke/e005 架構）——REPORT.json（cells_scored=2/infra=0、A 1/1 rate=1.0 calls=9.0 tok=148158、C 1/1 rate=1.0 calls=8.0 tok=128730、vacant_sha cf62d258…、pairs=1/A_only=0/C_only=0/mcnemar_p=1.0）＋envelope_compliance（C 臂 1 PASS/0 FAIL、home_bytes [35405,35405,35405]、256MiB 封頂）＋delivery.json（mode=agent_exit、agent_exit.rc=0、requests_seen=12）＋cell.json（A/C 臂 agent=pi、C 臂 agent_model=qwen3.8-27b）；--selftest 正控制＋4 負控制（cells_scored／C 臂 vacant_sha／envelope C 臂 NO_EVIDENCE 數／delivery mode 全必紅）；缺檔乾淨退出。
- 新增：tests/test_smoke_closure_check.py 53 行、3 測試（空 HOME selftest／正＋4 負／缺檔乾淨紅）。
- 驗收（本輪新跑）：`--selftest`→VERDICT: SMOKE_CLOSURE_OK RC=0；無 -q 複跑「3 passed in 0.12s」；非 selftest 路徑 RC=0；commit 55f703f77（2 產物檔）。
- 未驗證：CI 完成裁決（輪首三分支皆還沒跑完、延下輪頭一次讀不 poll）；envelope 數值未對 cell.json 逐格獨立重算（採信 envelope_compliance.py 重算、同 e003/e005 口徑）；量具只鎖 smoke 結案文字與數值、非機制效力證明。

## 紅線
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- NOW.md ≤3KB；ops/loop/NOW.md cp 鏡像 byte-identical。
- 不以文書改動充實進度：本輪實質＝新增量具＋測試 2 檔＋票結案＋簿記、全可機械複核。

## 下一步（2026-11-13 人類定案改寫，凌駕舊的下一步）
1. 照 tickets/qwen/open/ 的 D1→D2→D3→D4 做（需求→可檢查條件；成效門 2/76→≥30/76、0 錯判 PASS）。
2. 不再做任何 closure-check／結案量具／同步類工作（R20261113_0041-2 作廢）。
3. extract.py／checks.py 受控解凍：只加法、新參數預設＝舊行為、run_eval.py --all 三門數字與 g25 filing 相同。
