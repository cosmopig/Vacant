# 留出教材產生器 v2（heldout-v2，較難）

由 agy 在 `~/dev/heldout_gen2`（Vacant repo 以外的空 repo）照規格寫成，commit `885a526`；規格在 `~/dev/ops/agy_tasks/heldout2.md`（不入庫），
內容只有教材規格與「不准讀 Vacant repo、worktree、ops、heldout_gen、~/.claude」；agy 的輸出紀錄裡沒有出現那些路徑（同一個使用者帳號，事後查）。
它沒有拿到產品的出處實作、先導紀錄或第一輪的任何結果。這裡是逐位元複本（產生留出教材之後才放進來）。

較難的地方（檢查器實測，正式種子 20 組）：值所在的句子不含實體名 60%；同一個值字串在別處代表不同的量 60%；同一事實出現在多頁 45%；長頁面、干擾數字約為宣稱的 4.5 倍。

- 正式：seed 20261145、20 組，manifest sha256 `293a8293dd00baa06388e05e09a726528efded34d08d340719a5ef92091eae67`（不入庫，開跑前沒有人讀內容）。
- 冒煙樣本：seed 99、4 組，manifest sha256 `b341b53e8549423455376127130b51aeb1fb9ced3bf4086bf98e105c030f5176`。
