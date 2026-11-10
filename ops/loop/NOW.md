# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結）、G2 已完（凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1406、2026-11-10）

r1406＝r1405 rc=124 超時殘留收口＋vq-el4.90 結案（全庫唯一 open 仍 vq-1zf）。
- 紅燈根因（輪首 freeze_check 實跑、2/12 BROKEN）：r1405 最終簿記（ba5fe0a68 auto-commit）僅落 qwen27b，worker/argon 停在 5a74f7534／a03ec7927（4 簿記檔身份缺失）→diff_worker／diff_argon「no sync counterpart」（非產品 bug；in-scope 碼 0 檔）。
- 修（r1406 sync commits）：兩 worktree `git checkout auto/qwen27b -- STATE.md NOW.md ops/STATE.md ops/loop/NOW.md`＋commit（worker@6f4b5dfa4／argon@98528f91c）→diff OK→FROZEN_STATE_OK rc=0。
- vq-el4.90（is_green 假綠燈洞、r1405 實質完成）：本地驗收齊、唯一未驗證＝per-sha CI 測量（環境、每輪 ci_tip_check 追到 COVERED；r1402／r1404 先例亦帶 CI 未跑結案）→本輪 bd close（r1405 被超時切斷未執行）。
- 驗收（本輪全數新跑）：守衛 8 檔 109 passed in 5.03s；freeze_check 12/12 FROZEN_STATE_OK rc=0（含 now_redline）；ves 7/7 EFFECTS_SUMMARY_OK rc=0（policy30 13w0r g7/l6、once20 11w0r g7/l4、reference MATCH）；g3gate 22 passed NOT_FIRED；in-scope diff 0×2；queue 空（含隱藏）；live ci_tip_check→NO_COVERAGE ×3→CI_TIP_BROKEN rc=1（r1405 碼未被綠 CI 測量、fail-closed、在跑≠已綠、state.json 一次讀取不 poll）。
- 簿記：canonical＝STATE.md＋NOW.md；鏡像＝ops/STATE.md＋ops/loop/NOW.md（byte-identical）；三分支同步（qwen27b@ba5fe0a68／worker@6f4b5dfa4／argon@98528f91c）、in-scope diff 0×2。

## 下一步

1. 下輪開頭重跑 `python3 ops/reqloop/ci_tip_check.py`（一次讀取、不 poll）：現 3 tips（ba5fe0a68／6f4b5dfa4／98528f91c）若被綠祖先覆蓋→COVERED＝r1405 碼 CI 收口（rc=0）；未覆蓋→NO_COVERAGE 非退步（待 CI）、當時再驗。
2. 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決（GitHub auto-ci.yml disabled_manually、本地 vacant-ci 為實效通道）。

## 紅線

- 不讀 /srv/eval/hidden/ 與 scorer.py；G3 不入 /srv/vlab/queue；G3 只待人類 --fire 後發射。
- main 不碰；無 push（loop 自推）；.github/workflows/ 零改動；無 reset/rebase。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改。
- 0 模型呼叫（glm 未用）；不跑 full pytest；不 sleep poll；不以改文湊進展；數字一律實跑／重算驗證。
- 簿記：STATE.md（canonical、Current State 首行最新單行條目）＋鏡像 ops/STATE.md（byte 前綴）＋NOW.md＋鏡像 ops/loop/NOW.md（byte-identical）；每輪簿記後同步 worker／argon worktree（in-scope diff 0×2）。
