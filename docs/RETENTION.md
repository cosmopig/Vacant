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

## 使用者機器穩態用量（估算）

- 單專案的佔用 ≈ 該專案被改動過的檔案版本（內容定址去重）＋ 每步索引。
  未改動的檔案雖然**第一次掃描會先複製一份**（這是設計上的快照，
  見下「已知限制」），但之後任一輪 gc 都會把仍在工作區原位、重算吻合的副本清掉。
- 實測（本機 `~/.vacant`，143 個歷史專案）：一次自動 gc 釋放 **743.7 MB / 19,397 檔**
  （2026-10-24 11:42，`gc_report.json`）；之後穩態約 **25 MB**、trace 物件 300 個，
  增量 gc 每輪只清 KB 級。
- 粗估：一個日常專案穩態在 **數 MB 到數十 MB** 級；十個專案同時追緝，
  預算 1 GB 內有餘裕。

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

## 相關檔案與測試

- 實作：`vacant_network/retention.py`（`compact_trace`／`compact_quarantine`／
  `compact_work`／`compact_logs`／`auto_gc`／`usage_report`）
- 自動觸發：`vacant_network/adapters/hook.py:_spawn_auto_gc`
- 測試：`tests/test_retention.py`（11 項：回收與鏈／blame 完好、隔離區、
  一次性工作區、CLI、auto_gc 報告／頻率／鎖／fail-open、預算中斷安全點、
  usage 欄位、掛鉤觸發）
