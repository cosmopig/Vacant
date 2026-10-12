# 任務導向三題庫 94 題 × 零設定 v3.7（Colab G4，兩小時批次，2026-10-02）— RUNLOG

預註冊：`decisions/prereg/PREREG_20261002_COLAB_TASK3_V37.md`。時間 UTC。做法照 skill `colab-vacant-campaign`（含 10-02 空轉事故的修法：完成判斷只走檔案介面）。

| 時間 | 事件 |
|---|---|
| 08:06 | 人類：「找個兩個小時的任務導向的題目去做，兩個小時內要做完的，去比較結果給我」 |
| 08:07 | 選題：第一批備好的 DABench 30／DataBench 30／Polyglot Python 34（Mac 量具正 94／94、負 376／376）；舊 staged 只剩空目錄 ⇒ 從 `worktree-agent-a60e6be4976f52c82` @ `027a6a16` 的 `task_banks_20260927` 重新打包。兩組 A／C37（不設回合上限 ⇒ 提醒不會作用，不跑 C37R）；每格時限 1200 秒 |
| 08:07 | `colab new -s t3 --gpu G4`；vLLM 背景安裝、部署；kernel 保活；10:20 一律 stop 的保險 |
| 08:12 | 部署：wheel sha256 `92ddc44d…`（同 DABstep 批次）、114／114；圍牆負控制 OK。**VM 上量具**（`gauge_task3.py`）：正控制 94／94、負控制 376／376、失敗 0（`task3_gauge_vm.json`） |
| 08:12 | console 管道再次回空白 ⇒ VM 上的結果改用 `colab download` 取 |
| 08:13 | 預註冊凍結（本 commit）。沒有另跑冒煙：同一支 cell.sh／wheel 今天已在 DABstep 批次跑過 711 格；主跑最先完成的格子當冒煙看（只看 rc、安裝、score_rc） |
| 08:11:52 | **發射 `t3`**（`AGENT_TIMEOUT=1200`、48 位置、時限 09:21:52）；本機常駐：`sync_from_colab.sh t3`（每 5 分鐘）、`autostop_t3.sh`（**只走檔案介面**：SYNC_ALL_DONE，或 DRIVER_DONE 下載得到後 25 分鐘 ⇒ 補下載＋stop）、`cu_guard.sh t3 30`、10:20 保險 |
| 08:13 | 前 24 格：rc 0、沒逾時、C 裝上且走到交件前檢查；polyglot 格 `score_rc` 0、`agent_timeout_s` 1200、`max_turns` 空 |
| 08:59 | 253 格完成（第 1 次 188 全完）；逾時 A 19／C37 19；吞吐（代理帳本）：整批生成約 414 tok/s、單條中位約 10.5 tok/s、prompt 快取命中約 89% |
| 09:32 | 384 格；第 2 次 182／188；逾時 37／37 |
| 09:42:45 | DRIVER_DONE；09:44:59 同步 SYNC_ALL_DONE（10 個 chunk 驗過）；**09:47:04 自動 `colab stop`**（跑完到關機約 4 分鐘，沒有空轉） |
| 09:48 | void 檢查（不讀分數）：0 格；plan sha256 同凍結版 |
| 09:49 | 第一次讀分數、凍結分析：A 72.3% vs C37 75.0%，+2.7 pp，p＝0.36（不顯著）。結論 `decisions/conclusions/CONCLUSION_20261002_COLAB_TASK3_V37.md` |
