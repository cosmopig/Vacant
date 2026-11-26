# 快車道（ops/fl）ADDENDA

## 2026-11-26／27 — 先導第 1 輪（`fl_pilot1_apps_haiku`）兩次被 Claude Code 低記憶體回收器中斷

- **第 1 次**：約 16:24Z，停在 155/448 列。runner 是 Claude Code 背景 shell 的子行程，session 閒置、系統記憶體一度不足時被回收（系統 journal 沒有 OOM 紀錄）。使用者 23:35Z 說「繼續」，同計畫同 root 續跑。
- **第 2 次**：約 23:54Z，停在 179/448 列，原因同上。
- **處置**（vacant-hope 11-27 同意）：
  - 計畫與 root **都不變**：`ops/fl/plans/fl_pilot1_apps_haiku.json`、`~/dev/ops/fl/pilot1_apps_haiku`。
  - runner 支援續跑，已完成的列保留；中斷那一刻正在跑的格會重做。
  - 改用 `systemd-run --user -p MemoryMax=3G` 起成獨立單元，不受 session 回收器影響；cgroup 硬上限保護整台機器與正在跑的 rfh4。
  - 續跑前確認沒有上一輪殘留的 worker 或沙箱行程（`ps` 查過：0 個）。
- **若在 3 GB 上限內自己被 OOM**：受影響的列照計畫的基礎設施失敗規則處理、照實列出，不悄悄重跑到過。
