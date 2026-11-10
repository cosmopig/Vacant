# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結）、G2 已完（凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1404、2026-11-10）

r1404＝CI 三分支收口終證＋全口徑守衛複驗（NOW r1403 下一步 #1 達成；vq-el4.89 開→關；全庫唯一 open＝vq-1zf）。
- 本輪改善之命令輸出＝`python3 ops/reqloop/ci_tip_check.py` → **VERDICT: CI_TIP_OK rc=0**（r1403 UNKNOWN→收口，本輪新跑）：qwen27b@06963d19d COVERED（綠祖先 2ad1713cb per-sha 5145/0/74 磁碟直讀＋diff 純 4 簿記檔）；worker@8a695039a PEER_COVERED（root tree 與 qwen27b tip 恆等；CI 在跑≠已綠）；argon@77b7de8c4 COVERED（綠祖先 6faca25c＋diff 純 4 簿記檔）。
- 口徑分報：現 3 tips per-sha CI json 無→per-sha 層 UNKNOWN（覆蓋判定≠per-sha 綠，兩口徑皆留案）。
- 全口徑（本輪全數新跑）：守衛 8 檔 108 passed；freeze_check 12/12 FROZEN_STATE_OK rc=0；ves 7/7 EFFECTS_SUMMARY_OK rc=0；g3gate 22 passed NOT_FIRED；queue 空（含隱藏）；in-scope diff 0×2。

## 下一步

1. 下輪開頭重跑 ci_tip_check.py（一次讀取、不 poll）：維持 CI_TIP_OK＝收口成立；若 tips 前移→UNKNOWN／NO_COVERAGE 非退步、當時再驗。
2. 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決（GitHub auto-ci.yml disabled_manually、本地 vacant-ci 為實效通道）。

## 紅線

- 不讀 /srv/eval/hidden/ 與 scorer.py；G3 不入 /srv/vlab/queue；G3 只待人類 --fire 後發射。
- main 不碰；無 push（loop 自推）；.github/workflows/ 零改動；無 reset/rebase。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改。
- 0 模型呼叫（glm 未用）；不跑 full pytest；不 sleep poll；不以改文湊進展；數字一律實跑／重算驗證。
- 簿記：STATE.md（canonical、Current State 首行最新單行條目）＋鏡像 ops/STATE.md（byte 前綴）＋NOW.md＋鏡像 ops/loop/NOW.md（byte-identical）；每輪簿記後同步 worker／argon worktree（in-scope diff 0×2）。
