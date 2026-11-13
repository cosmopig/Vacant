# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1590、2026-11-13、0 model calls）
- 本輪（票 P20261113_1810-2 done）：D4 g4gate 全面接入 `specs.load_frozen_specs` 統一核驗口——
  `g4_dry_run` 開頭全量 4 題 spec_sha256 密碼學校驗（篡改/缺檔→SpecIntegrityError fail-closed），
  移除重複手動比對；`build_g4_execution_plan` 直接 `load_frozen_specs(manifest)`、移除 `_manifest_path` workaround；
  CLI dry-run 例外列加 SpecIntegrityError（篡改 manifest 乾淨 RC1）。
- 驗收（全綠、本輪新跑）：票面 2 passed（RC0）；g4_prereg＋frozen_specs＋anchors＋g3_frozen 29 passed；
  g3gate＋g3_frozen 42 passed；freeze_g4_specs 5 passed；CLI dry-run RC0／plan RC0／fire RC2（簽核仍 null）／
  篡改 manifest RC1 點名 dab_587；4 凍結檔未動。

## 紅線
- 凍結：repair.py／run_eval.py 仍凍結；extract.py／checks.py 受控解凍只加法；g25 filing（6 sha256）未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；本輪 0 發射。
- CI：輪首 auto/qwen27b 還沒跑完；argon 8 紅／worker 11 紅＝他枝新 WIP、既有、已上報、不代修。

## 下一步
1. 下一輪 doing/ 取票照做；open/ 現 2 張（1810-3 g3 CLI 護欄／1810-4 D1 replay 護欄）<3→規劃者依 11-13 §5 補票。
2. 不發 closure-check／結案量具類工單（11-13 §1 禁止）；G4 發射前需人類點頭。
3. 成效門現況：D1 K1＝66/76 確定性（≥30 達標）＋負控制 false_pass=0；G4 預註冊已備、待人類簽核。
