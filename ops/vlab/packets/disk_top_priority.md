# 最優先：~/.vacant 用量上限 —— 四條驗收條件總覽（round 166，2026-10-29）

> 對應 ASSIGNMENT「🔴 最優先」（2026-10-28 人類回報）：「~/.vacant 用量沒有上限……光是
> Vacant 自己的究責資料就快 1G」。本 Packet 把人類列的 4 條驗收條件逐條對現狀、
> 證據、缺口。目標數字與理由在 §3。

## 1. 時序（避免用舊碼的數字論現行碼）

- **10/28 上午**（舊碼，round 139 之前）：首掃全量複製 ≤8MB 檔 → 本 repo 被複製
  **542 MB / 17,097 blob**（`axis2_budget_64mib.md`，已 SHA 驗證 bit 相同於 repo 原檔）。
- **10/28 08:14** 人類清掉 `~/.vacant/trace`（授權動作，備份在 host 1003）。
- **10/28 10:54**（round 139）store-on-change 落地：`workspace.scan` 預設 `store=False`，
  掃描不再複製工作區位元組；只有「被改動那一刻」由 Recorder 存 after 版本
  （`vacant_network/trace/workspace.py:156` docstring，明文）。
- **round 142**：`DEFAULT_TRACE_BUDGET_BYTES` 512 MiB → **64 MiB**；dry-run 實測
  64 MiB 目標下 sweep 回收 469.7 MB / 16,584 檔、`bytes_remaining 63.4 MiB`、
  `target_reached: true`（工作集全保留，不是硬削）。
- **10/29（round 166）**：`vacant usage` 實測總計 **43.08 MB**，trace 物件 **21.95 MB / 553 檔
  < 64 MiB 上限 ✓**；auto_gc 07:00 跑過、釋放 944.4 KB（ok）。
- **10/29（round 168）**：`vacant usage` 上線**穩態封頂量具**（`usage_report().envelope`
  ＋人讀輸出，`--json` 同欄位）；真實 `~/.vacant` 實測 **52.65 MB / 256 MiB（20.57%）✓**，
  trace 32.03/64 MiB、wire body 13.80/96、wire index 1.30/8，各組餘量皆正。
- **10/29（round 178）**：真機 24h 增長序列落地（`ops/vlab/tools/vacant_growth_log.py` 唯讀快照，
  `~/dev/ops/data/vacant_growth.jsonl` 4 筆）：10/28 20:20 **82.3 MiB**（trace 65.0M、objects 821 檔，
  舊日累積峰值）→ 10/29 00:48 **35.2 MiB**（GC 後，trace 17.7M、objects 522、`gc target_reached=true`）
  → 09:32 **51.3 MiB**（trace 34.2M）→ 14:46 **49.7 MiB**（trace 33.9M、objects 750 檔）。
  四筆皆 `gc_last.status=ok、target_reached=true`——「一天長多少」= trace objects 一天長
  16–34 MiB、GC 削回 64 MiB objects 目標下，總量鋸齒在 35–82 MiB、全程 ≤ 256 MiB 封頂的 32%。
  口徑注意：64 MiB 硬上限是 **`trace/objects/` blob 庫存**（`retention.py:130`）；`trace/projects/`
  步索引是計數制（keep 50 步），故 trace 目錄總量可略超 objects 預算（10/28 20:20 快照 65.0 MiB
  = objects＋projects）。e002 C 臂 18/18 格 `vacant_home_bytes` min 35,563 B／median 161,209 B／
  max 290,622 B（≈35–284 KB/格），`envelope_compliance.py` verdict＝PASS（零改共用量具）。
- **10/29（round 176）**：§4 的誠實缺口（「總計封頂只是一個可驗算的加總」）收為**程式可驗不變量**：
  `retention.ENVELOPE_COMPONENTS` 註冊表（每個 `state_dir` top-level 組件都有命名上限：
  `trace` 64 MiB 位元組硬上限、`possess` 96+8 MiB wire 上限、`intake`/`quarantine` 每檔/計數制、
  `adapters`/`gc_*` 固定不增長）＋ `retention.envelope_accounting(root)`（無命名上限的 top-level
  組件 → `unaccounted`，量具不再宣稱「在封頂內」；只報告不刪除，fail-open）＋
  `within_envelope` 新增第三合取項「帳目完整」＋ `test_envelope_byte_caps_sum_within_stable`
  （位元組上限加總 168 MiB ≤ 256 MiB 封頂，封頂不是紙面數字）。真實 `~/.vacant` 實測
  **48.83 MB / 256 MiB（19.08%）✓、unaccounted=[]**。
