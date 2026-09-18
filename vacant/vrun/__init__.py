"""`vacant run -- <任何 agent 命令>` 與 `vacant demo gate` 的判斷層＋執行層。

## 這一包在架構裡承重什麼

把 Vacant 的可究責層從「要 agent 配合呼叫我們」變成「把 agent 包起來」。
承重的洞察只有一句：

    「宣告完成」之所以難偵測，是因為只有要**注入回對話**時才需要它。
    如果只是要**攔下交付**，觸發點根本不在 wire 上——在 agent 行程結束的那一刻。

那個訊號 100% 可靠、零協定知識、零 token 成本、跨所有框架。所以 V0 不碰
「注入回對話」（見 `docs/VACANT_RUN.md` §為什麼 V0 不做注入）。

## 為什麼住在套件裡（2026-09-18 搬家）

人類的要求逐字：「要確保人家**下載之後馬上**可以在他的 agent platform 上感受到
plus vacant 的威力」。這一包原本住在 `ops/vacantrun/` 與 `ops/gain/r530/`，而
**`ops/` 不進 wheel**——`pip install vacant-network` 的人跑 `vacant demo gate`
只會拿到一句「請先 clone」。那不是安裝，那是把第一屏換成一段安裝說明。

所以是**搬家＋反轉依賴**，不是複製：

  · 判斷層（`acceptance`／`sandbox`／`wshash`／`receipts`／`verify_receipts`）與
    執行層（`launcher`／`wireproxy`／`envmap`／`demo`）的實作都住這裡；
  · `ops/gain/r530/*` 與 `ops/vacantrun/*` 的舊路徑留著，內容是
    `sys.modules[__name__] = <這裡的模組>` 的 re-export ⇒ R530／R531／R534 的既有
    引用一行都不用改，而且**同一個行程裡是同一個 module 物件**；
  · 所以**只有一份判準**。`vacant/suitegauge.py` 的 docstring 與
    `conform_failure_detail` 兩處都明文禁止「第二把會漂的尺」——複製一份進 wheel
    正好是那件事。

⚠ **不是整個 `ops/` 都進來了**，也不該進來。留在 repo checkout 裡的有：
`ops/vacantrun/block_egress.sh`（V3 出網封鎖，要 root）、
`ops/vacantrun/selftest.py`／`verify_egress_block.py`（維運自檢）、
`ops/gain/r530/` 的實驗本體（題庫、隱藏驗收、judge、排程器）。
哪些功能真的需要 clone，README 有一節逐條寫出來——**不含糊帶過**。

誠實邊界一律寫在 `docs/VACANT_RUN.md`，各模組的 docstring 只重述與自己相關的那幾條。
"""
