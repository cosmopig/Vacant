# 磁碟治理：保留政策與自動回收（`vacant gc` / `vacant usage`）

Vacant 的三個承重路徑（追緝版本庫、收件隔離區、一次性工作區）都會在磁碟上留下
與專案等大的副本。這頁說明它**自己**怎麼把用量管住——零設定、自動觸發、
簽章鏈不受影響、被清掉的舊版本會誠實變「看不到」，而不是假裝還看得到。

## 零設定：裝完就有上限，不用人手跑

- **自動觸發**：agent 掛鉤在**工作階段結束／每回合結束**（stop / session_end）時，
  在背景離程啟動 `vacant gc --auto`（`adapters/hook.py:_spawn_auto_gc`）。
  掛鉤不等它跑完，agent 完全不被阻塞。
- **單例**：`$VACANT_HOME/gc.lock` 用 `fcntl.flock` 非阻塞取鎖；持鎖行程死掉時
  OS 自動釋放，不會留死鎖。多端同時觸發收斂成一次真跑。
- **頻率限制**：同一台機器至多每小時真跑一次（`gc_last.json`）。
- **時間預算**：一次自動 gc 最多佔 30 秒，在下一個迴圈邊界停下；
  已刪的都不是簽章鏈引用的 blob，中途停下也是安全點。
- **失敗放行**：任何例外只寫進 `gc_report.json`，不拋、不阻（掛鉤路徑永遠放行）。
- 人可以手動跑：`vacant gc`（預覽：`vacant gc --dry-run`）、
  `vacant usage`（看用量）。測試／特殊環境可用 `VACANT_HOOK_NO_GC=1` 關掉自動觸發。

## 預設政策（寫死的常數，`vacant_network/retention.py`）

| 常數 | 預設 | 意思 |
|---|---|---|
| `DEFAULT_KEEP_STEPS` | 50 | 每專案保留最近 50 步的**全部**索引與修改版本 |
| `DEFAULT_KEEP_RUNS` | 3 | `~/.vacant-work` 每任務保留最近 3 次執行 |
| `DEFAULT_KEEP_SET_ASIDE` | 3 | 每專案保留最近 3 份 `chain.set-aside.*.ndjson` |
| `DEFAULT_KEEP_DECISIONS` | 2 | 收件帳本保留最新 2 份接受／放行／待審裁決引用的物件 |
| `DEFAULT_MAX_LOG_BYTES` | 2 MB | hooks 追加日誌超過 2 MB 時截斷 |
| `DEFAULT_ACTIVE_WINDOW_S` | 7 天 | 活躍窗口：鏈活動在窗口內的專案視為「活躍」，其未變動背景 blob 保留（見「穩態用量」） |
| `AUTO_GC_MIN_INTERVAL_S` | 3600 s | 自動 gc 頻率限制 |
| `AUTO_GC_BUDGET_S` | 30 s | 自動 gc 時間預算 |

**永不刪除**：`chain.ndjson`、`head.json`、`ledger.ndjson`、`receipts_*.ndjson`
（簽章鏈與帳本本身）、被現用索引／保留集合引用的 blob、最近 50 步的全部狀態。

**回收順序**：未改動且仍在工作區原位、SHA-256 重算吻合的純重複副本 →
過期的 set-aside 鏈 → 未被帳本裁決引用的隔離候選 → 舊的一次性工作區 → 過大日誌。

## 被清掉的版本變成什麼

- 簽章**照樣驗得過**：`chain.ndjson` 簽的是內容摘要，gc 只動 `objects/` 裡的
  副本。`vacant gc --verify` 會在清理後對全部專案的簽章鏈驗章。
- 還看得到：未改動過、且檔案還在工作區原位的，`Trace.file_text`／`materialize`
  直接從工作區讀取並核對 SHA-256。
- 真看不到（舊中間版本已被清、且工作區原檔後來又被改寫）：`Trace` 誠實標記
  該狀態 `unreadable`，`blame` 回 **`UNOBSERVED`（gap／unattributable）**，
  說明「N 個記錄在案的工作區狀態已無法重建」——**不報錯崩潰、絕不當作 PASS、
  絕不栽給別的步驟**。看不到的東西結論是 UNKNOWN，不是 PASS、也不是「沒有」。

## 看得到用量

`vacant usage`：狀態目錄／工作區總量、分區（trace objects／projects、intake、
quarantine、possess、adapters）、每專案占用與步數、物件前 10、**可回收估算**
（dry-run 走完整 gc 邏輯、不取鎖不計頻）、上次自動 gc 的結果。

## 穩態用量（使用者機器）

