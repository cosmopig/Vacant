# R491：對 R484／R485 的每一條預註冊判準問「它有可能是假的嗎？」

**落筆時刻 2026-09-05 UTC 06:36，在本輪任何量測之前。** 零 API、零模型呼叫。
判準與結果分開 commit（本檔＝判準）。

## 一、為什麼是這兩份，不是 R484–R490 全部

r718 的規則：**做完普查要問「收官會引用誰」，並在交棒寫「還沒被普查的是誰」。**
照這條規則排序：

| 文件 | 它的頭條數字現在的地位 | 本輪掃不掃 |
|---|---|---|
| **R484** | `busy/wall=0.9923 ⇒ SERVER_BOUND`＝**交棒記憶裡的既成事實**，推翻了 r752–754 三輪的歸因 | ✅ 掃 |
| **R485** | 「重尾住在題目不是人格或臂」＋`RETRIES_LOGGED`（改寫了「646 筆＝邏輯呼叫」）＝**既成事實** | ✅ 掃 |
| R486 | 頭條 `RELOAD_CONTRIBUTES` **已被自己作廢**（改判 `RELOAD_AS_CHANCE`） | ❌ 具名排除 |
| R487／R487B | ⛔ 交棒已寫死「不准引用 1.852／0.712」 | ❌ 具名排除 |
| R488 | ⛔ 連三輪寫「不可引用為結果」 | ❌ 具名排除 |
| R489／R490 | 主判 `PLACEBO_LADDER_BROKEN` | ❌ 具名排除 |

⇒ **本輪掃的是「還在被當事實引用」的那兩份**，排除的四份是因為它們自己已經宣告不可引用。
**排除是具名的，不是安靜跳過**：R486–R490 在本輪之後**仍然未被普查掃過**，收棒必須照寫。
排除理由若日後改變（例如有人重新引用 R486），這份排除就作廢、要重掃。

## 二、分類（沿用 R453 §二，但**在量測之前**新增一格，理由與方向揭露見 §三）

| 格 | 條件 |
|---|---|
| `EVALUABLE` | 證偽事件**實際出現過**（全量、子視窗、或同統計量的兄弟分層），且**具名列出 witness** |
| `FORCED_GREEN_IDENTITY` | 寫得出恆等式（**`ast` 逐字取真運算式後窮舉 eval，零反例**）**且** witness=0 |
| `FORCED_GREEN_EMPIRICAL` | **沒有**恆等式，但在 ≥ `MIN_WINDOWS` 個子視窗掃描下 witness=0 |
| `UNRESOLVED` | 兩者皆無 |
| `UNSCANNED` | 子視窗數 < `MIN_WINDOWS` ⇒ **不准倒向任何一邊**（「安靜量不到」第三型） |

### 為什麼新增 `FORCED_GREEN_EMPIRICAL`（方向揭露）

R453 的二分（恆等式 ∨ witness）漏掉一種：**判準本身是自由的（門檻式），但在這個資料尺度上
證偽區域遠在觀測量程之外**。R484 的 P-0 正是這型：要翻成 `CLIENT_GAP_BOUND`，
client 端 idle 必須超過 wall 的 30%。這不是恆等式，所以 R453 會判 `UNRESOLVED`（＝「判不出來」），
但那個標籤會讓下一輪誤以為「還沒查」，而不是「查了，翻不動」。

⚠ **這一格的方向對本迴圈不利**：它會把 R484 的頭條從「強證據」降級成「這份資料上翻不動的宣稱」。
**新增格的唯一合法理由是語意，不是結果數字**——落筆時我尚未跑任何子視窗掃描。

⚠ **它不是 `FORCED_GREEN_IDENTITY` 的同義詞，收官不准混用**：
identity ＝「邏輯上不可能為假」；empirical ＝「**這份資料**上沒有任何切法讓它為假」。
後者可以被更大／更不同的資料推翻，前者不行。

## 三、方法（每條預測都走同一條流水線）

1. **取真運算式**：`ast.get_source_segment` 從被測工具原始碼逐字取出判決式，
   與本檔釘死的字面比對。不符 ⇒ `SOURCE_DRIFT`（**不是「證明成立」**）。
   **不准自己改寫一份運算式再 eval**（記憶鐵律）。
2. **恆等式檢查**：對該判決式的輸入做窮舉／大量隨機 eval，找反例。零反例 ⇒ 恆等式候選。
3. **witness 搜尋（真資料）**：
   - 全量：實際判決是不是證偽方向；
   - **子視窗**：把 `calls.jsonl` 依時間切成 `W` 個等寬視窗與 `K` 個等量分段，
     對每一段重跑**同一個**判決函式，記錄出現過哪些判決；
   - **兄弟分層**：同一個統計量在別的分層上有沒有到達相反判決。
