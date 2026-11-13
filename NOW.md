# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1594、2026-11-13、0 model calls）
- 本輪（票 P20261113_1900-1 done）：D1 重播 `--unverified-report` 點名全部 7 條非確定性 claim
  （dab_725 R4/R7、dab_517 req_write_answer_txt／req_do_not_modify_data＝model_declared_unverified；
  dab_587 req-3/4/5＝unknown_verifier:missing）——原因碼逐條、不印欄位值、唯讀、0 model calls；
  `--json` totals 旁純加法新增 `named_non_deterministic`（7 條、既有欄位一字未改）；
  `--missing-report`／`--gate` 輸出逐字不變（deterministic=66/76、false_pass=0、VERDICT: PASS）。
- 驗收（全綠、本輪新跑）：pytest -k unverified_report 4 passed（RC0）；--unverified-report 7 行點名 RC0；
  --gate VERDICT: PASS；test_replay_claims 23 passed；anchors＋frozen_specs 11 passed；
  4 凍結檔未動；G4 簽核仍 null、0 發射。

## 紅線
- 凍結／受控解凍：repair.py 2795 行／blob 5147f8c3…、run_eval.py 1298 行／blob b6d2f37f… 仍凍結；
  extract.py 1295 行／blob b502741b…、checks.py 2907 行／blob d401a8ae… 受控解凍只加法；g25 filing（6 sha256）未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；本輪 0 發射。
- CI：輪首 auto/qwen27b 還沒跑完；argon 8 紅／worker 11 紅＝他枝 WIP、既有、已上報、不代修。

## 下一步
1. **open/ 2 張（1900-2／1900-3）＜3**→規劃者依 11-13 §5 補票（每張動產品碼 vacant_network/reqloop/ 或 D1 重播器；不發 closure-check／結案量具類）。
2. 下一輪 doing/ 取票照做。
3. 成效門現況：D1 K1＝66/76 確定性（≥30 達標）＋負控制 false_pass=0；unverified 7 條已全部逐條點名（本輪新增）；G4 預註冊已備、待人類簽核。
