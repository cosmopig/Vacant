# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1573、2026-11-13、0 model calls）
- 本輪（票 P20261113_1307-1 done）：g3.py::PiChannel 支援 G4 purpose（(?:G3|G4））＋tasks_dir 自訂任務根（預設 None＝舊行為）；_ArmChannelRouter 分流正則同寬 G4；1 新測（TDD 先紅後綠）→mv done/。
- 驗收（全綠）：-k test_pi_channel_supports_g4_purpose→1 passed（改前 1 failed）；frozen_spec 9 passed；回歸 53 passed；g4gate --dry-run RC=0（12 cells ready）／--fire RC=2；human_signoff 仍 null。
- 效果門（不變）：replay_claims.py --gate → deterministic=66/76 ≥ 30，false_pass=0，VERDICT: PASS。

## 紅線
- 凍結：repair.py／extract.py／checks.py／run_eval.py 未改（frozen anchors 綠）；g25 filing；g3 歷史產物未改。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；run_g4 已接線、PiChannel 已支援 G4 通道呼叫，本輪 0 發射。
- CI：argon 2 紅／worker 11 紅＝既有 freeze_check/now_redline 系（已上報規劃者、不代修；11-13 §1 禁開 sync/mirror 票）。

## 下一步
1. open/ 2 張（P20261113_1307-2 g3 CLI G4 manifest 分派、P20261113_1307-3 g4gate 任務工作區 hash 守衛）→doing/ 取票照做。
2. open/<3 張→規劃者依 11-13 §5 補票（每張動產品碼或 D1 重播器）。
3. 不做 closure-check／closing-gauge／sync 類（11-13 §1 禁止）；G4 發射需人類簽核。
（MEMORY 上限 6 KB、NOW 上限 3 KB；超過的部分沒有附上，請先把它縮短）
