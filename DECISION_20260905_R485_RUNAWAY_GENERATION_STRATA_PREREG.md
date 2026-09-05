# R485 預註冊：失控長生成住在哪一層？（判準寫在量測之前）

日期：2026-09-05 UTC 04:1x　輪次：round756　模型：Opus 5
分支：`feat/v2-four-stages`　落筆時 HEAD：見本 commit 的 parent

## 一、問題（承接 R484 §4，只提出未斷定的那一條）

R484（`fcf4cfd`）量到主 run `runs/g_r461_lcb3_three_arm` 是 `SERVER_BOUND`
（busy/wall = 0.9923），並指出時間變異**不在端點吞吐**（`ms_per_tok` 逐小時中位數
14.3–29.7，判 `ENDPOINT_FLAT`）而在**每次生成多少 token**：
`latency p50 24.8s / p90 80.8s / p99 352.6s / max 600.1s`，
`completion_tokens` 上看 14465／16032，撞 `--request-timeout-s 600` 的有 9 筆，
**最慢 5% 的呼叫吃掉伺服器時間的 30.3%**。

R484 把「gemma-4-12b 在 LCB 題目上偶爾失控長生成」列為**候選**，明說沒斷定。
本輪要答的是它的下一階問題：

> **這條重尾住在哪一層——人格（`agent_id`）、臂（`arm`）、還是題目（`task_id`）？**

**為什麼這是實驗問題不是效能問題**：三臂用的人格池不同（OFF 1 份候選、
OFF5/CONFORM 5 份），如果重尾集中在某個人格，那條臂的**牆鐘成本**被系統性放大，
而它的**邏輯呼叫數**（c/t 的分子）不變 ⇒ 「等預算」在呼叫數上成立、在牆鐘上不成立。
這會影響下一個 run 的 DECISION 怎麼定義預算。

## 二、資料與範圍

- 唯一輸入：`runs/g_r461_lcb3_three_arm/calls.jsonl`（**已落盤**）。
- **零 API 呼叫。不改主 run 的任何參數。不 `git add` 主 run 目錄。**
- 主 run **仍在跑** ⇒ 本輪所有數字是**中途快照**，不是完整 run 的數字。

### 量測前已看過的東西（誠實邊界，避免「照結果挑判準」）

落筆前只做了 schema 普查，**沒有看過任何 latency／token 的分層數字**：

- 647 行、0 行不可解析；鍵普查：`ts_ms/agent_id/role/api/model/model_configured/
  temperature/attempt/ok/timeout_s/retries_max/latency_ms/system/prompt/meta` 各 647，
  `server_model/cost_usd/market_cost_usd/usage/response` 各 636，`error` 11。
- `role`：`gen` 646、`preflight` 1。**本 run 沒有任何 judge／reviewer 角色的 API 呼叫。**
- `agent_id`：plain-2 123、plain-1 117、careful-1 113、hasty-1 108、careful-2 96、hasty-2 89、preflight 1。
- `meta`：`{arm, task_id}`（646 筆）。`timeout_s`：600（646 筆）／120（preflight 1 筆）。
- 已引用 R484 已公開的分佈數字（p50/p90/p99/max、5%→30.3%、9 筆逾時）。

## 三、定義（機制導出，不是從觀測分佈挑的）

- **母體**：`role == "gen"` 的 646 筆（**排除 preflight**，它 `timeout_s` 不同尺）。
- **RUNAWAY**：`latency_ms >= 0.5 * timeout_s * 1000`（≥300 秒）。
  門檻來自**實驗條件**（600s 預算的一半），不是從觀測 p 分位挑的。
- **TIMEOUT_HIT**：`latency_ms >= 0.98 * timeout_s * 1000`（≥588 秒）。
- **集中率** `CR(S) = share_time(S) / share_calls(S)`，
  其中 `share_time(S) = Σ_{S} latency_ms / Σ_{all} latency_ms`、`share_calls(S) = |S| / 646`。
  `CR = 1.0` ＝該層吃的時間與它的呼叫佔比一樣。

## 四、預測（每條含門檻、三分判決、intent）

`intent=evidence` ＝收官會拿來當佐證（強制綠燈要警告）；
`intent=guard` ＝防 infra／防誤讀（強制綠燈是設計如此）。

