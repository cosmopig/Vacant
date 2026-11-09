# NOW — Vacant（ops/loop 鏡像）

## 現況：r1299 redo 落地 — 1362B/1646B 重算＋5 點名檔實開（vq-el4.43，已關）
- **redo（本輪）**：1362B/1646B 自 git 物件重算（3bf1b5f4e：NOW 1646／鏡像 1362，一致、不更正）；
  5 點名檔實開（auto-ci.yml 63L grep disable 0／effects summary 50 cells／g25 filing 3 門 PASS 3/3 MATCH／
  extract 1217L 51abfec3／repair 2795L 5147f8c3）。0 更正。
- **r1299 基底（上一段）**：三分支簿記漂移閉環＋vq-el4.41 補登（vq-el4.42 已關）；
  17 passed×3＋FROZEN_STATE_OK×3＋diff 0×2。
- **CI 一次讀取（不 poll）**：worker@39ccc65ea（pre-sync）RED——2 failed＝恰兩 live 測（實證漂移根因）；
  新 HEAD 待 runner。

## Next（依序）
1. CI：新 HEAD 在跑/排隊；輪末一次讀取、不 poll。綠→收尾；紅→依證據診斷（不猜）。
2. vq-1zf G3：待人工明確核准 → 然後 `--fire`（manifest 已 planned）。
3. CI 通道（auto-ci.yml disabled_manually）：待人類裁決、不重診斷。

## 常規
- TDD RED→GREEN＋負控制；fail-closed；不得以改文件／同步數字充實進程。
- STATE.md＝完整賬本；ops/STATE.md＝鏡像（title＋Current State）；
  NOW.md 與 ops/loop/NOW.md byte 一致；≤5 行/≤3KB。
- 簿記收口 checklist（r1299 教訓）：4 檔全更新→freeze_check＋17 測綠→同步 worker/argon＋commit
  →三分支複驗（commit 後複跑，非 commit 前）。
