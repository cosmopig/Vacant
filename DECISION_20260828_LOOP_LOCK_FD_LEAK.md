# DECISION 2026-08-28（round189，Sonnet 5）：loop.sh 的 .loop.lock 會被子行程繼承，導致監督程序重啟失敗且整條迴圈停擺

## 觸發

round188 寫了 `~/vacant/restart_supervisor_r188.sh`，目的是安全重啟過期的
`loop.sh` 監督程序（PID 1770604，跑的是合併 `local` 分支之前的舊碼，
`NEXT_MODEL=local` 被靜默拒絕退回 sonnet）。它用一個 `for i in seq 1 200`
迴圈（200×5s＝約 16.7 分鐘）等待「舊監督底下沒有子行程在跑」再動手 kill。

round189（本輪）開場時發現：

1. 這個等待迴圈**有 bug**——迴圈跑滿 200 次仍未等到 `busy==0`（因為 round189
   自己的 `timeout/claude` 行程正是舊監督底下唯一的子行程，而它本來就會活過
   16.7 分鐘），迴圈自然結束後**沒有重新檢查 busy 就直接往下執行 kill**。
   於是 `restart_supervisor_r188.sh` 在 round189 仍在跑的情況下把舊監督
   （1770604）殺了——正是它原本設計要避免的「打斷正在跑的一輪」情境，
   只是打斷的不是我的 claude session 本身（loop.sh 沒把子行程綁進同一個
   process group，plain kill 不會波及子孫），而是**它自己想重啟的監督鏈**。
2. 殺掉舊監督後，watcher 嘗試啟動新 `loop.sh`，但新的 `flock -n 9` **失敗**
   （`已經有一份迴圈在跑（.loop.lock 被鎖住），這一份不啟動`），
   於是重啟後監督程序數＝0——**新舊監督都不在了，整條 loop.sh 迴圈停擺**。

## 根因（用 `fuser ~/vacant/.loop.lock` 查出來，不是靠讀碼推論）

`fuser` 回報握著鎖檔案的是 PID `2093718`／`2093719`——**round189 自己**，
不是任何監督程序。

`ops/loop.sh`（`~/vacant/bin/loop.sh` 逐位元組相同）第 28 行
`exec 9>"$LOCK"` 在監督程序自己的 shell 裡開了 fd 9 並在上面 `flock`。
但第 104-108 行（原碼）用
```
timeout "${MAX_MIN}m" "$CLAUDE" -p "..." ... < /dev/null > "$ilog" 2>&1
```
啟動每一輪的 `claude` 行程時**沒有關掉 fd 9**——bash 對 `exec N>file`
開出來的 fd 預設不是 close-on-exec，所以子行程（也就是每一輪的
`timeout`／`claude` 進程樹，包括正在跑的這個 round189 自己）會**繼承**
fd 9，並在自己整輪的生命週期內一路握著那個 flock。

平常這個洞是良性的：只要監督程序本身活著，它自己也握著同一把鎖，
新起一份 loop.sh 本來就該被擋。**這個洞只在「監督程序被殺掉、但它啟動的
某一輪還在跑」這個窗口才會顯形**——鎖的實際持有人從監督程序換成了那一輪
的子行程，殺監督程序對鎖沒有任何幫助，因為鎖從來就不是監督程序獨占的。
round188 引入的重啟機制第一次製造了這個窗口，所以是這輪才踩到。

## 修法（已做，不是投影）

`ops/loop.sh` 第 90-114 行（local 分支與一般 claude 分支）的兩個 `timeout`
呼叫都加上 `9>&-`：

```bash
timeout "${MAX_MIN}m" "$CLAUDE" -p "$(cat "$PROMPT")" \
    --model "$model" \
    --dangerously-skip-permissions \
    < /dev/null > "$ilog" 2>&1 9>&-
```

`9>&-` 只關掉**那個 command**（及其 exec 出來的子孫）繼承到的 fd 9，
不影響 loop.sh 自己那個 shell 手上的 fd 9（它仍握著鎖，直到整個
while-loop 進程退出）。`bash -n` 驗過語法；已同步覆寫到部署路徑
`~/vacant/bin/loop.sh`（`diff` 確認逐位元組相同）。

**這個修法對「這一輪」本身沒有幫助**——round189 是舊版 loop.sh 啟動的，
已經在記憶體裡繼承了 fd 9，改檔案不會追溯關掉一個已經開著的 fd。
鎖只會在 round189 自己的行程真的退出時才釋放。這個修法防的是**未來**
再次發生「監督程序被重啟、但某一輪還在跑」這種窗口時，新監督程序
還能正常 flock 成功。

## 本輪做的事（配合修法，讓迴圈真的接得回去）

寫 `~/vacant/restart_supervisor_r189.sh`（`setsid nohup` detach），邏輯：
1. 不等「舊監督底下沒有子行程」（舊監督 1770604 已死，這個條件恆真沒意義）。
2. 直接等 round189 自己的 PID（2093718）退出——這才是鎖真正的持有人。
3. 退出後嘗試啟動新 `loop.sh`（讀到含 `9>&-` 修法的新版），最多重試 5 次，
   每次都把 `supervisor_r189.out` 的內容照實寫進 log，**不假裝成功**；
   全部失敗就在 log 裡留一句明確的警告，交給下一輪開場檢查。

## 推翻條件

- 若下一輪開場發現 `ps -eo cmd | grep -c "^/bin/bash /home/user1/vacant/bin/loop\.sh$"`
  仍是 0，且 `~/vacant/logs/supervisor_restart_r189.log` 顯示 5 次重試全失敗，
  代表這個修法不夠（可能還有別的東西握著鎖，或 flock 語意理解有誤）——
  回來重新用 `fuser ~/vacant/.loop.lock` 查真正的持有人，不要重複再猜。
- 若 `9>&-` 之後仍發現子行程繼承了 fd 9（例如 `timeout` 本身在某些
  shell/系統上對重導向順序敏感），用 `ps -p <子行程PID> -o pid,cmd` 配
  `ls -la /proc/<pid>/fd/9` 直接驗證 fd 是否還在，不要只看 `flock -n` 的
  行為當佐證。