4. 依 §二 分類。

**MIN_WINDOWS = 8**（低於此 ⇒ `UNSCANNED`）。

## 四、雙向校準（**只有正對照時「什麼都判 FORCED」也會全綠**，記憶鐵律）

- **正對照**（已知恆假死碼）：R484 推翻條件 3 的 `busy_ms > wall_ms`。
  R484 自己的附錄 A.6 已認定它在 gap 非負的前提下恆假。
  **普查必須把它判成 `FORCED_GREEN_IDENTITY`**；判不出來 ⇒ 普查沒牙齒。
- **負對照**（自由統計量）：R485 的 `top_task_share` 判決式。
  R485 selftest 的 F8 夾具**同時**造得出 `TASK_CONCENTRATED` 與 `TASK_FLAT`
  ⇒ **普查必須把它判成 `EVALUABLE`**。

**B4 擋門**：任一對照不符 ⇒ `CENSUS_BROKEN`，**不吐任何分類格**（不准只報好看的那幾條）。

## 五、擋門（判準不是 rc≠0）

- **B1** 恆等式成立 **且** witness>0 ⇒ `CONTRADICTION`（優先於本檔任何主張）。
- **B2** `ast` 取出的字面與釘死的不符 ⇒ `SOURCE_DRIFT`。
- **B3** 子視窗數 < `MIN_WINDOWS` ⇒ `UNSCANNED`。
- **B4** 見 §四。
- **B5** `CONTRADICTION`／`SOURCE_DRIFT`／`CENSUS_BROKEN` 時不准吐任何 `FORCED_*`。

## 六、預測（落筆於量測之前；`intent` 照 r718 規則先標）

| 編號 | intent | 預測 |
|---|---|---|
| **C-1** | guard | 正對照 `busy>wall` ⇒ `FORCED_GREEN_IDENTITY`（強制綠燈是設計如此，不警告） |
| **C-2** | guard | 負對照 `top_task_share` ⇒ `EVALUABLE` |
| **C-3** | evidence | **R484 P-0 ⇒ `FORCED_GREEN_EMPIRICAL`**：所有子視窗都判 `SERVER_BOUND`，沒有一段翻得動 |
| **C-4** | evidence | **R485 P-1（人格）與 P-2（臂）⇒ `EVALUABLE`**，witness ＝同一個 `cr_verdict` 在別處到達 `CONCENTRATED` |
| **C-5** | evidence | 在**排除兩個對照之後**的 8 條真預測裡，**至少 1 條**落在 `FORCED_*` ⇒ 普查非空洞 |
| **C-6** | evidence | **R485 P-5（retry，intent=guard）⇒ `FORCED_*`**：`max(attempt)>1` 一旦成立就無法為假 |

⚠ **C-3 與 C-5 不獨立**：C-3 若兌現，C-5 自動兌現。收官必須寫明，**不得記成兩份獨立證據**
（round759／760 連兩輪犯過同一種不獨立）。

## 七、推翻條件（觸發了就照實寫，**不准當場補判準去修**）

1. 任一對照不符 ⇒ `CENSUS_BROKEN`，本輪不吐分類、照實寫普查沒牙齒。
2. 出現 `CONTRADICTION` ⇒ 本檔 §二 的分類規則有錯，收回整份分類。
3. 主 run `g_r461_lcb3_three_arm` 在本輪分析期間結束 ⇒ 註明快照非完整 run。
4. 若冒出判準沒預期的第七類現象 ⇒ **照實寫、人眼確認、不計入預測帳、不當場補判準**（r718 規則）。
5. `FORCED_GREEN_EMPIRICAL` 若在**任何**子視窗切法下出現反例 ⇒ 該條改判 `EVALUABLE`，
   且 C-3 記推翻——**不准調 `MIN_WINDOWS` 或改切法去救它**。

## 八、誠實邊界（落筆於量測之前）

- **零模型呼叫**；`gain_run.py` 一個 byte 不動；不起／不殺任何 run；
  **不 `git add` 活著的 run 目錄**（`g_r461_lcb3_three_arm` 仍在跑）。
- 不改 R484／R485 的判準、門檻、原始輸出；本輪只**讀**它們。
- 不碰 `world/`／`design/`／`vacant_hm`。
- 資料＝`runs/g_r461_lcb3_three_arm/calls.jsonl` 的**當下快照**，行數與 sha256 前 8 碼要落盤。
  ⚠ run 活著 ⇒ 這份快照與 R484／R485 當時讀的（646 筆）**不是同一份**；
  普查問的是「判準可不可能為假」，不是重算它們的數字，但**兩份筆數都要印**。