- **10/29（round 187）**：「從零起算」的跨日序列補齊＋常規量具化。零點＝10/28 08:14
  人工清場（備份 `1003 D:/vlab_backup/vacant_data_20261028_0814.tgz`）；round 186 起 auto gc
  每次真跑自動記 `~/.vacant/growth.jsonl`，與手動快照併排後序列為 10/28 20:20 → 10/29 20:53
  （**24.55h，6 點**）。新量具 `ops/vlab/tools/growth_report.py`（唯讀、上限常數直接 import
  `vacant_network.retention`、證據不足＝UNKNOWN 不假 PASS）真機判定 **verdict=PASS**：
  **24h 視窗最大增長 16.0 MiB**、峰值 82.3 MiB（10/28 20:20 舊日累積、gc 後削至 35.2 MiB）、
  最新 50.7 MiB ≤ 256 MiB 封頂（19.8%）、最新 trace 33.1 MiB ≤ 64 MiB 上限、gc ok＋
  target_reached=true。直答 ASSIGNMENT「量它從零開始一天長多少」：2G repo 全日開發＋
  e002 實驗負載下，一天長 ≤16 MiB、穩態 35–51 MiB 鋸齒、全程 ≤ 封頂 32%。
  `tests/test_vlab_tools.py::test_growth_report_selftest_and_verdict_semantics` 紅綠對照在內。

## 2. 四條驗收條件對現狀

| # | 人類要求 | 現狀 | 證據 |
|---|---|---|---|
| 1 | 用量有上限；2G repo 用一天不能是 repo 的一半 | **有**（分組硬上限，見 §3 目標數字）＋**round 168 起 `vacant usage` 直接量出「總計 vs 封頂百分比＋各組餘量」**＋**round 176 起帳目完整性也是量具的一部分（無命名上限的 top-level 組件會被点名，且不得宣稱「在封頂內」）**＋**round 178 起「一天長多少」有真機 24h 序列（§1 末筆，4 筆 JSONL）** | 本輪實測 43.08 MB（r166）→ 52.65 MB（r168）→ 48.83 MB（r176）→ 49.7 MiB（r178 14:46，均在 256 MiB 內、≤32%）；真機序列峰值 82.3 MiB（10/28 20:20，舊日累積）GC 後 35.2 MiB；`test_usage_envelope_gauge`＋`test_envelope_accounting_*`＋`test_envelope_byte_caps_sum_within_stable`＋fail-open 測試 |
| 2 | 未改動的原位檔不整份複製（記 sha256，需要時回工作區驗 hash） | **有**（10/28 起 scan 不落盤；取不回誠實 UNKNOWN，不崩、不假 PASS） | `workspace.py:156` docstring；`blame.py:837/967`（reclaimed → `unknown`）；測試 `test_gc_rescan_cycle.py:129`、`test_retention.py:203`、`test_trace_rescan.py:122` |
| 3 | 超預算時 GC 刪到預算以下；刪掉的內容回 UNKNOWN 不崩不 PASS | **有**（`_sweep_to_target` + auto_gc 單例鎖/頻率/時間預算，fail-open） | `retention.py:1098`（64 MiB 解析）、`axis2_budget_64mib.md` dry-run 實測；UNKNOWN 語義三測試 |
| 4 | 驗收：(a) 真實 `~/.vacant` 前後數字 (b) lab C 組 `vacant_home_bytes` (c) 回收後 verify/blame | **(a) 有**：10/28 前 542 MB（舊碼複製產物）→ 清場（零點 10/28 08:14）→ 跨日序列 24.55h/6 點 82.3→35.2（GC）→…→50.7 MiB（round 187 `growth_report.py` 真機 verdict=PASS：24h 視窗最大增長 16.0 MiB、全程 ≤256 MiB 封頂 32%、gc ok＋target_reached）。**(b) 有**：e001 C 組 60/60 格 vacant_home_bytes：min 27,611 B（27.0 KB）、median 323,938.0 B（316.3 KB）、max 1,146,648 B（1.09 MiB）、gc_fired 57/60（95.0%）；e002 C 臂 18/18 格 min 35,563／med 161,209／max 290,622 B（envelope_compliance verdict＝PASS）。**(c) 有**：三測試 + axis2_reclaim 實驗 | `axis2_budget_64mib.md`、`axis2_disk.md`、`tests/`（上列＋`test_growth_report_selftest_and_verdict_semantics`）、`~/dev/ops/data/vacant_growth.jsonl`、`~/.vacant/growth.jsonl`、`ops/vlab/tools/{envelope_compliance,growth_report}.py` |

## 3. 目標數字（自訂，附理由）

**`~/.vacant` 穩態上限 ≤ 256 MiB**（一個 2 GiB repo 用一天之後）。組成：

