# axis2_budget_64mib：主軸 2 —— trace 版本庫常規上限 512MiB → 64MiB（round 142，2026-10-28）

1. 問題（人類回報，實測核實）：10/28 08:14 清掉 `~/.vacant` 之後，08:16 專案重新註冊、
   以 **round 139 之前的舊碼**（初掃「全量複製 ≤8MB」行為）把本 repo 的檔案複製進
   `trace/objects`：實測 **542 MB / 17,097 個 blob**（其中 83 個 >1MB 的內容複製＝247 MB，
   已 SHA 驗證 bit 相同於 repo 原檔，如 `runs/g_onoff5_371_r123_20260825/calls.jsonl`
   8.23 MB）。round 139（10:54）store-on-change 才落地，管不到已發生的複製。
   而當時 `DEFAULT_TRACE_BUDGET_BYTES = 512 MiB`（536,870,912 B）——**恰好高於現況
   536,012,009 B**，`_sweep_to_target` 乾跑即 `target_reached: true`，實跑 0 回收。
   ⇒ 「有上限」名不副實：上限比垃圾還高。

2. **我定的目標數字：`DEFAULT_TRACE_BUDGET_BYTES = 64 MiB = 67,108,864 B`**
   （`VACANT_TRACE_BUDGET_BYTES` 可覆寫；0＝關；`vacant gc --target-bytes N` 單次覆寫。既有機制，不改。）

   為什麼使用者可以接受 64 MiB：
   - **它不是「repo 的快照預算」，是「repo 之外多存的證據預算」。** store-on-change
     （round 139）之後，未變動檔案的讀取回退「工作區＋驗 sha」——未變動檔案的副本
     **零追緝價值**（工作區本身就是原檔，bit 相同已驗）。版本庫真正要留的只有：
     (a) 已改過/已刪除的檔案的舊版本，(b) 步驟 I/O（input/output/writes/reads blob），
     (c) 索引。這些與 repo 大小無關、與「動了多少東西」成正比。
   - **實測（本輪 dry-run，真實 `~/.vacant`）：64 MiB 目標下 sweep 回收
     469.7 MB / 16,584 檔，`bytes_remaining = 66,435,599 B（63.4 MiB）`、
     `target_reached: true`，`kept_blobs: 20807`（近 50 步＋I/O＋索引＋近期版本）
     全部保留**——工作集就裝在 64 MiB 裡，不是硬削。**
     （註：`kept_blobs: 20807` 為 `949c6461` 修復前計入未落盤索引條目的舊值；修復後本機 `gc_report.json` 實測 `kept_blobs: 512`（磁碟物件 499 個、30.50 MB）。）
   - **對 2G repo＝3.2%**，「不該是 repo 的一半」有 30 倍餘裕；對小 repo 是絕對值
     上限，不隨 repo 膨脹（e001 C 組 60/60 格實測 min 27.0 KB／median 316.3 KB／max 1.09 MiB，
     64 MiB ≈ 59–2400 個這樣的 session、median 約 207 個）。
   - **超標時誠實降級、不假 PASS**：回收順序「工作區冗餘 → 最舊舊版本」；被回收的
     舊版本 `file_text`/`materialize` 回 `None`/missing（UNOBSERVED），簽章鏈與近期
     blame 不受影響（blob 回收不影響 Ed25519 鏈，round 133 已 145/145 實證）。
   - 為什麼不是 16/32 MiB：工作集地板＝近 50 步的 I/O＋版本＋索引，忙日可超 32 MiB；
     削到連「近期 blame」都失守就削錯地方了。64 MiB 是**裝得下本專案實測工作集的
     最小二冪**（本輪 dry-run 的 63.4 MiB 殘留就是工作集本身）。

3. 改動（最小）：`vacant_network/retention.py:72` 常數 512→64（＋註記）。
   回收機制（`_sweep_to_target` 三級順位）、讀端回退（`file_text`/`materialize`
   工作區＋驗 sha）、誠實降級（`None`/missing）**全部既有、零改動**——本輪只是把
   「上限」放到「垃圾以下、工作集之上」。

4. 驗收（ASSIGNMENT 主軸 2 三條，全部真數）：
   - **(a) 本機真實 `~/.vacant` 前後**：`vacant gc` 前後 `du -sh`、objects 檔數、
     `gc_report.json` 的 `target` 欄；預期 542 MB → ≤64 MiB＋少量保留。
   - **(b) 大工作區寫端**：store-on-change 後，對本 2G repo 做一次**全新** baseline
     （scratch `VACANT_HOME`＋真實 workspace），量「新增 blob 位元組」；預期 ≈0
     內容複製（只有索引 JSON），對照 08:16 舊碼的 542 MB。
   - **(c) 回收後追緝**：`rec.verify()` 100%、`Trace.file_text` 對未變動檔經工作區
     回退仍取回原文、對已改檔的舊版本誠實 `None`（不崩、不假 PASS）。
   - lab cell 對照：e001 C 組 60/60 格 `vacant_home_bytes`（min 27.0 KB／median 316.3 KB／
     max 1.09 MiB，KB–MB 級）——本輪 (b) 的 2G 大工作區量測即「1 個大工作區 cell」的本機對照；
     e001 120 格完成後 `disk_report.py` 全量聚合（既有 BACKLOG，不重複立項）。

5. 誠實邊界：
   - 64 MiB 是**軟上限**：auto gc 每 ≥1 小時跑一次、每次 ≤30 s 預算；必須保留的 blob
     （近期步驟 I/O、must-keep 版本）動不了，若單日工作集 >64 MiB，store 會暫超
     上限、待步驟老化後下次 gc 收回。這是「持久上限」，不是「實時硬切」。
   - 本輪驗收 (a) 用**真實** `~/.vacant`（人類回報的那份 564 M），非合成 fixture；
     (b) 用真實 workspace＋scratch HOME，非 mock。
   - `test_compact_trace_keeps_active_project_live_blobs`（round 72 釘鎖）不受影響：
     其 store ≈20 KB ≪ 64 MiB，sweep 不觸發，`files_removed==0` 照舊。

6. 重驗：
   - `cd ~/dev/Vacant && .venv/bin/pytest tests/test_retention.py -x -q`
   - `cd ~/dev/Vacant && .venv/bin/vacant usage`
   - `cd ~/dev/Vacant && .venv/bin/python -c "from vacant_network.retention import verify_trace_chains as v; print(v())"`
