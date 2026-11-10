# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結）、G2 已完（凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1409、2026-11-10）

r1409＝r1408（rc=124）超時殘留收口（vq-1zf.7 開→關）：輪首守衛 112+2failed／freeze_check 10/12（diff_worker/diff_argon BROKEN＝兩 worktree 未同步 r1408 g3gate 3 檔）＋ci_tip_check CI_TIP_BROKEN（r1408 碼正被 CI 測量、在跑≠已綠）→獨立重驗 r1408（pin 2/2、g3gate 27 passed、live manifest 於上限仍 PLAN OK）→3 檔同步兩 worktree（worker@3cf8b580d／argon@0fe6b3cb7）→全綠：
- 本輪改善之命令輸出：freeze_check 10/12 FROZEN_STATE_BROKEN rc=1 → **12/12 FROZEN_STATE_OK rc=0**；守衛 8 檔 112+2failed → **114 passed**（g3gate 22→27；審查基線 108 之超集、0 排除 0 弱化）。
- ci_tip_check 仍 CI_TIP_BROKEN rc=1＝r1408 碼尚未被綠 CI 測量（fail-closed、不 poll）——進行中狀態、非缺陷。

## 下一步

1. 下輪開頭重跑 `python3 ops/reqloop/ci_tip_check.py`（一次讀取、不 poll）：qwen27b@ec538c2b 綠→COVERED＝r1408 碼 CI 收口；仍紅→查因（不預設退步）。
2. 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決（auto-ci.yml disabled_manually、本地 vacant-ci 實效通道；不翻開關、不重複診斷）。

## 紅線

- 不讀 /srv/eval/hidden/ 與 scorer.py；G3 不入 /srv/vlab/queue（維持空、含隱藏）；G3 只待人類 --fire 後發射。
- main 不碰；無 push（loop 自推）；.github/workflows/ 零改動；無 reset/rebase。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改；r1408 解凍 2 檔（g3gate.py f1bd86be…／test_reqloop_g3gate.py 86bac89d…，vq-1zf.7 記錄在案）已釘。
- 0 模型呼叫（glm 未用）；不跑 full pytest；不 sleep poll；不以改文湊進展；數字一律實跑／重算驗證。
- 簿記：canonical＝repo STATE.md＋NOW.md；鏡像 ops/STATE.md＝canonical byte 前綴（至最新條目行、行邊界結尾）＋ops/loop/NOW.md byte-identical；每輪簿記後同步 4 簿記檔入 worker／argon worktree（in-scope diff 0×2）。