| 分區 | 上限 | 機制 | 本輪實測 |
|---|---|---|---|
| trace 版本庫 | **64 MiB**（硬） | `_sweep_to_target` 刪最舊；`VACANT_TRACE_BUDGET_BYTES` 覆寫、0＝關 | 21.95 MB ✓ |
| wire body | **96 MiB**（硬） | `compact_wire`；`VACANT_WIRE_BODY_BYTES` 覆寫 | 15.10 MB ✓ |
| wire index | **8 MiB**（硬） | `compact_wire`；`VACANT_WIRE_INDEX_BYTES` 覆寫 | （含於 wire）✓ |
| 掛鉤日誌 | 2 MiB/檔 | `compact_logs` 截半，保留最新完整行 | 2.18 MB（intake 合計）✓ |
| quarantine / work | 計數制（每 task 2 決策 / 3 run） | `compact_quarantine`／`compact_work`／`compact_vrun_dir`；單 blob ≤ 8 MiB（MAX_BLOB） | 0 B / 0 B ✓ |
| 固定安裝面（bin/hooks/keys/projects 索引） | ~10 MiB 餘量 | 非增長性 | ~6 MB ✓ |
| **合計** | **168 MiB 硬 + 計數制 + 固定面 → 256 MiB 封頂** | | **49.7 MiB（19.4% of 256，round 178 真機 14:46 實測；24h 峰值 82.3 MiB＝32%）** |

**為什麼使用者可以接受 256 MiB**：
1. 它對 2 GiB repo 是 **12.5%**——「不該是 repo 的一半」（50%）有 **4 倍餘裕**。
2. 存的是**證據**不是 repo 副本：scan 已不落盤（§2-2），版本庫大小與「動了多少」成正比、
   與 repo 大小無關。對小 repo 是絕對值，對大 repo 是固定 256 MiB。
3. 每一塊都有**逃生門**：env 覆寫、0＝關、`vacant gc --target-bytes` 單次覆寫。
4. 今天實測 43.08 MB 已在封頂的 17%——不是紙面數字。

## 4. 誠實缺口（不藏）

- **沒有單一「總計」開關**（round 176 已收一半）：上限是各分組上限的總和；round 176 起
  `retention.ENVELOPE_COMPONENTS` 註冊表要求**每個** `state_dir` top-level 組件都有命名上限
  （位元組硬上限／每檔上限／計數制／固定不增長），無命名上限的組件會被
  `envelope_accounting` 点名為 `unaccounted`、量具不再宣稱「在封頂內」（只報告不刪除）；
  位元組上限分組的加總（168 MiB）≤ 256 MiB 封頂有常規測試把關。
  **仍剩**：`fixed` 類型組件（adapters/gc_* 等固定面）沒有 byte 封頂，靠「不增長」的語義
  保證＋實測（§1 時序）；若未來某 fixed 組件實際增長，需在此表升级为計數制或位元組上限。
- **計數制分組**（50 步索引、2 決策、3 run）在單檔逼近 MAX_BLOB（8 MiB）時可超過
  小預算；有界但沒有 byte 封頂。
- 人類 872 MB 的數字是**舊碼 + 清場前**的；不能用來評現行碼（§1 時序）。
- `retention.py` 模組 docstring 曾長期描述舊行為（「首掃全量複製 ≤8MB」）——
  **人類 10/28 回報引用正是這段過時文字**；本輪已改寫為現行行為（round 166 提交）。
  這正是 GPT_REVIEW P0「文件與程式不同步」的一個實例。

## 5. 下一步（依序，每步一個小提交）

1. ~~Packet + 目標數字 + 文檔修正~~（round 166）
2. ~~`vacant usage` 加一行「總計對 §3 封頂的百分比 + 各分組餘量」~~（round 168：
   `usage_report().envelope`＋人讀輸出；誠實口徑「各分組加總、不是一條單一開關」寫進
   輸出與 JSON `note`；紅燈測試先行、tests/test_retention.py 全綠、真實 `~/.vacant` 實測在內）
   ——把驗收條件 1 變成每次一問的常規量具（小改動）。
3. ~~若 lab 有新 C 組格：把 `vacant_home_bytes` 對 §3 封頂的合規性寫進 report~~（round 178 完成：
   `ops/vlab/tools/envelope_compliance.py`，e001 60/60＋e002 18/18 verdict＝PASS，共用量具
   cell.py/labd.py/report.py 零改動；每輪 e002 監測固定跑）
4. ~~`vacant_growth.jsonl` 隔天再記一筆，補齊「從零起算」的跨日序列~~（round 187 完成：
   序列 24.55h/6 點、`growth_report.py` 真機 verdict=PASS，見 §1 round 187 筆）。
   **仍待**：e002 C/H/M/S 臂完成時重跑 `report.py --rescore`＋`e002_wiring_gauge.py`＋
   `envelope_compliance.py`＋`p02_carm_audit.py` 四量具並把最終 C 臂 `vacant_home_bytes` 分佈
   回寫 §2-4(b)（round 187 監測：A/C 已完成、H 進行中、M/S 待排；四量具對已完成臂 rc=0）。
