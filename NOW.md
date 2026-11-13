# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1562、2026-11-13、0 model calls）
- 本輪（票 P20261113_0948-3 done、commit 19c97a5db）：D1 重播器 `ops/reqloop/extract/replay_claims.py` 支援 `--json`——K1（trusted）統計 `{"totals","by_task","deterministic"}` 以 json（indent=2、ensure_ascii=False）印 stdout、RC 0、不寫 OUT、0 model calls；`summarize()` 內建 `by_task`（每題 total/deterministic/unverified/missing_raw）；tests/test_replay_claims.py 加 `test_replay_claims_json_flag`（10 passed）。
- 驗收：`python3 ops/reqloop/extract/replay_claims.py --json`→RC=0、`json.loads` 通過、`"deterministic": 66`（int）、`by_task` 8 題合計 76（dab_725 total=18/det=14）；回歸 69 passed；git diff 僅 2 檔＋30/-1。
- 成效門（不變）：`python3 ops/reqloop/extract/replay_claims.py --gate`→`GATE_CHECK: deterministic=66/76 >= 30 false_pass=0 VERDICT: PASS`。
- 待驗：open/＋doing/ 皆空→規劃者依 11-13 §5 補票（每張動產品碼或 D1 重播器，<3 張要補）。

## 紅線
- 凍結／受控解凍：repair.py 2795 行／blob 5147f8c3…、extract.py 1295 行／blob b502741b…、checks.py 2907 行／blob d401a8ae…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2/g3_3 歷史未動；g26 歷史報告（g26_claim_replay.json）未改。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；g4gate 核准後發射管線未接線、另一步授權。
- 不以文書改動充實進度：本輪實質＝D1 重播器 --json＋by_task（2 檔＋30/-1、1 新測試），全可機械複核。

## 下一步
1. open/＋doing/ 空→規劃者依 11-13 §5 補票（每張動產品碼 vacant_network/reqloop/ 或 D1 重播器）。
2. 輪頭一次讀 CI 三分支（紅→讀 log 根因不猜；freeze_check 既有紅→上報規劃者、不代修）。
3. 不做 closure-check／結案量具／同步類（11-13 §1）；G4 發射須人類簽核（human_signoff=null）。
