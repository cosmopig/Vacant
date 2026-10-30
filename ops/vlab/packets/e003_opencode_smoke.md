# e003 研究包：OpenCode 真實 agent 冒煙（A/C 4 格配對，預註冊）

> 預註冊：本包在發射前寫死假設、臂、判準。發射後不改判準；要改就開 e003b 並註明。
> 定位：本包是**冒煙 GO/NO-GO**——驗證「OpenCode 能不能在 vlab 格子裡跑」＋「C 臂 Vacant 有無正確掛載並留下 trace 證據」；**不是**成效量測，不產成效結論。
> 量具：`/srv/vlab/bin/report.py`（共用量具，本輪不改動）。

## 0. 背景與假設（ASSIGNMENT 主軸 1：串接真實 agent——pi、OpenCode；真的裝、真的跑、真的看到 Vacant 介入了什麼）

- e001/e002 的 C 臂都在 pi agent 上驗證；**OpenCode 至今沒有預註冊冒煙**。
- 背景事實（已量測、非成效結論）：2026-10-28 跑過 2 格 ad-hoc 探測（`/srv/vlab/done/00_smoke_opencode.json`、
  報告 `/srv/vlab/runs/smoke_opencode/REPORT.{json,md}`）：A/C × pg_pig_latin，0 infra、兩格皆正常結束、pass 皆 0；
  C 臂 `install_rc=0`、留下 `vacant_home.tgz`（15,029 B＝該 tgz 檔 stat 實測大小，含 `.vacant/intake/hooks/events.jsonl`），該次 vacant_sha=dd2c6746（P0-1 修前）。
- 假設（冒煙層，互相獨立）：
  - H-run：OpenCode 能在 vlab 格子環境中完成 polyglot_py 程式任務的**執行流程**——兩臂皆正常結束、無 infra 崩潰；pass/fail 只記錄、不判定。
  - H-mnt：C 臂 `vacant install`（opencode plugin）能在格子 HOME 內正確掛載，並在該格 HOME 留下 trace 證據（收據/事件鏈），不是「裝了但沒記到」。

## 1. 實驗設定（4 格配對）

| 項 | 設定 |
|---|---|
| agent | opencode（真實 agent，非 mini_agent；`opencode run` 下任務） |
| 臂 | `A`（無 Vacant、對照）／`C`（究責：`vacant install`，opencode plugin，交件前對工作區驗收） |
| 任務 | `pg_pig_latin`、`pg_affine_cipher`（`/srv/eval/staged/polyglot_py`，unittest 方言） |
| 設計 | A/C × 2 題 × 1 rep ＝ **4 格**（同題 A/C 配對） |
| 模型 | gemma-4-12b-it-qat（1004 本機，base `http://100.86.226.21:1234/v1`） |
| 超時 | 900 s/格（同 10/28 探測；e001/e002 的 1800 s 是五臂全盤預算，不套到冒煙） |
| C 臂版本 | `vacant_sha = 1ada835b`（與 e002 同版、P0-1 已修；讓 OpenCode 盤與 pi 盤的 C 臂同版本，避免版本成為變數） |
| A 臂 | 不裝 Vacant、不碰 `~/.vacant` |

## 2. 預註冊判準（發射前寫死）

**GO ⇔（四條全成立）**
1. **4 格皆正常結束、無 infra 崩潰**：每格有 `cell.json`（agent 有退出，rc 可非零）、有 `score.json` 且 `pass ∈ {true,false}`；infra（`pass=None` 或無 `score.json`）＝ 0 格。
2. **C 臂（2 格）正確掛載並留下 trace 證據**：`install_rc=0`，且該格 `vacant_home.tgz` 存在、非空、含 `.vacant/intake/hooks/events.jsonl`（Vacant 有真的記錄，不是只裝到 plugin）。
3. **A 臂（2 格）純對照**：該格 HOME 不產生 `~/.vacant` 資料（無掛載）。
4. **無臂專屬機構崩潰**：opencode plugin 載入錯誤、harness 例外等不屬 agent 任務失誤的錯誤＝0 次。

**NO-GO（任一不成立）** ⇒ 不發 OpenCode 全盤；先修機構/臂檔，複測冒煙，綠了再發。

**明言非判準**：通過率、A vs C 差異、成本指標——本包**只作描述**，不進 GO/NO-GO、不引成效結論
（2 題 × 1 rep 不足以支持任何成效主張；「OpenCode 上 Vacant 是否改善結果」屬全盤盤、另包預註冊）。

## 3. 回退與邊界

1. **Fail-open**：Vacant 自身故障（plugin 錯、鏈寫入失敗）不得擋住 agent 交件——使用者任務照常結束、照常打分；
   但「靜默吞掉」（C 臂無任何 trace 證據）落入判準 2 的 NO-GO。