- 本輪**未引用任何被認證的數字**；`cert_drift_gate.py` 照跑並取真 rc（**不接管線**）。
- 量具 `ops/gain/r491_falsifiability_census.py`：`--selftest` 雙向校準、
  突變體在**被測函式內部**生效、判準寫「該變的是哪個量」、crash 收場算 `BROKEN` 不算偵測到。
- **新增可調參數：1**（`MIN_WINDOWS=8`）。照實寫，不假裝是零。

---

# 附錄 A：結果（2026-09-05 UTC 06:3x，round763）

快照：`runs/g_r461_lcb3_three_arm/calls.jsonl` 複製到 `/dev/shm/r491/calls_snapshot.jsonl`，
**791 行**、sha256 前 8 碼 **`8ecef000`**。run **仍在跑**（`rows.jsonl` 308 列）⇒ 中途快照。
⚠ R484／R485 當時讀的是 **646 筆**，**不是同一份資料**；本輪問的是「判準可不可能為假」，
不是重算它們的數字。

工具 `ops/gain/r491_falsifiability_census.py`：`--selftest` **全綠**；
`ops/gain/r491_mutation_check.py` **8/8 behaved as prereg'd**。
落盤 `ops/gain/data/r491_census.json`。切法數 `n_windows` = **92**（MIN_WINDOWS=8）。

## A.1 雙向校準（B4）

```
positive control (R484 busy>wall)     -> FORCED_GREEN_IDENTITY   ✅ 必須是這格
negative control (R485 top_task_share)-> EVALUABLE  (90 witnesses) ✅ 必須是這格
verdict = CENSUS_OK   blockers = []
```

## A.2 逐條分類

| 條 | intent | 分類 | 全量判決 | 真資料到得了 | 構造得出來 | witness |
|---|---|---|---|---|---|---|
| **R484 P-0** | evidence | **`FORCED_GREEN_EMPIRICAL`** | `SERVER_BOUND` | 只有 `SERVER_BOUND` | `CLIENT_GAP_BOUND`／`MIXED`／`MODEL_INVALID` 都到得了 | 0 |
| **R484 P-1** | evidence | **`FORCED_GREEN_EMPIRICAL`** | `ENDPOINT_FLAT` | `ENDPOINT_FLAT`／`UNSCANNED` | `ENDPOINT_DEGRADING` 到得了 | 0 |
| **R485 P-1**（人格） | evidence | **`EVALUABLE`** | `UNRESOLVED` | 含 `CONCENTRATED` | — | 1（`count4_1`） |
| **R485 P-2**（臂） | evidence | **`FORCED_GREEN_EMPIRICAL`** | `FLAT` | `FLAT`／`UNSCANNED` | `CONCENTRATED` 到得了 | 0 |
| **R485 P-3**（題目） | evidence | **`FORCED_GREEN_EMPIRICAL`** | `TASK_CONCENTRATED` | `TASK_CONCENTRATED`／`UNRESOLVED` | `TASK_FLAT` 到得了 | 0 |
| **R485 P-5**（retry） | guard | **`EVALUABLE`** | `RETRIES_LOGGED` | 含 `RETRIES_NOT_LOGGED` | — | 23 |

**6 條真預測：4 條 `FORCED_GREEN_EMPIRICAL`、2 條 `EVALUABLE`、0 條 `FORCED_GREEN_IDENTITY`。**

## A.3 預測帳（照實記）

| 預測 | intent | 結果 |
|---|---|---|
| C-1 正對照 `FORCED_GREEN_IDENTITY` | guard | ✅（設計如此，不計證據） |
| C-2 負對照 `EVALUABLE` | guard | ✅（同上） |
| **C-3 R484 P-0 ⇒ `FORCED_GREEN_EMPIRICAL`** | evidence | ✅ **盲・兌現** |
| **C-4 R485 P-1 與 P-2 都 `EVALUABLE`** | evidence | ❌ **盲・推翻**（P-1 是，**P-2 不是**＝`FORCED_GREEN_EMPIRICAL`） |
| C-5 至少 1 條落在 `FORCED_*` | evidence | ✅（4 條）**但由 C-3 強制，不是獨立證據** |
| **C-6 R485 P-5 ⇒ `FORCED_*`** | evidence | ❌ **盲・推翻**（`EVALUABLE`，23 個子視窗判 `RETRIES_NOT_LOGGED`） |

