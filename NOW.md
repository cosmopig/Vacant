# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1585、2026-11-13、0 model calls）
- 本輪（票 P20261113_1507-1 done）：D1 重播 dab_587 三條 unknown_verifier:missing 根因點名＋0 假 PASS 負控制。judge_claim verifier 空/None→missing（對齊 extract.py:806）；replay_reason 明確分支維持 unverified（I-4）；新增負控制測試。
- 驗收（全綠、本輪新跑）：票面 1 passed；test_replay_claims 17 passed；--json deterministic=66（≥30 門）、dab_587 unverified=3、點名 unknown_verifier:missing=3；--gate false_pass=0 PASS；selftest PASS；anchors 5 passed。

## 紅線
- 凍結／受控解凍：repair.py 2795 行／blob 5147f8c3…、run_eval.py 1298 行／blob b6d2f37f…（仍凍結）；extract.py 1295 行／blob b502741b…、checks.py 2907 行／blob d401a8ae…（受控解凍、只加法、預設＝舊行為）；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；本輪 0 發射；run_g4/g4gate 接線未做（1507-2/1708-1 另步授權）。
- CI：輪首 qwen 還沒跑完；argon 2 紅／worker 11 紅＝既有、已上報、不代修。

## 下一步
1. open/ 3 張（1507-2 g4gate 接線、1708-1 g3.run_g4 接線、1708-2 D1 missing-param 守衛）→doing/ 取票照做。
2. G4 發射需人類簽核；不做 closure-check／結案量具類（11-13 §1 禁止）。
3. 達成效門（≥30/76 確定性＋負控制 0 假 PASS）前不發新真模型實驗。
