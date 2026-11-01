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
  剩 5.5G、labd 的 4G 護欄：staged 299M＋2 格 app 副本 598M（＝299M×2）≈ 897M（＝299M＋598M；兩數皆為對上方已記錄之 du 值 299M 的純算術）後仍餘 ≥4G。（stage 實值以 worker done 工單證據為準：du 300M／6,543 檔案，對應算術為 600M／900M；另本 repo 檔案數會隨開發漂移——11:3x 重測 8,253（含 458 個 __pycache__），故本數僅作預算，不作驗收。）
  全規模（1.3G/41k 檔案）格子留待 e009 完賽、磁碟有餘時再排（見 BACKLOG）。
- scorer 是**完成信號**（README.md 存在且 ≥200 B——200 B 為本包自訂的完成信號下限，屬**假設值**，非由任何已讀材料算出），不是質量判定；本實驗的主指標是
  `cell.json` 的 `vacant_home_bytes`／`vacant_objects_bytes`，不是 score。
- 不改 cell.py／labd.py／report.py（共用量具零改動）；不改既有四題庫任何檔案。
- 失敗模式（格子 infra／磁碟不足）：停發、留 queue 檔待人工，不刪任何東西。

**驗收線**（見 `ops/vlab/packets/e010_bigwork.md` §5）：C-r1 `vacant_home_bytes`
≤256MiB 穩態封頂、且 <0.5× workspace（149.5M＝299M÷2，對已記錄之 du 值 299M 的純算術；stage 實值 300M 時為 150M）；envelope_compliance verdict=PASS；
任一量不到＝UNKNOWN，不寫 PASS。

## round 841 重驗（2026-11-01；e010 開跑前）
- venv 凍結核實：`/srv/vlab/vacant/683bbb83b277d39beb8f4d3fb61c7eeb99e9064f/venv/pyvenv.cfg`＝
  `include-system-site-packages = false`（舊行為，cell.py 改動前建好）；`cell.py:41` early-return
  保證已建 venv 不會被重建（重建將走 `cell.py:56` `--system-site-packages`，會污染 e010 量具）。
- 驗收量具重驗：`ops/vlab/tools/envelope_compliance.py --selftest` 16/16 PASS（本輪重跑）；
  e008 dry-run C 30/30 PASS（max 231,785 B≈0.22 MiB；envelope_source＝
  `vacant_network.retention.STABLE_ENVELOPE_BYTES` 268,435,456 B）——量具在真實數據上可用；
  <150 MiB 口徑（0.5×workspace）以 `--envelope 157286400` 可跑。
- 排程與磁碟：labd PAR=1＋queue 串行（`/srv/vlab/labd.log:100-101` 13:36:18）→ e010 在 e009
  完賽後跑；free 5.6G ≥ 4G 護欄（`/srv/vlab/state/disk.json` 19:1x `paused=false`）。
- 結論：§5 驗收線的量具與前提就緒；e010 完賽前一切判定維持 UNKNOWN。
