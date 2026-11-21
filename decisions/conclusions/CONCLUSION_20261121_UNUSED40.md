# CONCLUSION 2026-11-21 — UNUSED40（`vacant do pi` rc1 對原生 pi，gemma-4-12b，1004，沒用過的 exercism 40 題×5，jobs 1）

state＝**EFFECTIVE**，harness_changed_mid_run＝false，harness＝c7c6f5842dbf（auto/redo 主 checkout）。數字來源：[`ops/redo/results/unused40_REPORT.json`](../../ops/redo/results/unused40_REPORT.json)。
這批與 confirm1／confirm1c、hardpy26、W3-5 各自判 state，**不併表、不合併 p 值**；同一天結案的 hardpy26（UNRESOLVED）與 W3-5 Python（UNRESOLVED）見各自的結論檔，不可只挑這批單講。

## 0. 一句話（帶條件）

原生 pi 在這 40 題上本來就過 92%（184/200）；`vacant do pi`（rc1）過 96%（192/200），差 4 個百分點、b=1 c=9、p=0.0215。
淨增益集中在 **5 題**（ex_crypto_square +2、ex_hexadecimal +2、ex_state_of_tic_tac_toe +2、ex_resistor_color_expert +1、ex_swift_scheduling +1），
其餘 35 題兩臂相同或互相抵銷（ex_rectangles 各 4/5）。這是一批接近天花板的題上的小幅、但達到預註冊門檻的差距，不是大效果。

## 1. REPORT.md（原樣）

# unused40_vacantdo_rc1_pi_gemma12b_1004 — EFFECTIVE

計畫 sha256 `a70735a137264ce6…`　完成 200/200 對（有效 200，infra_void 0）　產生於 2026-11-21T12:36:28Z

| 臂 | 通過／有效格 | 比率 | 平均嘗試數 | 平均 agent 牆鐘 | 逾時次數 | 驗收放行卻錯 | 平均模型呼叫 |
|---|---|---|---|---|---|---|---|
| A | 184/200 | 0.92 | 1.0 | 84.4s | 3 | 0 | 12.7 |
| P | 192/200 | 0.96 | 1.0 | 90.6s | 0 | 0 | None |

**配對（A 對 P）**：只有對照過 b＝1、只有處理過 c＝9、都過 183、都沒過 7；精確 McNemar 雙尾 p＝0.021484；差 4.0 個百分點；題數上淨正 5／淨負 0。

| rep | 對數 | 對照過 | 處理過 | b | c | p |
|---|---|---|---|---|---|---|
| 1 | 40 | 37 | 38 | 0 | 1 | 1.0 |
| 2 | 40 | 36 | 39 | 0 | 3 | 0.25 |
| 3 | 40 | 37 | 38 | 1 | 2 | 1.0 |
| 4 | 40 | 36 | 38 | 0 | 2 | 0.5 |
| 5 | 40 | 38 | 39 | 0 | 1 | 1.0 |

**驗收訊號對評分器（每一次嘗試）**：放行且對 376、放行卻錯 0、擋下卻對 0、擋下且錯 24。

引用規則：只有 state=EFFECTIVE 且 harness_changed_mid_run=false 的整批數字可以引用；引用時要同時講：模型、agent、題庫、對數、等預算的定義、mean_attempts。INCOMPLETE／UNRESOLVED 不是負結果。


## 2. 這個 state 可以說的話（逐字抄自計畫檔 `prereg.states.EFFECTIVE`）

> 200 對全部完成、c > b 且 p < 0.05。可以說：「在這 40 題沒用過的 Python 題（exercism，事先固定規則選出）、pi、gemma-4-12b（1004，llama.cpp 2.46.0）、同樣 1800 秒上限下，發布候選版 `vacant do pi`（零設定重開；pi 不載入任何 Vacant 擴充）交出通過的成果，比原生 pi 一次跑到底多（數字、P 的內層平均嘗試數一起講）」。不可以說：不帶條件的「Vacant 讓 agent 更好」、外推到別的模型／語言／沒有可執行測試的工作。

照計畫要求一起講的數字：P 的內層平均嘗試數 **1.125**（見 §4）。

## 3. 已知限制（逐字抄自 `prereg.known_limits`）

- 與 confirm1 的差別：P 臂的 pi 用 harness 的乾淨設定目錄（PI_CODING_AGENT_DIR），不載入 `~/.pi/agent` 的 Vacant 擴充——量的是重開模式本身；P 臂用 rc1 獨立 venv（~/dev/ops/rc1_venv，3eed78fed），不受主 checkout 合併影響。
- exercism 的測試是 unittest.TestCase，P 臂走的是 rc1 的 python_unittest 驗收路徑（與 confirm1 量的同一條）。
- 等預算是牆鐘的；P 的模型呼叫數 harness 量不到（usage=none），結案用 ops/redo/analysis/p_model_calls.py 補算（UNKNOWN 照列）。
- P 臂的內層嘗試沒有 harness 的 infra 重試；這個不對稱只會壓低 P。
- 跑在 1004（llama.cpp 2.46.0、jobs 1，與 redo1／confirm1c 同一台）；數字不與 1003 或 Colab 的批次併表。

另外（結案時補，不改計畫）：
- 原生臂 92%、在天花板附近：絕對差距只有 4 個百分點，來自 5 題；不能把它說成「在沒看過的題上大幅提升」。
- P 臂是 rc1（3eed78fed，~/dev/ops/rc1_venv），**不是要發布的 0.9.2 wheel**；發布 wheel 的數字看 confirm2（1004）／confirm2c（Colab）。

## 4. 代價

- A：平均模型呼叫 12.7（harness 量）、平均 agent 牆鐘 84.4s、逾時 3 次。
- P：harness 量不到（usage=none）；`ops/redo/analysis/p_model_calls.py` 補算：200 格可算 **200**、UNKNOWN 0；可算的格平均模型呼叫 **13.3**（中位數 7.0）、平均內層嘗試 **1.125**；平均 agent 牆鐘 90.6s、逾時 0 次。
- 這批的 P 幾乎都是一次就過（內層嘗試 1.125），模型呼叫數與 A 相當（13.3 對 12.7）——和 confirm1c（P 62.0 對 A 38.3）不同，這批的增益沒有用多很多算力去換。

## 5. 中斷與作廢紀錄

- 00:32:38Z 發射、10:23:05Z 結束，中間沒有停批；infra_void 0。
- Colab 上的保險批在 0 次模型呼叫時撤回，撤回時看過本機前 13 格的早期結果（措辭已更正），見 `ops/redo/plans/unused40_vacantdo_rc1_pi_gemma12b_colab.WITHDRAWN.md`。

## 6. 同日結案的其他批（只並列，不合併）

| 批 | 後端／harness | P 是哪版 | 題 | A | P | b | c | p | state |
|---|---|---|---|---|---|---|---|---|---|
| unused40（本批） | 1004 llama.cpp／c7c6f584 | rc1 | exercism 沒用過 40×5 | 184/200 | 192/200 | 1 | 9 | 0.0215 | EFFECTIVE |
| hardpy26 | Colab L4 vLLM／3c741397 | rc3 | 難 Python 26×5 | 114/130 | 116/130 | 3 | 5 | 0.73 | UNRESOLVED |
| W3-5 Python | Colab L4 vLLM／3c741397 | rc4 | 篩選入選 9×5 | 27/45 | 25/45 | 6 | 4 | 0.75 | UNRESOLVED |

三批的題、後端、產品版本都不同，這張表只是讓讀者看到同一天的全部結果，不構成合併的估計。
