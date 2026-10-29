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

## 2. 四條驗收條件對現狀

| # | 人類要求 | 現狀 | 證據 |
|---|---|---|---|
| 1 | 用量有上限；2G repo 用一天不能是 repo 的一半 | **有**（分組硬上限，見 §3 目標數字）＋**round 168 起 `vacant usage` 直接量出「總計 vs 封頂百分比＋各組餘量」** | 本輪實測 43.08 MB（r166）→ 52.65 MB（r168，仍在 256 MiB 內 20.57%）；`usage` 明示「在封頂內」＋各組餘量；`test_usage_envelope_gauge`＋fail-open 測試 |
| 2 | 未改動的原位檔不整份複製（記 sha256，需要時回工作區驗 hash） | **有**（10/28 起 scan 不落盤；取不回誠實 UNKNOWN，不崩、不假 PASS） | `workspace.py:156` docstring；`blame.py:837/967`（reclaimed → `unknown`）；測試 `test_gc_rescan_cycle.py:129`、`test_retention.py:203`、`test_trace_rescan.py:122` |
| 3 | 超預算時 GC 刪到預算以下；刪掉的內容回 UNKNOWN 不崩不 PASS | **有**（`_sweep_to_target` + auto_gc 單例鎖/頻率/時間預算，fail-open） | `retention.py:1098`（64 MiB 解析）、`axis2_budget_64mib.md` dry-run 實測；UNKNOWN 語義三測試 |
| 4 | 驗收：(a) 真實 `~/.vacant` 前後數字 (b) lab C 組 `vacant_home_bytes` (c) 回收後 verify/blame | **(a) 有**：10/28 前 542 MB（舊碼複製產物）→ 清場 → 10/29 穩定 43.08 MB（新碼一天生長）。**(b) 有**：e001 C 組 60/60 格 vacant_home_bytes：min 27,611 B（27.0 KB）、median 323,938.0 B（316.3 KB）、max 1,146,648 B（1.09 MiB）、gc_fired 57/60（95.0%）。**(c) 有**：三測試 + axis2_reclaim 實驗 | `axis2_budget_64mib.md`、`axis2_disk.md`、`tests/`（上列） |

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
| **合計** | **168 MiB 硬 + 計數制 + 固定面 → 256 MiB 封頂** | | **52.65 MB（20.57% of 256，round 168 量具實測）** |

**為什麼使用者可以接受 256 MiB**：
1. 它對 2 GiB repo 是 **12.5%**——「不該是 repo 的一半」（50%）有 **4 倍餘裕**。
2. 存的是**證據**不是 repo 副本：scan 已不落盤（§2-2），版本庫大小與「動了多少」成正比、
   與 repo 大小無關。對小 repo 是絕對值，對大 repo 是固定 256 MiB。
3. 每一塊都有**逃生門**：env 覆寫、0＝關、`vacant gc --target-bytes` 單次覆寫。
4. 今天實測 43.08 MB 已在封頂的 17%——不是紙面數字。

## 4. 誠實缺口（不藏）

- **沒有單一「總計」開關**：上限是各分組上限的總和；若某分組漏設上限就能繞過。目前
  主要增長分組（trace/wire/logs/quarantine/work）都有上限或計數制，但「總計封頂」
  本身不是一條程式保證，只是一個可驗算的加總。→ BACKLOG。
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
3. 若 lab 有新 C 組格：把 `vacant_home_bytes` 對 §3 封頂的合規性寫進 report
   （e002 格已有欄位，共用量具零改動）。
