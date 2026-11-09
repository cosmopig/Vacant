# NOW — Vacant（ops/loop 鏡像）

## 現況：r1299 落地 — 三分支簿記漂移閉環＋vq-el4.41 補登（vq-el4.42，已關）
- **缺陷（機器發現）**：qwen27b bk_now BROKEN（ops/loop/NOW.md 鏡像停 r1298、canonical 已 r1298 redo）
  ＋worker/argon diff BROKEN（ops/STATE.md 停 r1298 條目）＋兩 live 測 qwen27b 紅
  ＋vq-el4.41 缺於 beads（記錄稱已關、bd list/search 無此 issue）。
- **根因**：r1298 redo（auto commit 3bf1b5f4e、rc=124）只捕獲 4 簿記檔中 3 檔、未同步 worktree、
  commit 後未複跑收口——與 r1298（vq-el4.40）同型。
- **修復（vq-el4.42）**：vq-el4.41 補登（create＋close、reason 引 redo 證據）；本輪 4 簿記檔
  3 分支對齊（qwen27b 更新→worktree checkout 同步＋commit）。0 產品改動、0 新代碼、0 模型呼叫。
- **驗證（本輪新跑）**：17 passed×3＋freeze_check 9/9 OK VERDICT: FROZEN_STATE_OK rc=0×3
  ＋in-scope diff 0×2（freeze_check live＋git diff 雙證）。
- **CI 一次讀取（不 poll）**：worker@39ccc65ea（pre-sync）RED——2 failed＝恰兩 live 測（實證漂移根因）；
  同步後新 HEAD（b1f2de295／da593442b／dacbf5563）待 runner、不 poll。

## Next（依序）
1. CI：三分支現 HEAD 在跑/排隊；輪末一次讀取、不 poll。綠→收尾；紅→依證據診斷（不猜）。
2. vq-1zf G3：待人工明確核准 → 然後 `--fire`（manifest 已 planned）。
3. CI 通道（auto-ci.yml disabled_manually）：待人類裁決、不重診斷。

## 常規
- TDD RED→GREEN＋負控制；fail-closed；不得以改文件／同步數字充實進程。
- STATE.md＝完整賬本；ops/STATE.md＝鏡像（title＋Current State）；
  NOW.md 與 ops/loop/NOW.md byte 一致；≤5 行/≤3KB。
- 簿記收口 checklist（r1299 教訓）：4 檔全更新→freeze_check＋17 測綠→同步 worker/argon＋commit
  →三分支複驗（commit 後複跑，非 commit 前）。
