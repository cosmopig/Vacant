# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1592、2026-11-13、0 model calls）
- 本輪（票 P20261113_1810-4 done）：D1 replay `verify_frozen_specs` 接入 manifest spec_sha256
  密碼學綁定核驗（`load_frozen_specs` 統一核驗口）——篡改/損毀 → fail-closed RC1、點名
  `FROZEN_SPECS FAIL: manifest integrity`；TDD 先紅後綠＋新增負控制測試。
- 驗收（全綠、本輪新跑）：票面 1 passed（RC0）；test_replay_claims 19 passed；
  frozen_specs＋g4_prereg＋anchors＋g3_frozen 30 passed；`--verify-specs` 仍 PASS（22 checkable、0 假 PASS）；
  `--gate` 仍 66/76 false_pass=0；4 凍結檔未動；G4 簽核仍 null、0 發射。

## 紅線
- 凍結：repair.py／run_eval.py 仍凍結；extract.py／checks.py 受控解凍只加法；g25 filing（6 sha256）未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；本輪 0 發射。
- CI：輪首 auto/qwen27b 還沒跑完；argon 8 紅／worker 11 紅＝他枝 WIP、既有、已上報、不代修。

## 下一步
1. **open/ 0 張＋doing/ 空＜3**→規劃者依 11-13 §5 補票（每張動產品碼 vacant_network/reqloop/ 或 D1 重播器；不發 closure-check/結案量具類）。
2. 下一輪 doing/ 取票照做。
3. 成效門現況：D1 K1＝66/76 確定性（≥30 達標）＋負控制 false_pass=0；G4 預註冊已備、待人類簽核。
