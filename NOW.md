# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結）、G2 已完（凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1402、2026-11-10）

r1402＝CI 紅燈收口（工單 P20261110_1904-1，vq-el4.87 開→關，vq-el4 87/87 全閉）。r1401 完成三分支碼同步（ci_tip 對＋GUARD_CONTENT_PIN 10→12 檔；qwen27b@2ad1713cb／worker@2bbbc5cec／argon@355c50d01）；r1402 完成剩餘驗收（本輪全數新跑）：
- in-scope diff 0×2；repair.py 直開核實：2795 行、blob 5147f8c3…、sha256 c860fc23…，0 更正；
- 測試：ci_tip 10 passed、freeze_check 27 passed（基線 26＋1 r1401 負控、0 弱化）；ci_tip_check.py 輸出正常（rc=0、三分支 tips NO_COVERAGE fail-closed、CI 在跑）；
- freeze_check 12/12 OK FROZEN_STATE_OK rc=0（diff 0×2、filing 3/3＋3/3、queue 空含隱藏、g3gate NOT_FIRED、bk 同步、wt 3/3、now_redline OK）；ves 7/7 OK EFFECTS_SUMMARY_OK rc=0；
- bd：vq-el4.87 已結；全庫唯一 open＝vq-1zf（G3、待人類 --fire、不代發、不入 queue）；/srv/vlab/queue 空（含隱藏）。
- 未驗證：現三分支 tips per-sha CI 輪首未跑完→UNKNOWN（非紅燈；一次讀取、不 poll）。

## 下一步

1. 下輪開頭一次讀取三分支現 tip per-sha CI json（綠＝收口終證、紅＝查因；不 poll）。
2. 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決（CI 現為唯一全量綠燈通道）。

## 紅線

- 不讀 /srv/eval/hidden/ 與 scorer.py；G3 不入 /srv/vlab/queue；G3 只待人類 --fire 後發射。
- main 不碰；無 push（loop 自推）；.github/workflows/ 零改動；無 reset/rebase。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改。
- 0 模型呼叫（glm 未用）；不跑 full pytest（只 CI 一次讀取）；不 sleep poll；不以改文湊進展；數字一律實跑／重算驗證。
- 簿記：STATE.md（canonical、Current State 首行最新單行條目、先 append 條目）＋鏡像 ops/STATE.md（5 行鏡像）＋NOW.md（repo root）＋鏡像 ops/loop/NOW.md（byte-identical）；每輪簿記後同步 worker／argon worktree。
