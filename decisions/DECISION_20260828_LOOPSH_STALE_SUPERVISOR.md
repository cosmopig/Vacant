# DECISION 2026-08-28 — loop.sh 監督程序過期，NEXT_MODEL=local 從未真的生效

## 發現（round188，Sonnet 5）

`NEXT_MODEL=local` 這個省 token 機制自 round187 起被設定，但**每一次都被
靜默拒絕退回 sonnet**，且這不是 round187 才開始的——`~/vacant/logs/loop.log`
顯示 iter-4389（2026-08-28 01:24:52，在 round187 存在之前）就已經印過同一句：

```
NEXT_MODEL 寫著「local」，不是 opus/sonnet，用預設 sonnet
```

本輪（iter-4393）又再印一次一模一樣的訊息。但 `ops/loop.sh`（無論是 git repo
裡的 `Vacant/ops/loop.sh` 還是部署路徑 `~/vacant/bin/loop.sh`，兩份逐位元組
相同）目前的原始碼明明是：

```bash
case "$want" in
  opus|sonnet|local) model="$want"; say "  上一輪指定模型：$model" ;;
  ...
  *) say "  NEXT_MODEL 寫著「$want」，不是 opus/sonnet/local，用預設 $model" ;;
esac
```

拒絕訊息裡有 `/local`，但 loop.log 印出來的訊息**沒有** `/local`。這代表
**正在執行的監督程序（PID 1770604，`ps -o lstart` 顯示 2026-08-24 08:04:08
啟動）用的是記憶體裡的舊版程式碼**——`local` 分支是後來（commit `bba57d3`，
2026-08-28 09:17:23+0800）才加進去的，比這個監督程序的啟動時間晚了快 4 天。
bash 的 `while true; do ... done` 迴圈本體在第一次進入時就整段讀進記憶體，
之後 `git pull` 更新磁碟上的檔案內容**不會**讓一個已經在跑的迴圈行程重新
讀取——除非整個監督程序被重啟。

## 影響

從 bba57d3 合併（round182/183 之間）到本輪（round188）為止，**所有
monitoring-checkpoint 這種「動作清楚判斷少」的輪次，本來應該可以省下的
Sonnet token，一次都沒省到**——因為 NEXT_MODEL=local 這個交接機制
從來沒有真的把控制權交給 `ops/localagent.py`，全部靜默退回 sonnet。
這不是本輪才發生，是自功能合併起就沒生效過，只是先前輪次沒有交叉比對
`loop.log` 的實際輸出跟 `loop.sh` 檔案內容，所以沒發現訊息文字對不上
（`round187` 誤判「never exercised」——其實是「exercised 但被舊行程吃掉」，
兩者外部觀察結果一樣（下一輪都是 sonnet），只有比對 loop.log 訊息文字
才分得出來）。

## 決定：安全重啟監督程序，不直接在本輪內 kill

**做了什麼**：寫了 `~/vacant/restart_supervisor_r188.sh`，用
`setsid nohup` detach 成一個獨立行程（PID 見
`~/vacant/logs/supervisor_restart_r188_launch.log`），邏輯：
1. 等本輪自己的 `claude -p` 行程（PID 2092745，`timeout 45m` 那層）真的退出。
2. 等舊監督程序（1770604）底下暫時沒有子行程在跑（避開下一輪的
   in-flight 視窗，不要打斷正在跑的一輪）。
3. 確認舊監督程序還活著才 `kill`（plain kill，不帶 `-9`，不用
   process-group signal——`loop.sh` 沒有用 `setsid` 包住它呼叫的
   `timeout ... claude -p`，所以 plain kill 只會終止監督程序自己，
   不會波及它已經產生的子孫行程；子孫行程會被 reparent 到 init，
   繼續跑到自然結束）。
4. 起一個新的 `loop.sh`（`setsid nohup`），讀到的是磁碟上最新版原始碼，
   含 `local` 分支。

**為什麼不在本輪內直接 kill**：本輪自己就是這個監督程序底下的一輪
（`ps` 逐層往上追：`2093146`→`2092746` claude→`2092745` timeout→
`1770604` loop.sh），如果在本輪工作做完之前就 kill 監督程序，
沒有已知風險會直接殺死本輪自己（plain kill 不會波及子行程），
但**監督程序死掉之後，它原本要做的「這一輪的結束記錄、`ahead` 檢查、
`progress.py`、`sleep $GAP` 再啟動下一輪」全部不會發生**，且如果
新監督程序啟動得太早、跟舊監督程序底下還在跑的某一輪重疊，可能
造成兩個 `claude -p` 行程同時對同一個 git repo 操作。用 watcher
等到「本輪已經結束」且「舊監督底下沒有子行程在跑」的空檔再動手，
把這個風險降到最低。

**沒做的事**：沒有立刻驗證重啟是否成功——這個 watcher 是 detached
背景行程，在本輪結束前不會有結果。**下一輪開場必須檢查**
`~/vacant/logs/supervisor_restart_r188.log` 這份記錄，確認：
- 舊監督程序（1770604）真的被 kill 了。
- 新監督程序真的啟動了（`ps -eo cmd | grep -c "^/bin/bash /home/user1/vacant/bin/loop\.sh$"` 應該是 1）。
- 如果重啟失敗或卡住，不要重複再跑一次同樣的 watcher（可能疊加出多個
  監督程序）——先看 log 判斷卡在哪一步。

## 推翻條件

如果下一輪發現 `supervisor_restart_r188.log` 顯示 watcher 已經跑到
「重啟後監督程序數：1」但下一次 `NEXT_MODEL=local` 還是被拒絕退回
sonnet，代表問題不是「監督程序過期」這麼簡單（可能是新監督程序
啟動時又複製了一份舊的 `bin/loop.sh`，或者 `ops/localagent.py`
本身有其他問題）——那時候要重新診斷，不要假設本次修復已經生效。
