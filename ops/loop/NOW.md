# NOW.md — 現況（≤3KB）

## 輪次／階段／狀態
r1426（2026-11-11）：**G3 已發射**（vq-1zf，全庫唯一 open）。人類核准檔 `~/dev/ops/approvals/g3_vq-1zf_fire_20261111.json`（approved=true、11-11T05:00Z、scope＝4 未見題×3 臂＝12 格、2M/日 quota fail-closed、缺值 UNKNOWN 不填 0）。
- 預檢全綠（0 模型呼叫）：`g3 --dry-run` 12 cells＋arm conformance OK＋DRY-RUN OK；`g3gate --fire --approval …` → verify_frozen OK＋budget OK＋APPROVED。
- 05:41:18Z `systemctl --user start vacant-g3-fire-20261111`（一次性 unit、無 [Install]＝不自動再發射）→ active；首格 dab_129 擷取 rc=0 6824 tok（05:41:27Z）、native_pi 格已進 pi agent 迴圈；out=`~/dev/ops/g3_fire_20261111`（repo 外）；/srv/vlab/queue 未寫。
- bd：vq-1zf claimed＋發射 note（核准檔/時間/out/12 格 scope/結果查法）。

## 下一步（下一輪）
- 查 G3 進度/結果（一次讀取、不 poll）：`systemctl --user status vacant-g3-fire-20261111`；`ls ~/dev/ops/g3_fire_20261111/cells/*`；`tail ~/dev/ops/state/vibe_calls.jsonl`（G3 purpose 新筆數）；完成後讀 cell json（g3 result/1）逐格事實報告（含失敗/UNKNOWN；hidden_after 全 UNKNOWN）。
- 12 格全完成→審計摘要入 repo 提交（raw 留 ~/dev/ops）；同批重複發射不得當獨立樣本。
- 輪首 ci_tip_check 一次讀取（本輪簿記 commit 無產品碼，預期 COVERED 維持）；待人類：CI 通道裁決。

## 關鍵約束（紅線）
- 無 push（loop 自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改；r1419/r1420/r1421 解凍已釘（g3.py 2ba95fe5…／test_reqloop_g3.py b07ce47e…／g3_conformance a7507f6a…／g3gate.py a1b10e2e…／test_reqloop_g3gate.py 86bac89d…；r1420＝AMEND-1 人類裁決之合法解凍、記錄在 GUARD_CONTENT_PIN r1420 條目）。
- /srv/eval/hidden/、scorer.py 不讀；anchors 5＋filing 3/3+3/3 每輪複驗。
- G3 發射中（12 格、2M/日額度內）；/srv/vlab/queue 空（0 項含隱藏）；無 sleep poll CI；無 full pytest。

## 證據與下輪驗證點
- `systemctl --user status vacant-g3-fire-20261111` → active (running) since 05:41:18 UTC。
- `tail ~/dev/ops/state/vibe_calls.jsonl` → 2026-11-11T05:41:27Z glm53「G3 dab_129 擷取需求」rc=0 finished 6824 tok。
- `python3 -m vacant_network.reqloop.g3 --dry-run` → DRY-RUN OK rc=0；`g3gate --fire --approval …` → APPROVED（發射前）。
- 本輪改動＝4 簿記檔×3 分支（條目＋鏡像＋NOW＋sync）＋bd claim/note；0 產品碼、凍結 4 檔＋filing 未改。
