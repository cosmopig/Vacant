# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1588、2026-11-13、0 model calls）
- 本輪（票 P20261113_1708-2 done）：D1 重播 dab_517 missing_param:values 根因點名＋負控制。replay_reason 對 missing_param:* 明確回 (None, reason)（保留根因碼、I-4 未測量不是通過、絕不翻 deterministic）；新增 0 假 PASS 負控制測試；TDD 先紅後綠。
- 驗收（全綠、本輪新跑）：票面 1 passed（RC0）；test_replay_claims 18 passed；--missing-report 含 `CLAIM_MISSING: dab_517/req_data_unchanged: values missing_param`；selftest PASS；gate 66/76 false_pass=0 PASS；anchors+frozen_specs 10 passed；git diff 2 檔（產品碼 9 行）。

## 紅線
- 凍結：repair.py 2795 行／blob 5147f8c3…、run_eval.py 1298 行／blob b6d2f37f…（仍凍結）；extract.py b502741b…、checks.py d401a8ae…（受控解凍、只加法、預設＝舊行為）；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；本輪 0 發射；1507-2／1708-1 接線已完成（g4gate、run_g4 統一核驗口）。
- CI：輪首 qwen 還沒跑完；argon 8 紅／worker 11 紅＝他枝新 WIP、既有、已上報、不代修。

## 下一步
1. open/ 0 張＋doing/ 空＜3→規劃者依 11-13 §5 補票（每張動產品碼 vacant_network/reqloop/ 或 D1 重播器；每次最多 4 張）；下一輪 doing/ 取票照做。
2. 不發 closure-check／結案量具類工單（11-13 §1 禁止）；G4 發射前需人類點頭。
3. 成效門現況：D1 K1＝66/76 確定性（≥30 達標）＋負控制 false_pass=0；達標後 G4 預註冊已備（4 題凍結規格）、待人類簽核。