「未變動背景 blob」能不能回收，取決於**專案是否活躍**
（`DEFAULT_ACTIVE_WINDOW_S`，預設 7 天）：

- **活躍專案**（鏈活動在窗口內）：除最近 50 步、所有被改動版本與目前索引外，
  **未變動的背景 blob（原檔快照）按設計保留**——那正是該檔下一次被修改時所需的
  **before 版本**；回收它只會買回「下一次掃描如數重存」（round 72 設計決定，
  gc↔rescan whack-a-mole；可執行證據：`tests/test_retention.py::test_compact_trace_keeps_active_project_live_blobs`）。
  ⇒ 活躍專案穩態 ≈ **該專案 ≤8 MB 檔案的快照總量**＋最近 50 步的被改版本＋每步索引。
  工作區越大佔用越大——這是「原檔被刪掉仍可讀」保證的設計成本，不是洩漏；
  佔用量受工作區規模限界，不隨輪次無界增長。
- **非活躍專案**（超過 7 天無活動）：未變動背景 blob 被回收，
  只留鏈、目前索引與保留集合內的被改版本——MB 級以下
  （`tests/test_retention.py::test_compact_trace_reclaims_untouched_blobs_and_preserves_chain_and_blame`，
  以 `active_window_s=0.0` 模擬非活躍）。

實測（本機 `~/.vacant`，`vacant usage`）：

- 2026-10-24（活躍保留政策落地前）：一次自動 gc 釋放 743.7 MB / 19,397 檔
  （`gc_report.json`）；當時穩態約 25 MB / 300 個 trace 物件
  （當時活躍專案的快照也會被回收，故數字小）。
- 2026-10-27（活躍保留政策下）：總計 788.03 MB，其中活躍開發專案（6007 步）佔約
  760 MB / 21,030 個物件，其餘 142 個歷史專案合計僅約 11 MB；當輪政策下「可回收（估算）」
  只有 469.1 KB——佔用的主體是活躍專案的 live 快照，**屬政策保留、非待清理**。
  自動 gc 同日正常執行（05:04，釋放 1.09 MB，status ok）；
  `vacant gc --verify`：143 個專案簽章鏈全數通過。

## 已知限制（誠實邊界）

1. **不是備份**。被清掉的舊中間版本無法再用 `materialize` 還原當時內容；
   那一步的簽章與寫入清單（路徑＋前後 sha256）仍在 `chain.ndjson`。
2. **寫入端先複製後清理**：`workspace.scan` 第一次掃描仍會把專案每個 ≤8 MB 的檔案
   複製進 `trace/objects/`（快照讓「檔案之後被刪／被改」也能追溯）；冗餘副本靠
   gc 清。這是「先全量快照、後依政策回收」，不是「只存被改動的檔」。
   改寫入端成增量快照會犧牲「原檔被刪後仍可读」的保證，現階段不取。
3. **自動 gc 是背景且有限**：30 秒預算內清不完就停在安全點下輪再清
   （`status="ok_partial"`），極大的狀態目錄需要人手 `vacant gc`（可加大 `--budget-s`）。
4. 沙箱與簽章鏈的安全性與磁碟用量無關：gc 不引入新的信任假設，
   也不降低 H-3／H-4 的既有邊界。
5. **活躍專案佔用 ∝ 工作區大小**：只要專案活躍（7 天內有鏈活動），其 ≤8 MB 檔案快照就保留；
   多 GB 級開發工作區會讓 `trace/objects/` 佔據數百 MB（2026-10-27 實測總計 788.03 MB，
   見「穩態用量」）。專案 7 天不活躍後自動收縮到最小。**目前沒有 CLI 開關可以回收活躍專案的
   live 快照**（`vacant gc --aggressive` 只縮短保留步數，不改活躍窗口——`gc_all()` 呼叫
   `compact_trace()` 時未傳 `active_window_s`，恆為預設 7 天）；只有 API
   `retention.compact_trace(active_window_s=0.0)` 能做到。逃生門開關已列 BACKLOG。
   注意這是**設計成本**（避免 gc↔rescan whack-a-mole），不是洩漏：佔用量受工作區規模限界。

## 相關檔案與測試

- 實作：`vacant_network/retention.py`（`compact_trace`／`compact_quarantine`／
  `compact_work`／`compact_logs`／`auto_gc`／`usage_report`）
- 自動觸發：`vacant_network/adapters/hook.py:_spawn_auto_gc`
- 測試：`tests/test_retention.py`（11 項：回收與鏈／blame 完好、隔離區、
  一次性工作區、CLI、auto_gc 報告／頻率／鎖／fail-open、預算中斷安全點、
  usage 欄位、掛鉤觸發）
