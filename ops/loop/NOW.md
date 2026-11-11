# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結）、G2 已完（凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1417、2026-11-11）

驗證＋簿記輪（0 代碼改動、0 model calls），全綠＋審查 redo（effects summary 直開、逐格獨立重算、0 更正）：
- 審查 redo：effects_20261105_summary.json 60228B sha256 a710f7e4…（ves pin）直開＋cells_detail 逐格重算——policy30 30 格 w2r 13（g7/l6）r2w 0、sess 35＝19+16、API 915＝365+550、tok 33670510；once20 20 格 w2r 11（g7/l4）r2w 0、sess 20＝10+10、API 457＝165+292、tok 19503953；total 50／local 45／current 50 全 MATCH 0 更正
- ci_tip_check（輪首一次讀取、不 poll）：**VERDICT: CI_TIP_OK rc=0**——qwen27b@b1372e492 COVERED（綠祖先 a08a6f7d7..tip 純簿記 4 檔）；worker@24f2939f PEER_COVERED（root tree 位元組恆等）；argon@52fa0034 COVERED；綠底 5152 passed/0 failed/74 skipped（三分支同一）
- freeze_check：12/12 FROZEN_STATE_OK rc=0（anchors 5／ci_contract 2／diff 0×2／filing 3/3＋3/3／g3gate NOT_FIRED PLAN_OK／queue 空（含隱藏）／bk 同步／wt clean 3/3／now_redline 相符）
- 守衛套件 8 檔 115 passed（27/5/2/19/27/18/5/12；審查基線 114＋r1413 負控 (i) 1、0 弱化）
- bd：vq-el4 94/94 全閉、0 open；唯一 ready＝vq-1zf（G3）待人類 --fire；/srv/vlab/queue 空；無新人類指示（ops/ 最新仍 11-07）

## 下一步

1. 下輪常規：頭次 `python3 ops/reqloop/ci_tip_check.py`（一次讀取、不 poll）維持收斂態（CI_TIP_OK）。
2. 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決（auto-ci.yml disabled_manually、本地 vacant-ci 實效通道；不翻開關、不重複診斷）。

## 紅線

- 不讀 /srv/eval/hidden/ 與 scorer.py；G3 不入 /srv/vlab/queue（維持空、含隱藏）；G3 只待人類 --fire 後發射。
- main 不碰；無 push（loop 自推）；.github/workflows/ 零改動；無 reset/rebase。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改；r1408 解凍 2 檔（g3gate.py f1bd86be…／test_reqloop_g3gate.py 86bac89d…，vq-1zf.7 記錄在案）已釘。
- 守衛/尺子改動＝顯式 pin 更新＋解凍記錄（r1414 例 ci_tip_check c0d41a91→90f3a0ab、vq-el4.92 在案）。
- 0 模型呼叫（glm 未用）；不跑 full pytest；不 sleep poll；不以改文湊進展；數字一律實跑／重算驗證。
- 簿記：canonical＝repo STATE.md＋NOW.md；鏡像 ops/STATE.md＝canonical byte 前綴（至最新條目行、行邊界結尾）＋ops/loop/NOW.md byte-identical；每輪簿記後同步 4 簿記檔入 worker／argon worktree（in-scope diff 0×2）。
