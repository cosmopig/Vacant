# NOW.md — 現況（≤3KB）

## 輪次／階段／狀態
r1425 redo（2026-11-11）：例行機械複驗輪＋redo——審查點名 effects_20261105_summary.json 本輪直接開啟＋獨立重算（60228B／a710f7e44c…、50 格、policy30 13w g7/l6、once20 11w g7/l4、sess 35/20、API 915/457、tok 33670510/19503953）——0 更正。vq-el4 全數關；vq-1zf（G3）全庫唯一 open，待人類 `--fire`。
- 輪首 ci_tip_check 一次讀取 → CI_TIP_OK rc=0（qwen27b@b1fa10ef5 COVERED／worker@03f9d086 COVERED／argon@c044ea28 PEER_COVERED）。
- 守衛 8 檔 122 passed（freeze 27／anchors 5／ci_contract 2／ves 19／g3gate 27／g3 25／now_redline 5／ci_tip 12；涵蓋審查 115，g3 已增 18→25＝覆蓋擴大）；redo 後複跑仍 122 passed。
- GUARD_CONTENT_PIN 13 檔（含審查 12 檔）sha256 與磁碟 100% 吻合（獨立 hashlib 重算 0 差異）；repair 2795 行/148101B/5147f8c3…、extract 1217 行/57363B/e757aec5…；g25 filing 6/6 sha256 MATCH。
- verify_effects_summary → EFFECTS_SUMMARY_OK（policy30 13w/0r g7/l6、once20 11w/0r g7/l4、50 格）；freeze_check 12/12 FROZEN_STATE_OK。

## 下一步（下一輪）
- 唯一實質項（一輪內做完、一條指令）：若人類已核准 `--fire`（vq-1zf）→ 依 RLOOP_PLAN 發射 G3 並記錄結果；否則同款機械複驗（ci_tip_check 一次讀取＋守衛 8 檔＋freeze 12 項＋簿記三分支同步），不另造新工作。
- 待人類：① G3 `--fire` ② CI 通道裁決（現三分支全覆蓋）。

## 關鍵約束（紅線）
- 無 push（loop 自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改；r1419/r1420/r1421 解凍已釘（g3.py 2ba95fe5…／test_reqloop_g3.py b07ce47e…／g3_conformance a7507f6a…／g3gate.py a1b10e2e…／test_reqloop_g3gate.py 86bac89d…；r1420＝AMEND-1 人類裁決之合法解凍、記錄在 GUARD_CONTENT_PIN r1420 條目）。
- /srv/eval/hidden/、scorer.py 不讀；anchors 5＋filing 3/3+3/3 每輪複驗。
- G3 未發射（queue 空、0 項含隱藏、NOT_FIRED）；無 sleep poll CI；無 full pytest；本輪 0 model calls。

## 證據與下輪驗證點
- `python3 ops/reqloop/ci_tip_check.py` → VERDICT: CI_TIP_OK rc=0（本輪一次讀取；三分支 COVERED/PEER_COVERED）。
- `python3 ops/reqloop/freeze_check.py` → VERDICT: FROZEN_STATE_OK 12/12（redo 後複跑）。
- 守衛 8 檔 122 passed（freeze 27／anchors 5／ci_contract 2／ves 19／g3gate 27／g3 25／now_redline 5／ci_tip_check 12）。
- redo：effects_20261105_summary.json 直接開啟＋逐格重算（13w g7/l6、11w g7/l4、50 格）與 11-06 人類參考吻合，0 更正。
