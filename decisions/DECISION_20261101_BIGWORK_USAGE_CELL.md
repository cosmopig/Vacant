# DECISION 20261101 — bigwork 大工作區用量格子（Axis 2 驗收 (b) 缺口）

**日期**：2026-11-01（round 823）
**決定**：新增一個實驗題 `bigwork/bw_repo_readme`（新增，不改任何既有題），用於量測
C 組 `~/.vacant` 在 repo 級工作區（299M、6,541 檔案）上的真實用量——補上 Axis 2
驗收 (b)「一個大工作區的格子」的缺口。

**理由**：
1. 10/28 事件（🔴）：2G repo、23,594 個快照 → `~/.vacant` 872M（≈0.44× repo）。
   這是「專案越大紀錄越大」的失敗模式。
2. 現有 183 個 C 臂格子（e001–e009）workspace 全部 ≤23.1 MiB（dabstep 單一資料檔，
   檔案數 ~25）——量到的都是「小工作區」regime，無法判定大工作區下封頂是否有效。
3. 真機序列（本機 2G repo，72 點/86.9h，peak 82.3 MiB、gc ok/target_reached）已有
   大工作區證據，但那是開發者序列、不是另一台機器可重復的實驗室格子。

**邊界（保守取法）**：
- workspace 取 `~/dev/Vacant` 剔除 `.git`/`.venv`/`node_modules`/`runs`/`tmp`/`ops/gain`
  ＝ 299M、6,541 檔案 ≈ 原事件快照數（23,594）的 28%。取小不取大是因為 1004 磁碟
  剩 5.5G、labd 的 4G 護欄：staged 299M＋2 格 app 副本 598M ≈ 897M 後仍餘 ≥4G。
  全規模（1.3G/41k 檔案）格子留待 e009 完賽、磁碟有餘時再排（見 BACKLOG）。
- scorer 是**完成信號**（README.md 存在且 ≥200 B），不是質量判定；本實驗的主指標是
  `cell.json` 的 `vacant_home_bytes`／`vacant_objects_bytes`，不是 score。
- 不改 cell.py／labd.py／report.py（共用量具零改動）；不改既有四題庫任何檔案。
- 失敗模式（格子 infra／磁碟不足）：停發、留 queue 檔待人工，不刪任何東西。

**驗收線**（見 `ops/vlab/packets/e010_bigwork.md` §5）：C-r1 `vacant_home_bytes`
≤256MiB 穩態封頂、且 <0.5× workspace（149.5M）；envelope_compliance verdict=PASS；
任一量不到＝UNKNOWN，不寫 PASS。