2. **版本**：C 臂釘 1ada835b；換版本重跑＝開 e003b 註明。10/28 探測的 dd2c6746 兩格**不併入**本包分母，只作背景。
3. **模型邊界（H-12 類）**：gemma-4-12b 本地量化；結果不外推到其他模型／預算／任務庫。
4. **磁碟**：4 格 ×（`app_final.tgz`＋`vacant_home.tgz`＋events）量級遠小於 e002 170 格；封頂/GC 政策照 disk_top_priority 不變。
5. **下一步（另包）**：GO ⇒ OpenCode 通用多輪評測盤（對齊 e002 五臂結構、34 題、1800 s/格）另開獨立預註冊封包；本包不含其判準。

## 4. 可複現檔

- 佇列檔（發射時建立，命名沿現況）：`/srv/vlab/queue/05_e003_opencode_smoke.json`（4 格；未 GO 前不入隊）。
- 原始格：`/srv/vlab/runs/e003_opencode_smoke/<suite>-<task>-opencode-<arm>-r1/`（`cell.json`、`score.json`、`events.jsonl`、`app_final.tgz`、C 臂 `vacant_home.tgz`）。
- 背景探測（10/28，只引用不併入）：`/srv/vlab/done/00_smoke_opencode.json`、`/srv/vlab/runs/smoke_opencode/`。
- 判準核對（發射後）：`report.py e003_opencode_smoke` 出 `REPORT.{json,md}`，副本提交本庫 `ops/vlab/runs_e003_opencode_smoke/`。

## 5. 實際結果（2026-10-30，`opencode_cell_audit` 量具審計 4 格）

**GO/NO-GO 判定：GO**（四條預註冊判準全成立；通過率與成本明言非判準，只作描述）。

判準逐條核對（每格 pass 取自各格 `score.json`；成本/呼叫取自 `AUDIT.json`；`REPORT.json` infra=[]）：

1. **4 格皆正常結束、無 infra 崩潰：成立。** 4/4 格有 `cell.json`＋`score.json`（pass ∈ {true,false}）；
   REPORT.json `infra:[]`。pg_affine_cipher A 格 agent_rc=124（牆鐘逾時）但有 score（pass=false）——
   判準容許 rc 非零，非 infra。
2. **C 臂（2 格）正確掛載並留下 trace 證據：成立。** 兩格 `install_rc=0`、`vacant_home.tgz` 非空、
   含 `.vacant/intake/hooks/events.jsonl`；audit 另重算 trace 鏈：affine C 16 筆、pig C 75 筆，
   seq 連續、prev_hash 重算相符（prev_link=ok）；review actions 25/25 與 143/143 全 allow、denied=0。
3. **A 臂（2 格）純對照：成立。** 兩格皆無 `vacant_home.tgz`、install.log 空（無掛載、未產生 ~/.vacant）。
4. **無臂專屬機構崩潰：成立。** audit `bad=[]`、`unknown=[]`；install/agent 日誌無 plugin 載入或例外錯誤。

每格數字（呼叫/token 與 AUDIT.json 一致；pass 為 score.json 原值；成本為描述，非判準）：

| 格 | pass | agent_rc | 模型呼叫 | tokens in/out/total | 工具呼叫 |
|---|---|---|---|---|---|
| pg_affine_cipher A | false | 124 | 12 | 169,702 / 12,591 / 182,293 | 12 |
| pg_affine_cipher C | true | 0 | 13 | 139,083 / 3,627 / 142,710 | 12 |
| pg_pig_latin A | true | 0 | 8 | 69,901 / 3,484 / 73,385 | 7 |
| pg_pig_latin C | false | 0 | 72 | 1,779,788 / 28,492 / 1,808,280 | 71 |
| 合計 | A 1/2、C 1/2 | — | 105 | — / — / 2,206,668 | 102 |

**能說**：OpenCode 在 vlab 格子完成 4 格執行流程（2 過 2 掛；兩臂各 1/2，通過率明言非判準）；
C 臂 Vacant 真的掛載並留下可重算的 trace 證據（events.jsonl、review 168 次全 allow、trace 鏈 91 筆、
prev_hash 重算相符）；A 臂零 Vacant 資料。這是 OpenCode 真實 agent 串接的第 1 組客觀證據。
**不能說**：不能說「Vacant 讓 OpenCode 結果變好／變差」——2 題×1 rep，pass 率與 A/C 差異被本包明言排除；
trace 僅鏈結構完整性重算（H-3/H-4 口徑），未驗簽章、未驗完整性；不外推到其他模型／題庫。

**證據**：`ops/vlab/runs_e003_opencode_smoke/AUDIT.json`＋同目錄 `REPORT.{json,md}`＋
`/srv/vlab/done/04_e003_opencode_smoke.json`（failed_cells=[]）。
