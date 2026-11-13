# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1575、2026-11-13、0 model calls）
- 本輪（票 P20261113_1307-3 done）：g4gate.build_g4_execution_plan 納入任務工作區檔案雜湊守衛——逐題 RequirementSet.load＋verify_task_hash(ws)，goal.md/contract.md sha256 與凍結規格綁定值不符→ValueError「雜湊不符（…；fail-closed）」；輸入檔漂移離線組裝時即攔截（不必等真發射 load_frozen_spec）；TDD 先紅後綠（goal.md 改一個字元→雜湊不符負控制；缺檔負控制改真實檔基底）→mv done/。
- 驗收（全綠）：票面 1 passed（含篡改負控制）＋g4gate --plan 12 格 RC 0；32 passed（g4_prereg/g3_frozen_spec/anchors/replay_claims）；4 題真實工作區 hash 全吻合；human_signoff 仍 null。
- G4 接線現況：manifest 校驗→簽核門→dry-run（12 格）→plan（hash 守衛）→fire 全鏈 0 model calls；唯缺人類簽核（human_signoff=null）→fire RC 2 fail-closed。

## 紅線
- 凍結：repair.py／extract.py／checks.py／run_eval.py 未改（frozen anchors 綠）；g25 filing；g3 歷史產物未改。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；本輪 0 發射。
- CI：argon 2 紅／worker 11 紅＝既有 freeze_check/now_redline 系（已上報、不代修；11-13 §1 禁開 sync/mirror 票）。

## 下一步
1. open/ 空（<3 張）→規劃者依 11-13 §5 補票（每張動產品碼 vacant_network/reqloop/ 或 D1 重播器）。
2. 不做 closure-check／結案量具／sync 類（11-13 §1 禁止）；G4 發射需人類簽核。
3. 達成效門（≥30/76 確定性＋負控制 0 假 PASS）前不發新真模型實驗。
（MEMORY 上限 6 KB、NOW 上限 3 KB；超過的部分沒有附上，請先把它縮短）
