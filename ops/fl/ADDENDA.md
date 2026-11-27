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

## 2026-11-27 00:30Z — 先導第 1 輪跑完（448 列）：179 列 infra_void，原因是 OAuth 憑證被撤銷
- 00:1x–00:27Z 之間，24 題 × 8 臂（179 列）的每次嘗試都回 `Failed to authenticate: OAuth token revoked`。
- 原因：runner 在起跑時把 `~/.claude/.credentials.json` 複製進沙箱、唯讀掛載；主機上的 Claude Code 之後換了 token，舊的就被撤銷。
- 照規則：這 179 列不進分母、照實列出，不重跑。有效：B0／B0×3 36 題，其他臂 32–34 題。
- 下一輪要先修：每次嘗試前重新複製最新的憑證（或在偵測到撤銷時把該次標成 void 並暫停）。
- 結果（探索性；題目是 Haiku 篩題沒過的，B0 會往上回歸）：見 `ops/fl/results/pilot1_apps_haiku_summary.json`。
  - **沒有候選過門檻。**
  - GT 10/34 對 B0×3 8/36。
  - EX、TF、XM、MV、CT 的增益比例分別是 −0.23／0.28／−0.92／−0.92／−0.92。
  - 誤收率分別是 38%／42%／34%／69%／81%，GT 是 9%。
  - Haiku 花費 $2.10。
