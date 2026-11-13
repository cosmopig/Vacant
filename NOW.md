# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1591、2026-11-13、0 model calls）
- 本輪（票 P20261113_1810-3 done）：D4 g3 CLI G4 `--dry-run` 篡改 spec_sha256 fail-closed pin 測試。
  票步驟1（捕獲＋`G4 DRY-RUN FAIL`＋RC1）現樹已存在（1307-2 之 except Exception ⊇ 票點名三型；收窄會弱化 fail-closed）
  → 本票落地為 pin 測試 `test_g3_cli_g4_dry_run_tampered_spec_fails_closed_exit_1`（RC1、點名題號、無 Traceback）。
- 驗收（全綠、本輪新跑）：票面 1 passed（RC0）；g3_frozen 12＋anchors 5＋g4_prereg 6＋freeze 5＋g3gate/frozen_specs 37＝66 passed；
  git diff 僅測試 1 檔＋17；4 凍結檔未動；G4 簽核仍 null、0 發射。

## 紅線
- 凍結：repair.py／run_eval.py 仍凍結；extract.py／checks.py 受控解凍只加法；g25 filing（6 sha256）未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；本輪 0 發射。
- CI：輪首 auto/qwen27b 還沒跑完；argon 8 紅／worker 11 紅＝他枝 WIP、既有、已上報、不代修。

## 下一步
1. 下一輪 doing/ 取票照做；open/ 現 1 張（1810-4 D1 replay manifest pin 護欄）<3→規劃者依 11-13 §5 補票。
2. 不發 closure-check／結案量具類工單（11-13 §1 禁止）；G4 發射前需人類點頭。
3. 成效門現況：D1 K1＝66/76 確定性（≥30 達標）＋負控制 false_pass=0；G4 預註冊已備、待人類簽核。
