# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結）、G2 已完（凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1414、2026-11-10）

r1414＝驗收＋落地 r1413（qwen3.8-27b、rc=124）未收尾改動（vq-el4.92 結案、非簿記輪）：
- **輪首紅燈→收口**：ci_tip_check（一次讀取）CI_TIP_BROKEN rc=1（qwen27b NO_COVERAGE＝r1413 三檔未被綠 CI 測量；worker COVERED；argon TIP_GREEN 5151 passed）；freeze_check 10/12 BROKEN（r1413 三檔未 sync）→ **12/12 FROZEN_STATE_OK rc=0**
- **r1413 vacuous 修復驗收**：零分支輸入（舊碼 all([]) 恆真→CI_TIP_OK 空集綠燈、r1272/r1334 同族）→ 修後 `--branches '{}'` → CI_TIP_BROKEN rc=1（證據點名 vacuous）＋負控 (i) 綠；佔位 .9x 解析為 vq-el4.92（3 處純文字、pin c0d41a91→90f3a0ab 在案）
- **三分支落地**：三檔 sync 入 worker 8cb8b7472／argon f6d7f43de（首次 sync 取到 .9x 版本、grep 抓到後修正）；in-scope blob 3 檔×3 分支全同；守衛 8 檔 **115 passed × 3 分支**（＝基線 114＋負控 (i) 1）；GUARD_CONTENT_PIN 12/12 MATCH（獨立重算）；ves EFFECTS_SUMMARY_OK rc=0（與 r1412 數字一致）；g3gate NOT_FIRED PLAN_OK；queue 空（含隱藏）
- **輪末 ci_tip_check（一次讀取）**：3× NO_COVERAGE CI_TIP_BROKEN rc=1——待新 tips（a08a6f7d7／8cb8b7472／f6d7f43de）綠 CI；下輪頭次讀取確認收斂

## 下一步

1. 下輪開頭重跑 `python3 ops/reqloop/ci_tip_check.py`（一次讀取、不 poll）確認三分支收斂（新 tips 被綠 CI 測量）。
2. 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決（auto-ci.yml disabled_manually、本地 vacant-ci 實效通道；不翻開關、不重複診斷）。

## 紅線

- 不讀 /srv/eval/hidden/ 與 scorer.py；G3 不入 /srv/vlab/queue（維持空、含隱藏）；G3 只待人類 --fire 後發射。
- main 不碰；無 push（loop 自推）；.github/workflows/ 零改動；無 reset/rebase。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改；r1408 解凍 2 檔（g3gate.py f1bd86be…／test_reqloop_g3gate.py 86bac89d…，vq-1zf.7 記錄在案）已釘。
- 守衛/尺子改動＝顯式 pin 更新＋解凍記錄（r1414 例 ci_tip_check c0d41a91→90f3a0ab、vq-el4.92 在案）。
- 0 模型呼叫（glm 未用）；不跑 full pytest；不 sleep poll；不以改文湊進展；數字一律實跑／重算驗證。
- 簿記：canonical＝repo STATE.md＋NOW.md；鏡像 ops/STATE.md＝canonical byte 前綴（至最新條目行、行邊界結尾）＋ops/loop/NOW.md byte-identical；每輪簿記後同步 4 簿記檔入 worker／argon worktree（in-scope diff 0×2）。
