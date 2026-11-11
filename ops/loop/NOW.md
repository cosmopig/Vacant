# NOW.md — 現況（≤3KB）

## 輪次／階段／狀態
r1418（2026-11-11）：收斂態＋修 r1417 auto-commit 紅燈。
- 主線：G2.5（凍結、閉）；G3（vq-1zf）待人類 `--fire`；vq-el4 全閉（0 open；r1418 vq-el4.93 建立即閉）。
- 開輪實測：freeze_check 3 BROKEN（bk_state TRUNCATED＋diff_worker/diff_argon）＝r1417 rc=124 超時未收尾之實際紅燈（非假綠）。

## 下一步（次輪）
- 常規：頭部 ci_tip_check 一次讀（不 poll）確認 CI_TIP_OK；freeze_check 12 項全核（含 3 分支 wt clean＋diff 0×2）。
- 實質新任務以人類批核或新產品 bug 為準；11-06 指示仍有效：不加同線重試、不加大規模重跑。

## 近期關鍵事件
- r1418：① bk_state：r1417 條目被寫在 header 正下方、header 後約定空行被擠到條目後→餘部非日期條目起始→空行歸位＋mirror head -5（2820B）→OK。② diff：r1417 簿記同步 worker/argon worktree（各 1 commit）→0×2。③ 護衛 8 檔 115 passed（2 個 live-verdict 測試紅→綠）。
- r1417：驗證＋簿記輪（auto-commit 8e3f1cd80、rc=124 未收尾→本輪紅燈源頭）。

## 關鍵約束（紅線）
- 不 push（loop 自動 push auto/qwen27b）、不 main、不 reset/rebase；.github/workflows/ 唯讀。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改；r1408 解凍 2 檔（g3gate.py f1bd86be…／test_reqloop_g3gate.py 86bac89d…，vq-1zf.7 記錄在案）已釘。
- /srv/eval/hidden/、scorer.py 不讀；anchors 5＋filing 3/3＋3/3 每輪複核。
- G3 未 fire（/srv/vlab/queue 空、NOT_FIRED）；不 sleep poll CI；不全量 pytest；本輪 0 model calls。

## 證據與次輪驗證點
- `python3 ops/reqloop/freeze_check.py` → VERDICT: FROZEN_STATE_OK 12/12（r1418 修後實測 OK）。
- `python3 ops/reqloop/ci_tip_check.py` → CI_TIP_OK（開輪一次讀；綠祖先 json 5152 passed/0 failed/74 skipped）。
- 護衛套件：8 檔 115 passed（27/5/2/19/27/18/5/12）。
- 本輪紅燈證據：開輪 freeze_check FROZEN_STATE_BROKEN（3 BROKEN）→修後 12/12 OK；vq-el4.93 已閉。
