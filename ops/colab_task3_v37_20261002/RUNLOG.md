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
