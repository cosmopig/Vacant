# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1581、2026-11-13、0 model calls）
- 本輪（票 P20261113_1358-2 done）：D1 重播 --missing-report——stdout 尾段逐條 `CLAIM_MISSING: <task>/<claim>: <欄位名> <原因碼>`（3 條：dab_517 values/missing_param；dab_725 R1＋R6 verifier/raw_fields_not_saved；只點名欄位、不印值）；--json totals 加 missing_detail；K0/K1 數字不變（14→66）。實作＋4 測試於 r1579 超時輪 WIP 入樹（f2c7beb95）；本輪＝全數驗收＋簿記收口。
- 簿記修復（票驗收必需）：ops/STATE.md 鏡像重生成（canonical 前綴至 Current State 最新條目行；輪首 633185B 鏡像截斷於第 509 行行中）；NOW.md 紅線契約行恢復（值自磁碟重算）＋ops/loop/NOW.md byte-identical。
- 驗收（全綠）：--missing-report RC0 逐條點名；--json deterministic=66＋missing_detail 3 條；pytest tests/test_replay_claims.py 16 passed；freeze_check VERDICT: FROZEN_STATE_OK（輪首 BROKEN：bk_state/bk_now/now_redline 3 項全修）；anchors 5 passed；票尾 3 行→mv done/。

## 紅線
- 凍結／受控解凍：repair.py 2795 行／blob 5147f8c3…、run_eval.py 1298 行／blob b6d2f37f…（仍凍結）；extract.py 1295 行／blob b502741b…、checks.py 2907 行／blob d401a8ae…（受控解凍、只加法、預設＝舊行為）；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；本輪 0 發射。
- CI：輪首 auto/qwen27b 15 紅＝freeze_check/now_redline 系；本輪簿記修復後本分支應轉綠、待 CI 證實；argon 2 紅／worker 11 紅＝既有、已上報、不代修。

## 下一步
1. open/ 3 張（1358-3 D4 frozen spec loader、1507-1、1507-2）→doing/ 取票照做（每張動產品碼或 D1 重播器）。
2. 不做 closure-check／結案量具／sync 類（11-13 §1 禁止）；G4 發射需人類簽核。
3. 達成效門（≥30/76 確定性＋負控制 0 假 PASS）前不發新真模型實驗。
