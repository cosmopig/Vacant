# ops — 執行端（`user1-2`）的 24 小時迴圈

2026-08-15 人類指示：那台 Ubuntu VM 要 24 小時不間斷做事，每階段回報，
做完自我驗證，驗完迭代，並且要有外網看得到的執行日誌與進度大綱。

這個目錄是那套東西的**單一真相來源**。VM 上跑的是這裡 pull 下去的副本，
不要在 VM 上直接改——改了下一次 `git pull` 就衝突，而且稽核端看不到。

## 檔案

| 檔案 | 是什麼 |
|---|---|
| `LOOP_PROMPT.md` | 每一輪餵給 claude 的常駐指令。**這份是核心。** |
| `loop.sh` | 迴圈本體。每輪跑一個全新 session，記錄、數產物、產生進度頁 |
| `progress.py` | 產生外網看的進度頁 |
| `genimg-linux.sh` | Linux 版生圖包裝（Windows 版在 `HANDOFF.md` 提到的那支） |

## 為什麼每一輪是全新 session

`claude -p` 沒有跨輪記憶。連續性全部靠 `~/vacant/STATE.md`——
上一輪做了什麼、驗證方法是什麼、實際數字是多少、下一步從哪接。

**這不是限制，是設計。** 記憶在腦袋裡就沒人驗得到；記憶在檔案裡，
每一輪的自述都可以拿去跟 repo 裡的 commit 對帳。
`progress.py` 把「有沒有 commit」放在最顯眼的位置，就是因為
**那是唯一能證明某一輪真的做了事的東西，其餘欄位全是自述**。

## 安裝到 VM

```bash
cd ~/vacant/Vacant && git pull
mkdir -p ~/vacant/bin ~/vacant/logs ~/vacant/public
cp ops/loop.sh ops/progress.py ~/vacant/bin/
cp ops/genimg-linux.sh ~/vacant/bin/genimg.sh
cp ops/LOOP_PROMPT.md ~/vacant/
chmod +x ~/vacant/bin/*.sh ~/vacant/bin/progress.py
```

## 啟動

```bash
cd ~/vacant
setsid nohup ~/vacant/bin/loop.sh > ~/vacant/logs/supervisor.out 2>&1 &
```

**停止：`touch ~/vacant/STOP`** —— 當輪跑完就停。
不要 `kill`：那會讓一輪做到一半沒收尾，而沒 commit 的那一輪在稽核端等於沒發生。

## 外網看進度

```bash
cd ~/vacant/public && python3 -m http.server 8787 &
tailscale funnel --bg 8787
tailscale funnel status      # 看網址
```

⚠ **`funnel` 是對整個網際網路公開的**，沒有密碼。頁面上會有專案路徑、
commit 訊息、每一輪的日誌尾巴。只要在自己的裝置上看就夠的話，用
`tailscale serve --bg 8787`（只有同一個 tailnet 看得到）。

關閉：`tailscale funnel --https=443 off`

## `--dangerously-skip-permissions`

`loop.sh` 用了這個旗標，因為無人值守時沒有人可以按同意。
代價是那一輪的 claude 在那台 VM 上不會再問任何權限。

減害的部分寫在設計裡，不是靠自律：

- 工作範圍限定 `~/vacant`
- `LOOP_PROMPT.md` §七 列出**不准自己決定**的事（視覺方向、persona 資料邊界、
  永久排除、刪資料、改寫歷史、推到別的分支、裝要 sudo 的東西）
- 單輪 45 分鐘上限，逾時中止
- 那台沒有免密碼 sudo，動不了系統
- 每輪 commit + push，稽核端看得到每一次改動

## 稽核（Mac 端）

```bash
ssh user1@100.124.254.83 'cat ~/vacant/STATE.md; tail -40 ~/vacant/logs/loop.log'
git -C ~/Documents/GitHub/vacant_hm log --oneline -20
```

看的是 commit 不是回話——今天已經有十四次「回報成功但產物是錯的」，
其中最惡劣的一次是訊息送到了名字對但機器錯的 session，而每一次都回報成功。