| 編號 | intent | 判準 | 判決 |
|---|---|---|---|
| **P-1**（人格） | evidence | `max_p CR(p)` 跨 6 個人格 | ≥1.50 ⇒ `PERSONA_CONCENTRATED`；<1.25 ⇒ `PERSONA_FLAT`；否則 `UNRESOLVED` |
| **P-2**（臂） | evidence | `max_a CR(a)` 跨 3 臂 | ≥1.50 ⇒ `ARM_CONCENTRATED`；<1.25 ⇒ `ARM_FLAT`；否則 `UNRESOLVED` |
| **P-3**（題目，**含基準率**） | evidence | `top5_share = ` 依 Σlatency 排序前 5 個 `task_id` 的 `share_time`；均勻虛無下期望 `5/N_tasks` | `top5_share >= 3 * 5/N_tasks` ⇒ `TASK_CONCENTRATED`；`< 1.5 * 5/N_tasks` ⇒ `TASK_FLAT`；否則 `UNRESOLVED` |
| **P-4**（重現性，本輪最有行動力的一條） | evidence | 在「至少有一筆 RUNAWAY」的 task 裡，**RUNAWAY 橫跨 ≥2 個臂**的比例 `f_obs`；虛無＝把 `arm` 標籤在 646 筆上重排（各臂筆數固定）2000 次得 `f_null` 分佈 | `f_obs > p95(f_null)` ⇒ `TASK_INTRINSIC`；`f_obs < p50(f_null)` ⇒ `NOT_TASK_INTRINSIC`；否則 `UNRESOLVED` |
| **P-5**（retry 落不落盤） | guard | `max(attempt)` | `>1` ⇒ `RETRIES_LOGGED`；全 `==1` ⇒ `RETRIES_NOT_LOGGED` |

**P-5 兩個方向的後果都先寫死**（不准看到結果再解釋）：
- `RETRIES_NOT_LOGGED` ⇒ 11 筆失敗之後的重送是**看不見的伺服器時間**，
  它落在 R484 量的「idle gap」裡 ⇒ **R484 的 `busy_frac=0.9923` 是下界**，
  `SERVER_BOUND` 的結論被**加強**而非削弱。
- `RETRIES_LOGGED` ⇒ 646 筆是**請求數**不是邏輯呼叫數 ⇒
  🔴 **交棒記了很久的「646 筆是邏輯呼叫不是請求數」要改寫**，
  且 c/t 的分子在三臂之間可能不同尺，收官要重算。

## 五、推翻條件（觸發就照實寫，不准當場補判準去修）

1. **主 run 在本輪分析期間結束**（`run_complete=True`）⇒「中途快照」的標籤失效 ⇒ 重跑一次並兩份都報。
2. `|Σ_S share_time(S) − 1.0| > 1e-9`（對任一分層）⇒ `BROKEN`，不准報任何 CR。
3. 任一分層出現**筆數 0 的格**而該格本來該有曝光 ⇒ 記 `UNSCANNED`，**不准報成 `FLAT`**
   （「安靜量不到」第三型）。
4. `N_tasks < 20` ⇒ P-3／P-4 的基準率沒有解析度 ⇒ 兩條一律 `UNRESOLVED`。
5. 有 RUNAWAY 的 task 數 `< 5` ⇒ P-4 的 `f_obs` 是 1/n 級雜訊 ⇒ `UNRESOLVED`，
   並附「離邊界／擾動」比值。
6. 本輪若冒出判準沒預期的第七類現象（r718 規則），**照實寫、人眼確認、不計入預測帳、不當場補判準**。

## 六、量具的自我要求（沿用本迴圈已成立的通則）

- `ops/gain/r485_runaway_strata.py`，`--selftest` 雙向校準（正對照＝已知恆假的死碼；
  負對照＝自由統計量），夾具**不共用被測檔的 helper**、不 import 主分析函式。
- 突變體一律在**被測函式內部**生效（不是模組層讀 env），
  判準寫「該變的是哪個量」**不是只寫 rc≠0**，且 crash 收場算 `BROKEN` 不算偵測到。
- 契約常數（本檔的 0.5／0.98／1.50／1.25／3.0／2000）用 `ast` 從被測檔原始碼逐字取出比對。
- **新增可調參數：0**（0.5 與 0.98 由 `timeout_s` 導出，其餘門檻是本檔釘的判決線）。

## 七、本輪不做的事（具名排除）

- 不碰 `gain_run.py`、不碰主 run 的參數（尤其 `--request-timeout-s`，那是 SPEC_GAIN §7 的實驗條件）。
- 不做任何臂間**準確率**比較（`accepted`／`meets_demand` 一個都不讀）——本輪只讀時間與 token。
- 不跑 `cert_drift_gate.py`：本輪不引用任何被認證的數字（引用的 R484 數字在 `fcf4cfd`，
  是**上一輪自己**產的、非認證數字）。
