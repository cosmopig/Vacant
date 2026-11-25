# 留出教材產生器（heldout-v1）

由 agy（Gemini，khc.haruki 帳號）在 `~/dev/heldout_gen`（Vacant repo 以外的空 repo）照規格寫成，commit `aba9982`；
規格全文在 `~/dev/ops/agy_tasks/heldout.md`（不入庫，內容只有教材規格與「不准讀 Vacant repo、worktree、ops、~/.claude」）。
它沒有拿到 `trace sources`／`blame` 的實作與先導紀錄；agy 的輸出紀錄裡沒有出現那些路徑（同一個使用者帳號，技術上擋不住，只能事後查）。

這裡是那三支檔的逐位元複本（產生留出教材之後才放進來）。執行：`cd ops/d2/heldout_gen && python3 gen_heldout.py --seed S --sets N --out DIR && python3 check_heldout.py DIR`。

- 留出主批次的教材：seed 20261134、20 組，manifest sha256 `2512a2c5d05d5b7fccd537046556311dd994ab9e92d2b1bef74cab3b7e55bd8c`（不入庫）。
- 冒煙用的樣本：seed 99、3 組，manifest sha256 `5ecb92766e61d5ac6f31d908cb92be3fdeafeb00be365666f7dbda0341cc6286`。
