# T05 — 把同一個政策做進產品指令，再用同一支 harness 量（S3）

**前提**：T04 的 state＝EFFECTIVE。**這是這條分支第一張改產品碼的票。**

## 要的行為（使用者只打一行；沒有契約、沒有設定檔）
在一個有測試檔的專案裡：

    vacant do pi --prompt "<任務>"

沒有任務契約時不要再回「no task contract found」，改成零設定模式，政策與 `ops/redo/redo.py` 的 R3 **逐條相同**：
1. 驗收訊號＝專案在開始那一刻就有的測試檔（先支援 `*_test.py`／`test_*.py`＋`python3 -m unittest`）。
   跑驗收之前把這些檔還原成開始時的內容；被改過要記下來。
2. 每一次嘗試在全新的隔離工作區、全新的 agent 行程；嘗試之間不留任何東西、不給失敗原文。
3. 驗收通過就停、交那一次；最多 3 次，每次 600 秒，合計 1800 秒；都沒過就交原件測試過最多的那一次，
   並在給人的訊息裡明講「測試沒有全過」。
4. 專案裡沒有測試檔 ⇒ 跑一次、照實說「沒有可執行的驗收」，不假裝檢查過。
5. 既有行為不動：有契約時走原本的路；`vacant do` 既有測試全綠。

實作位置建議：`vacant_network/adapters/cli.py::cmd_do`（沒有契約的分支）＋`vacant_network/adapters/run.py`。
政策的三個函式可以直接照 `redo.py` 的 `acceptance`／`_policy_stop`／`_policy_deliver` 寫。先寫會失敗的測試再實作。

## 量（產品指令的數字，和 T03 的機制數字分開講）
1. 複製 `screen16_pi_gemma12b.json` → `screen16p_pi_gemma12b.json`：取新 `id`；加第三個臂
   `"P": {"policy": "single", "attempt_timeout_s": 1800, "agent": {"argv": [<產品指令，含 {prompt}>], …}}`，
   `pair` 改成 `["A", "P"]`。commit 後照 T02 的方式跑。
2. 篩選判定：P 對 A 同樣用「c ≥ b + 3 且 accepted_but_wrong == 0」。GO 才複製 `redo1_…` 做 34×5 的確認批。

## 驗收
- 改動前先跑一次 `python3 -m pytest tests/ -q -k "adapters or redo"`，記下通過／失敗數；改動後新增的測試先紅後綠，
  而且原本通過的一個都沒有變紅（原本就紅的不在這張票的範圍，不修）。
- `screen16p` 的 `REPORT.md` 進 `ops/redo/results/`。
- 對外口徑（README／CLAUDE.md）**不在這張票**：確認批 EFFECTIVE 之後由人類看過再寫。

## 禁止
- 不為了讓 P 過而改 `redo.py` 的判定；不在產品碼裡認題庫的檔名或題號。

## 票尾（做完填這三行，再把票移到 done）
- commit：
- 驗收指令的實際輸出（逐字貼最後一行）：
- 沒做完的：
