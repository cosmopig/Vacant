"""`vacant run -- <任何 agent 命令>` 的 V0 實作（launcher ＋ wire proxy）。

這一包在架構裡承重什麼：把 Vacant 的可究責層從「要 agent 配合呼叫我們」
變成「把 agent 包起來」。承重的洞察只有一句：

    「宣告完成」之所以難偵測，是因為只有要**注入回對話**時才需要它。
    如果只是要**攔下交付**，觸發點根本不在 wire 上——在 agent 行程結束的那一刻。

那個訊號 100% 可靠、零協定知識、零 token 成本、跨所有框架。所以 V0 不碰
「注入回對話」（見 `docs/VACANT_RUN.md` §為什麼 V0 不做注入）。

誠實邊界一律寫在 `docs/VACANT_RUN.md`，各模組的 docstring 只重述與自己相關的那幾條。
"""
