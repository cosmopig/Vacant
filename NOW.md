# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結）、G2 已完（凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1412、2026-11-10）

r1412＝收 r1411（rc=124 超時）簿記殘留（vq-el4.91 結案、非簿記輪——修真實紅燈）：
- **輪首紅燈→收口**：freeze_check 10/12 FROZEN_STATE_BROKEN rc=1（diff_worker/diff_argon＝r1411 被殺後簿記未 sync，純簿記 4 檔 0 產品碼）→ sync 後 **12/12 FROZEN_STATE_OK rc=0**；守衛 8 檔 2 failed/112 passed → **114 passed**
- **ci_tip_check（輪首、一次讀取）**：**CI_TIP_OK rc=0** 三分支全 COVERED——worker/argon 由 r1411 的 PEER_COVERED 轉直接 COVERED（綠祖先 json 已量到）
- **ves 7/7 EFFECTS_SUMMARY_OK**；**g3gate NOT_FIRED PLAN_OK rc=0**（manifest 12/300/2M 恰於上限、非放寬）；GUARD_CONTENT_PIN 12/12 MATCH（獨立重算）；queue 空（含隱藏）

## 下一步

1. 下輪開頭重跑 `python3 ops/reqloop/ci_tip_check.py`（一次讀取、不 poll）確認 COVERED 維持。
2. 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決（auto-ci.yml disabled_manually、本地 vacant-ci 實效通道；不翻開關、不重複診斷）。

## 紅線

- 不讀 /srv/eval/hidden/ 與 scorer.py；G3 不入 /srv/vlab/queue（維持空、含隱藏）；G3 只待人類 --fire 後發射。
- main 不碰；無 push（loop 自推）；.github/workflows/ 零改動；無 reset/rebase。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改；r1408 解凍 2 檔（g3gate.py f1bd86be…／test_reqloop_g3gate.py 86bac89d…，vq-1zf.7 記錄在案）已釘。
- 0 模型呼叫（glm 未用）；不跑 full pytest；不 sleep poll；不以改文湊進展；數字一律實跑／重算驗證。
- 簿記：canonical＝repo STATE.md＋NOW.md；鏡像 ops/STATE.md＝canonical byte 前綴（至最新條目行、行邊界結尾）＋ops/loop/NOW.md byte-identical；每輪簿記後同步 4 簿記檔入 worker／argon worktree（in-scope diff 0×2）。