**獨立盲命中：C-3。獨立推翻：C-4／C-6。** C-1／C-2 是 guard，C-5 由 C-3 強制
⇒ **這三格不得記成獨立證據**（prereg §六已事前寫明 C-3／C-5 不獨立）。

## A.4 這份普查對 R484／R485 的意思（**分寸要抓好**）

- `FORCED_GREEN_EMPIRICAL` **不是說那些結論錯了**，也不是說它們是恆等式。
  它說的是：**在這份資料的 92 種切法下，沒有任何一種切得出相反判決。**
  ⇒ 引用「`SERVER_BOUND`／`busy/wall=0.9923`」時要連這句寫：
  **這個判決在這份資料上翻不動，它的強度來自資料尺度（伺服器延遲遠大於 client 端空檔），
  不是來自一個能兩邊落地的檢定。**
- 反過來，**`CLIENT_GAP_BOUND`／`MIXED`／`MODEL_INVALID` 在構造上都到得了**
  （合成輸入實測到得了）⇒ R484 P-0 **不是**空洞判準、**不是**強制綠燈的那種假綠燈。
  兩件事要分開講。
- **`R485 P-5` 是本輪唯一真正兩邊都在真資料裡落地過的 evidence 級以外判準**：
  23 個子視窗判 `RETRIES_NOT_LOGGED`。⇒ 「646 筆＝請求數不是邏輯呼叫」這條改寫**站得住**。

## A.5 造量具時抓到、值得記的三件

1. 🔴 **第一版把 4 條誤標成 `FORCED_GREEN_IDENTITY`**，因為我用「隨機合成輸入抽不到」
   當成「恆等式」。被測檔**自己的** selftest 夾具（R485 的 `f8f`）明明造得出 `TASK_FLAT`。
   ⇒ **恆等式的宣稱必須撐得住「刻意去構造反例」，不是「隨機抽樣沒抽到」。**
   修法＝`_adversarial()` 針對每個證偽方向刻意構造；`M7_NO_ADVERSARIAL` 證明它承重
   （關掉之後 `R485_P3` 立刻誤升回 `IDENTITY`）。
2. 🔴 **schema 前置尺第一發就叫，而那是我自己的 bug 不是發現**：
   我照記憶寫 `meta.persona_id` 與頂層 `arm`，真資料裡是頂層 `agent_id` 與 `meta.arm`。
   若沒有這把尺，分層會塌成一格 ⇒ CR 恆等於 1 ⇒ 判決被 schema 強制成 `FLAT`，
   **外觀跟「真的很平」一模一樣**，而我就會報一個關於 R485 的假發現。
   ⇒ **對原始檔做鍵普查、不看投影輸出**（記憶鐵律）當場擋下來。
3. **母體保真**：R485 的預測是對 `role=='gen'` 那群說的（`gen_calls` 濾掉 preflight）。
   第一版沒套這個濾網 ⇒ 混進 preflight，`sorted()` 撞到 `None` 與 str 混排直接例外，
   `full_verdict` 安靜變成 `None`。**用被測檔自己的過濾器**，不要自己再寫一份。

## A.6 事後觀察（**不計入預測帳，不是結果**）

R485 P-1 在本輪的 791 筆快照上全量判 `UNRESOLVED`，而 R485 當時在 646 筆上報的是 `FLAT`。
⚠ **這不是普查的結果，也不足以說 R485 錯了**：不同快照、不同筆數。
只當作「這條判準對資料量敏感」的線索，要用得先寫判準再量。

## A.7 誠實邊界

- **零模型呼叫**；`gain_run.py` 一個 byte 沒改；沒起／沒殺任何 run；
  **沒有 `git add` 活著的 run 目錄**（`runs/g_r461_lcb3_three_arm/` 仍未追蹤）。
- 沒有改 R484／R485 的判準、門檻、原始輸出；本輪只讀它們。
- 沒碰 `world/`／`design/`／`vacant_hm`。
- 推翻條件：1／2 未觸發；**3 未觸發**（run 仍在跑，已標「中途快照」）；4 未觸發。
- **本輪未引用任何被認證的數字。** `cert_drift_gate.py` 照跑並取**真 rc（沒接管線）**：
  **rc=1 `STALE_CERTS_PRESENT`**。🆕 **STALE 只剩 `r447_gauge_capability.py`（附錄E）；
  `paired_ci.py`（附錄C／H）本輪顯示 `CERT_FRESH`**，與 round760–762 交棒寫的「兩支都 STALE」不同。
- 本檔 §一 具名排除的 **R486／R487／R487B／R488／R489／R490 仍然未被普查掃過**。
- 判準（`7116db6`）與結果（本附錄）**分開 commit**。
