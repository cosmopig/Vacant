# axis2_disk：主軸 2 —— ~/.vacant 真實用量與回收（round 133，2026-10-28 發射）

1. 問題：在**真實使用者機器**上 Vacant 到底佔多少磁碟？**回收有沒有在真實使用裡被觸發並生效**？**回收後追緝（簽章鏈／blame）還站不站得住**？
   （ASSIGNMENT 主軸 2；e001 研究包 §5 掛勾「從 cell.json 彙整 C 組 vacant_home_bytes」。）

2. 量具與來源（**共用量具 cell.py / labd.py / report.py 零改動**）：
   - `ops/vlab/tools/disk_report.py`（本輪新增，含 `--selftest`）：讀格子 `cell.json` 的
     `vacant_home_bytes`／`vacant_objects_bytes`／`workspace_bytes`、`score.json`，
     以及 `vacant_home.tgz` 內的 `.vacant/gc_last.json`／`.vacant/gc_report.json`
     （＝auto_gc 在真實使用中被觸發過的證據）。
   - 真實使用者機（本 dev VM，數週真實使用）：`vacant usage`（分區用量）、
     `vacant_network.retention.verify_trace_chains`（全專案鏈驗證）。
   - 回收路徑實測：`axis2_reclaim` 實驗的 keep-home 格子（真實 pi 跑的 C 組 cell，
     其 `~/.vacant` 含 trace/objects），對**該真實產物**跑產品 API
     `retention.compact_trace(active_window_s=0.0)`（＝把該專案當非活躍），
     前後 `usage` 數字＋`verify_trace_chains`＋blame 誠實狀態。

3. 實測（2026-10-28 07:00–07:20 區間）：
   - **單次任務 session（e001 C 組，真實 pi 0.8x＋乾淨 HOME）**：10/10 格有
     `vacant_home_bytes`：home **19–115 KB**、objects **18–77 KB**、workspace 含快照
     約 19–115 KB。⇒ 每 session 磁碟成本是 **KB 級**，不是 MB 級。
   - **auto_gc 在真實使用中被觸發**：e001 C 組 10/10 格 `gc_last.json` 存在且
     `status: ok`（Stop/session_end 掛鉤 → 背景 `vacant gc --auto`）；`bytes_freed: 0`
     ——數據是剛產生的、未過任何保留窗口，**「沒東西可清」是正確行為**，不是沒跑。
   - **A 組（沒裝）**：9 格無 vacant 欄位（未裝 ≠ 0 用量，量具誠實標記為未測）。
   - **真實使用者機（本 dev VM）**：總計 **800.80 MB**（apparent）；
     `trace_objects` **771.03 MB / 21,213 個物件**；其餘 intake 2.09 MB、
     trace_projects 11.87 MB、quarantine 0 B。
     771 MB 的主體＝**本 repo 自己的首掃快照**（`find` 實測 ≤8 MB 檔案
     **26,369 個、780.56 MB**）⇒ 與 `docs/RETENTION.md`「活躍專案穩態 ≈ 該專案
     ≤8 MB 檔案的快照總量」一致；不是洩漏、不是無界增長（受工作區規模限界）。
   - **回收後追緝站得住**：dev 機在多次小時級自動 gc 之後，
     `verify_trace_chains`：**145/145 專案簽章鏈全數通過**（2026-10-28 07:02 實跑）。
   - **真實 cell 產物的回收路徑**：（`axis2_reclaim` 格子完成後回填：
     前後 usage、釋放量、`verify_trace_chains` 通過數、blame 對被清步驟 → `unreadable/UNOBSERVED`。）

4. 誠實邊界（照實記，不修飾）：
   - **活躍專案的 ≤8 MB 快照按設計保留**（round 72：gc↔rescan whack-a-mole；
     回收它只買回 I/O、省不下持久磁碟）。多 GB 工作區的活躍專案會讓
     `trace/objects/` 佔數百 MB（實測 771 MB）。**目前沒有 CLI 開關**可回收活躍專案
     live 快照（只有 API `compact_trace(active_window_s=0.0)`）→ 已在 BACKLOG。
   - **「零設定：裝完就有上限」指的是 per-project 上限＋非活躍專案自動收縮**，
     不是全域 byte 上限；全域用量＝Σ 各專案快照＋保留窗口，受工作區規模限界。
   - 單 task cell 的 `bytes_freed: 0` 只證明「觸發且誠實」，**不證明 shrink 路徑**；
     shrink 路徑的證據＝dev 機（2026-10-24 一次自動 gc 釋放 743.7 MB／19,397 檔，
     `gc_report.json`，見 docs/RETENTION.md）＋`tests/test_retention.py`（11 項，
     含回收後鏈／blame 完好、fail-open、預算中斷安全點）＋本輪 axis2_reclaim 產物實測。
   - 本輪實測用 `dd2c6746` 的預建 venv（e001 同版本）；`1ada835b` venv 尚未預建
     （sudo 下 `vacant_env` 找不到 `/root/dev/Vacant`）——**e002 的 C/H/M/S 臂發射前
     必須先建好 `1ada835b` venv**（列入下一輪前置）。

5. 重驗：
   - `python3 ops/vlab/tools/disk_report.py --selftest`
   - `python3 ops/vlab/tools/disk_report.py e001_pi_AC_baseline --table`
   - `cd ~/dev/Vacant && .venv/bin/python -c "from vacant_network.retention import verify_trace_chains as v; print(v())"`
   - `cd ~/dev/Vacant && .venv/bin/vacant usage`

6. 下一輪：
   - e001 120 格完成 → `disk_report.py` 全量聚合：**C 組磁碟成本 × 通過/失敗結果**
     的配對描述（成本不是只看總量，要看「花多少磁碟買多少正確」）。
   - `1ada835b` venv 預建（e002 前置，見 §4 末）。
   - 若 supervisor 要「時間性回收」的真實證據：設計多專案／跨天 cell（現在沒有，
     不假裝有）。
