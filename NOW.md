# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1589、2026-11-13、0 model calls）
- 本輪（票 P20261113_1810-1 done）：D4 `load_frozen_specs` 支援 manifest dict 入參（`_manifest_path` 點名來源檔、僅報錯文案；無 specs 鍵照舊 fail-closed）；TDD 先紅（改前 Path(dict)→TypeError）後綠；票→done/。
- 驗收（全綠、本輪新跑）：票面 1 passed（RC0）；frozen_specs 6 passed；g4_preregistration 6 passed；frozen_anchors 5 passed（4 凍結檔未動）；g4gate --dry-run RC0；git diff 2 檔。

## 紅線
- 凍結：repair.py／run_eval.py 仍凍結；extract.py／checks.py 受控解凍只加法；g25 filing（6 sha256）未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；本輪 0 發射。
- CI：輪首 auto/qwen27b 還沒跑完；argon 8 紅／worker 11 紅＝他枝新 WIP、既有、已上報、不代修。

## 下一步
1. 下一輪 doing/ 取票照做；open/ 現 3 張（1810-2 g4gate dry-run 接 loader／1810-3 g3 CLI 護欄／1810-4 D1 replay 護欄）≥3 達標。
2. 不發 closure-check／結案量具類工單（11-13 §1 禁止）；G4 發射前需人類點頭。
3. 成效門現況：D1 K1＝66/76 確定性（≥30 達標）＋負控制 false_pass=0；G4 預註冊已備、待人類簽核。
