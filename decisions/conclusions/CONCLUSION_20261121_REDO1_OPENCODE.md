# CONCLUSION 2026-11-21 — REDO1_OPENCODE（harness 裡的重開機制 R3 對原生 OpenCode 一次跑到底，gemma-4-12b，1003，polyglot_py 34 題×5）

state＝**EFFECTIVE**，harness_changed_mid_run＝false，harness＝c7c6f5842dbf（auto/redo 主 checkout）。數字來源：[`ops/redo/results/redo1_opencode_REPORT.json`](../../ops/redo/results/redo1_opencode_REPORT.json)。

## 0. 一句話（帶條件）

原生 OpenCode 一次跑到底 79/170、harness 的重開機制 R3 114/170，b=10 c=45，精確 McNemar p≈2e-6；infra_void 0。
**這量的是 redo harness 裡的重開機制套在 OpenCode 上，不是產品指令 `vacant do opencode`**（OpenCode 也沒有載入任何 Vacant 外掛：`~/.config/opencode` 沒有 Vacant 外掛，已查證）。產品指令的真模型數字仍然只有 pi。

## 1. REPORT.md（原樣）

# redo1_opencode_gemma12b_polyglot34 — EFFECTIVE

計畫 sha256 `324c7c1ecd5bbc6e…`　完成 170/170 對（有效 170，infra_void 0）　產生於 2026-11-21T17:02:58Z

| 臂 | 通過／有效格 | 比率 | 平均嘗試數 | 平均 agent 牆鐘 | 逾時次數 | 驗收放行卻錯 | 平均模型呼叫 |
|---|---|---|---|---|---|---|---|
| A | 79/170 | 0.4647 | 1.0 | 221.5s | 0 | 0 | None |
| R3 | 114/170 | 0.6706 | 1.988 | 492.1s | 20 | 0 | None |

**配對（A 對 R3）**：只有對照過 b＝10、只有處理過 c＝45、都過 69、都沒過 46；精確 McNemar 雙尾 p＝2e-06；差 20.59 個百分點；題數上淨正 19／淨負 3。

| rep | 對數 | 對照過 | 處理過 | b | c | p |
|---|---|---|---|---|---|---|
| 1 | 34 | 14 | 22 | 3 | 11 | 0.057373 |
| 2 | 34 | 14 | 19 | 2 | 7 | 0.179688 |
| 3 | 34 | 19 | 24 | 2 | 7 | 0.179688 |
| 4 | 34 | 14 | 26 | 3 | 15 | 0.007538 |
| 5 | 34 | 18 | 23 | 0 | 5 | 0.0625 |

**驗收訊號對評分器（每一次嘗試）**：放行且對 193、放行卻錯 0、擋下卻對 0、擋下且錯 315。

引用規則：只有 state=EFFECTIVE 且 harness_changed_mid_run=false 的整批數字可以引用；引用時要同時講：模型、agent、題庫、對數、等預算的定義、mean_attempts。INCOMPLETE／UNRESOLVED 不是負結果。


## 2. 這個 state 可以說的話（逐字抄自計畫檔 `prereg.states.EFFECTIVE`）

> 170 對全部完成、c > b 且 p < 0.05。可以說：「在這 34 題、OpenCode 1.18.33、gemma-4-12b（1003，llama.cpp 2.73.0）、同樣 1800 秒上限下，測試沒過就重開（最多 3 次）交出通過的成果較多（數字、平均嘗試數一起講）」。不可以說：不帶條件的「Vacant 讓 agent 更好」、外推到別的模型／題庫／沒有可執行測試的工作。這是 harness 裡的機制，不是產品指令的數字。

## 3. 已知限制（逐字抄自 `prereg.known_limits`）

- 等預算是牆鐘的；R3 的模型呼叫數可能比 A 多或少，報告照實列，不當成主張的一部分。
- polyglot_py 的可見測試就是評分器，驗收訊號在這個題庫上是真的；換題庫要先看報告的 signal.accept_fail。
- 34 題在 e001／e002／e016／realrun 都用過：這是同一批題上的確認，不是沒看過的題。
- A 的時限 1800 秒與 e001／e002 相同，但那些批次的格子環境（vlab cell）與本 harness 不同，數字不可併表。
- agent 改成 OpenCode：設定經 OPENCODE_CONFIG_CONTENT 指向 1003 的 LM Studio；XDG_DATA_HOME 指到每格自己的空目錄（工作階段不跨格）。
- usage＝none：呼叫數記 null 不填 0；void 只剩 infra_re 那條，已補 OpenCode 的斷線字樣（2026-11-20 實測：端點關掉時印 `Cannot connect to API: Unable to connect`、rc=1）。
- 手動確認：pg_affine_cipher 一格 320 秒自己結束（rc=0），有寫檔。
- 冒煙 smoke2_opencode_gemma12b（fd5fbc41292c）：4/4 格完成、R3 有重開（attempts=2）；端點關掉的暫時計畫：R3 與 A 都被記成 infra_marker、4 次後 infra_void（不算嘗試）。
- 這 16 題是替 pi＋gemma 挑的；NO-GO 時只能寫「篩選題組是替 pi＋gemma 挑的」，不可寫成「OpenCode 上沒效」。
- 1003 的 llama.cpp 是 2.73.0；與 pi 的批次不併表。
- OpenCode 的呼叫數 harness 量不到（usage=none）：報告的平均模型呼叫為 None；void 只靠 infra_re。
- 數字不與 pi 的批次併表、不合併成一個 p 值。

## 4. 代價

- R3 平均內層嘗試 1.988；逾時 20 次（A 0 次——A 是一次跑到底，1800 秒內都自己結束）。
- 模型呼叫數：OpenCode 的用量 harness 沒有記（兩臂 `mean_model_calls` 都是 None），這批不報呼叫數。
- 驗收訊號：放行且對 193、放行卻錯 0、擋下且錯 315、擋下卻對 0（polyglot_py 的可見測試＝評分器）。

## 5. 中斷與作廢紀錄

- 1003，從 11/20 跑到 11/21 17:02Z；infra_void 0。期間 1003 佇列的舊冒煙批都撤回（#WITHDRAWN），本批照預註冊跑完。

## 6. 同題其他批（只並列，不合併）

| 批 | agent／機制 | 後端 | 原生 | 處理臂 | b | c | p | state |
|---|---|---|---|---|---|---|---|---|
| confirm1 | pi／`vacant do pi`（舊碼＋擴充） | 1003 | 89/170 | 105/170 | 13 | 29 | 0.0195 | EFFECTIVE |
| confirm1c | pi／`vacant do pi`（舊碼＋擴充） | 1004 | 80/170 | 103/170 | 6 | 29 | 0.000117 | EFFECTIVE |
| redo1_opencode（本批） | OpenCode／harness R3 | 1003 | 79/170 | 114/170 | 10 | 45 | ≈2e-6 | EFFECTIVE |

三批的 agent、處理臂（產品指令 vs harness 機制）、機器不同，只並列；不可讀成「`vacant do opencode` 有效」。
