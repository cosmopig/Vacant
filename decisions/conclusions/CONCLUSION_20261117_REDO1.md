# CONCLUSION 2026-11-17 — REDO1（pi＋gemma-4-12b-it-qat，polyglot_py 34 題×5）

state＝**EFFECTIVE**，harness_changed_mid_run＝false（harness c7c6f5842dbf 從頭到尾沒變）。數字來源：[`ops/redo/results/redo1_REPORT.json`](../../ops/redo/results/redo1_REPORT.json)。

## 1. REPORT.md（原樣）

### redo1_pi_gemma12b_polyglot34 — EFFECTIVE

計畫 sha256 `f95f90d86b779fa3…`　完成 170/170 對（有效 168，infra_void 2）　產生於 2026-11-17T10:50:51Z

| 臂 | 通過／有效格 | 比率 | 平均嘗試數 | 平均 agent 牆鐘 | 逾時次數 | 驗收放行卻錯 | 平均模型呼叫 |
|---|---|---|---|---|---|---|---|
| A | 84/170 | 0.4941 | 1.0 | 436.0s | 12 | 0 | 30.5 |
| R3 | 113/168 | 0.6726 | 1.935 | 703.9s | 101 | 0 | 61.9 |

**配對（A 對 R3）**：只有對照過 b＝7、只有處理過 c＝36、都過 77、都沒過 48；精確 McNemar 雙尾 p＝9e-06；差 17.26 個百分點；題數上淨正 19／淨負 2。

| rep | 對數 | 對照過 | 處理過 | b | c | p |
|---|---|---|---|---|---|---|
| 1 | 33 | 20 | 21 | 3 | 4 | 1.0 |
| 2 | 34 | 16 | 23 | 1 | 8 | 0.039062 |
| 3 | 33 | 14 | 26 | 0 | 12 | 0.000488 |
| 4 | 34 | 18 | 25 | 0 | 7 | 0.015625 |
| 5 | 34 | 16 | 18 | 3 | 5 | 0.726562 |

**驗收訊號對評分器（每一次嘗試）**：放行且對 197、放行卻錯 0、擋下卻對 0、擋下且錯 301。

引用規則：只有 state=EFFECTIVE 且 harness_changed_mid_run=false 的整批數字可以引用；引用時要同時講：模型、agent、題庫、對數、等預算的定義、mean_attempts。INCOMPLETE／UNRESOLVED 不是負結果。

⚠ 有嘗試以模型錯誤結束、但沒被歸成基礎設施失敗（照常計入分母）。看原文決定是不是該歸成 void：`{"A": {"Model reloaded.": 12}, "R3": {"Model reloaded.": 15, "got exception: bad allocation": 1}}`

## 2. 這個 state 可以說的話（逐字抄自計畫檔 `prereg.states.EFFECTIVE`）

> 170 對全部完成、c > b 且 p < 0.05。可以說：「在這 34 題、pi、gemma-4-12b、同樣 1800 秒上限下，測試沒過就重開（最多 3 次）交出通過的成果較多（數字、平均嘗試數一起講）」。不可以說：不帶條件的「Vacant 讓 agent 更好」、外推到別的模型／題庫／沒有可執行測試的工作。這是 harness 裡的機制，不是產品指令的數字。

## 3. 已知限制（逐字抄自 `prereg.known_limits`）

- 等預算是牆鐘的；R3 的模型呼叫數可能比 A 多或少，報告照實列，不當成主張的一部分。
- polyglot_py 的可見測試就是評分器，驗收訊號在這個題庫上是真的；換題庫要先看報告的 signal.accept_fail。
- 34 題在 e001／e002／e016／realrun 都用過：這是同一批題上的確認，不是沒看過的題。
- A 的時限 1800 秒與 e001／e002 相同，但那些批次的格子環境（vlab cell）與本 harness 不同，數字不可併表。

## 4. 代價（抄自 `per_arm`）

| 臂 | mean_model_calls | mean_attempts | mean_agent_wall_s |
|---|---|---|---|
| A | 30.5 | 1.0 | 436.0 |
| R3 | 61.9 | 1.935 | 703.9 |

R3 的模型呼叫數與 agent 牆鐘都比 A 多（見上表；牆鐘上限兩臂相同）。這一層換到的是交付率，不是省算力。

## 5. infra_void 與處理紀錄

- `pg_transpose/r1`：R3 臂 `void×4:model_died_mid_run`（2026-11-14T22:02:33Z），整對不計。
- `pg_connect/r3`：R3 臂 `void×4:infra_marker`（2026-11-16T00:18:38Z），整對不計。
- `pg_bottle_song/r1/A`、`pg_list_ops/r5/R3`：harness 例外 `OSError(117, 'Structure needs cleaning')`（本機 `/tmp` 檔案系統錯誤），當時沒有 cell.json。2026-11-17T10:22Z 以同一份計畫、同一個 harness 續跑（`--only-tasks`，TMPDIR 改到沒壞的磁區），兩格重做完成；這是 redo.py 設計上的續跑，不是改條件。
- 報告 ⚠ 列的 `Model reloaded.`（A 12、R3 15）與 `bad allocation`（R3 1）照計畫的 void 規則**計入分母**，未事後改判。1004 的 LM Studio 當時設 1 小時 TTL，可能是重載來源；之後的批次要先關 TTL。
