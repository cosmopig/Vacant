# mirror2（2026-10-13）：習慣句更分散、更有個人味，每句尾端「（第 N 步）」對得上收據的逐步清單

* `recompute_r7.py`：用 divine 那 30 張真跑（round3 的 24＋round4/live 的 6）離線重算，走真的 `fortune.build_card`
  （做法同 `evidence_divine_20261007/round6/recompute_r6.py`；這版另把每次嘗試的逐格結果還原成 `visible_path`，讓「被退回的原因」走真的 `retry_ids_of`）。
  輸出 `cards_r7.json`、`habits_r7.txt`。
* `cards_before.json`：mirror 第一版（`recompute_r6.py` 的輸出，10-12）。
* `analyze_r7.py` → `compare.txt`：前後分布表（數字一律當 N，同一種句型換個數字不算不同句）。
* `sample6.txt`：隨機 6 張（種子 1013）。

⚠ 誠實：旁註 `twin_step` 不帶檔名，路徑由位元組數還原（同 r6）；「做出來的東西」的內容判準（問號／留餘地的詞／數字／字數）
用的是 `made_things` 全文。稀有度表（`fortune.RARITY`）是依這 30 張的出現率手訂的固定表，不用模型、不看「這一批」——展場一張一張出卡。

## 「第 N 步」怎麼對上收據
* N＝`twin_steps.ndjson` 裡那一行的順位（1 起算；`fortune.read_steps` 給每列 `_n`，**不是**排序後的位置）。
* 收據副本（`twinagent.receipt_bundle`）多帶 `steps`＝`fortune.public_steps`（只有 n／t 讀寫列／k 哪一類／ok，沒有檔名與內容）與 `steps_sha256`；
  雲端 `receipt.html` 逐步列出（id＝`s<N>`）、在瀏覽器重算雜湊、`receipt.html?id=…#s<N>` 高亮那一步；手機的過程清單用同一個編號。
* ⚠ 誠實：簽章鏈（ws_attempt／ws_verdict）簽的是每次嘗試的工作區雜湊與裁決；逐步清單是同一跑的紀錄副本，**附雜湊、沒有逐步簽章**。
  頁面上照實這樣寫；要做到「每一步都簽」需要 0.9.1 掛鉤的 trace 鏈（線 A）。
* `screens/`＝390×844@2x 截圖（雲端 repo `evidence/mirror2_20261012/` 同一份＋`shoot.mjs`）。
