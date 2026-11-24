# Colab／佇列的操作腳本（版控副本）

實際執行的是 `~/dev/ops/` 裡的同名檔（systemd user unit 直接跑那裡的路徑）；這裡是版控副本，改了 `~/dev/ops` 的檔就同步一份過來並 commit。
腳本裡寫死了 `$HOME/dev/ops`、`$HOME/dev/wt/nonpy` 等本機路徑，是這台機器的操作工具，不是產品的一部分。

| 檔 | 用途 |
|---|---|
| `colab_launch.sh` | 依 GPU 順序要機器、發射批次、接 keepalive；LAUNCH_OK 時確保該帳號的預算看門在跑 |
| `colab_keepalive_fetch3.sh` | 保持 session、poll 進度、跑完取回並停機；連續三次查不到 session 才判定消失 |
| `colab_guard2.sh` | keepalive 意外結束而 VM 還在時，重新起 keepalive |
| `colab_snapshot2.sh` | 每小時唯讀快照（v2.2：排除工作區副本、接受 tar rc 1、exec 帶 --timeout、失敗 10 分鐘內重試） |
| `colab_budget_watch.py` | 帳號級預算看門（看帳號上所有批次；取回失敗超過 2 小時停機；餘額地板） |
| `gpu_queue.sh` | 本機 GPU 佇列（pid 取自 `$!`；起 unit 要帶 MemoryMax 與 OOMPolicy=continue） |
| `orphan_watch.sh` | 砍掉格子結束後還活著的脫離測試行程 |

⚠ `colab_snapshot2.sh` v2.2 與 `colab_budget_watch.py` 只在本機用假的 colab 指令測過，**還沒在真的 Colab VM 上跑過**（見 `ops/redo/results/void/w35js_rerun_a100/FIXES.md`）。
