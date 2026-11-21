# CONCLUSION 2026-11-21 — CONFIRM1C（`vacant do pi` 對原生 pi，gemma-4-12b，1004，polyglot_py 34 題×5，jobs 1）

state＝**EFFECTIVE**，harness_changed_mid_run＝false。數字來源：[`ops/redo/results/confirm1c_REPORT.json`](../../ops/redo/results/confirm1c_REPORT.json)。
這是 confirm1（1003）在另一台機器、另一版推論引擎上的**獨立複製**；兩批不併表、不合併 p 值。

## 1. REPORT.md（原樣）

# confirm1c_vacantdo_pi_gemma12b_1004_j1 — EFFECTIVE

計畫 sha256 `bba27ed549b885bf…`　完成 170/170 對（有效 170，infra_void 0）　產生於 2026-11-20T22:04:09Z

| 臂 | 通過／有效格 | 比率 | 平均嘗試數 | 平均 agent 牆鐘 | 逾時次數 | 驗收放行卻錯 | 平均模型呼叫 |
|---|---|---|---|---|---|---|---|
| A | 80/170 | 0.4706 | 1.0 | 516.5s | 19 | 0 | 38.3 |
| P | 103/170 | 0.6059 | 1.0 | 735.7s | 1 | 0 | None |

**配對（A 對 P）**：只有對照過 b＝6、只有處理過 c＝29、都過 74、都沒過 61；精確 McNemar 雙尾 p＝0.000117；差 13.53 個百分點；題數上淨正 13／淨負 1。

| rep | 對數 | 對照過 | 處理過 | b | c | p |
|---|---|---|---|---|---|---|
| 1 | 34 | 18 | 20 | 2 | 4 | 0.6875 |
| 2 | 34 | 15 | 21 | 1 | 7 | 0.070312 |
| 3 | 34 | 16 | 21 | 2 | 7 | 0.179688 |
| 4 | 34 | 16 | 20 | 1 | 5 | 0.21875 |
| 5 | 34 | 15 | 21 | 0 | 6 | 0.03125 |

**驗收訊號對評分器（每一次嘗試）**：放行且對 183、放行卻錯 0、擋下卻對 0、擋下且錯 157。

引用規則：只有 state=EFFECTIVE 且 harness_changed_mid_run=false 的整批數字可以引用；引用時要同時講：模型、agent、題庫、對數、等預算的定義、mean_attempts。INCOMPLETE／UNRESOLVED 不是負結果。

⚠ 有嘗試以模型錯誤結束、但沒被歸成基礎設施失敗（照常計入分母）。看原文決定是不是該歸成 void：`{"A": {"Context size has been exceeded.": 1}}`


## 2. 這個 state 可以說的話（逐字抄自計畫檔 `prereg.states.EFFECTIVE`）

> 170 對全部完成、c > b 且 p < 0.05。可以說：「在這 34 題、pi、gemma-4-12b（1004，llama.cpp 2.46.0）、同樣 1800 秒上限下，用產品指令 `vacant do pi`（零設定重開模式，本機已安裝 Vacant 的 pi 擴充）交出通過的成果，比原生 pi 一次跑到底多（數字、P 的內層平均嘗試數一起講）」。不可以說：不帶條件的「Vacant 讓 agent 更好」、外推到別的模型／題庫／沒有可執行測試的工作；也不能把增益單獨歸給重開或單獨歸給 hook（兩者在 P 臂裡同時存在）。

## 3. 已知限制（逐字抄自 `prereg.known_limits`）

- 等預算是牆鐘的；R3 的模型呼叫數可能比 A 多或少，報告照實列，不當成主張的一部分。
- polyglot_py 的可見測試就是評分器，驗收訊號在這個題庫上是真的；換題庫要先看報告的 signal.accept_fail。
- 34 題在 e001／e002／e016／realrun 都用過：這是同一批題上的確認，不是沒看過的題。
- A 的時限 1800 秒與 e001／e002 相同，但那些批次的格子環境（vlab cell）與本 harness 不同，數字不可併表。
- P 臂的 pi 讀使用者自己的 ~/.pi/agent（含 `vacant install` 裝的 extensions/vacant.ts 與壓縮設定），A 臂是 harness 的乾淨設定目錄：比的是「沒裝 Vacant 的原生 pi」對「裝了 Vacant、打 `vacant do pi`」。screen16p4 的 P 日誌裡 hook 沒有注入過任何訊息。
- P 臂的內層嘗試沒有 harness 的 infra 重試（模型崩潰會吃掉一次嘗試），A 臂有；這個不對稱只會壓低 P。
- P 的模型呼叫數 harness 量不到（usage=none），結案時從 {logs}/vacant-work 的 pi 日誌補算。
- 跑在 1004（llama.cpp 2.46.0，與 redo1 同一台、同一個引擎），但 P 臂與 A 臂的定義與 confirm1 相同；1004 的 gemma 與實驗室助手共用。

勘誤（不改計畫）：計畫的 question 文字寫 1003，實際端點是 1004（`lms1004nothink`），見 `ops/redo/results/void/confirm1b/VOID.md`。

## 4. 代價

- A：平均模型呼叫 38.3、逾時 19 次（`per_arm`）。
- P：harness 量不到（usage=none）；`ops/redo/analysis/p_model_calls.py` 補算：170 格可算 169、UNKNOWN 1（`pg_forth/r2/P`：沒有 restart result.json），可算的格平均 **62.0** 次（中位數 36）、平均內層嘗試 1.941；逾時 1 次。
- 和 confirm1 一樣：換到的是交付率，不是省算力，P 的模型呼叫多於 A。

## 5. 敏感度分析（事後、非預註冊；主結論以 §1 為準）

jobs 1，但任一臂日誌出現 `Context size has been exceeded` 的對有 2 對：`pg_forth/r2`（P 側）、`pg_rest_api/r2`（A 側），兩對都是 A／P 皆沒過。
拿掉這 2 對：168 對、b=6、c=29、p=0.000117（與全部 170 對相同）。結論不變。

## 6. 中斷與作廢紀錄

- 2026-11-19 03:48:27Z–14:13:33Z 停批（本機 ext4 錯誤，重開機 fsck）；SIGTERM 停、同計畫同 harness 續跑，中斷那格整格重做。
- 前身 confirm1b（1004 jobs 2，bad allocation）作廢，見 `ops/redo/results/void/confirm1b/VOID.md`，不進任何結論。

## 7. 兩台合看（只並列，不合併）

| 批 | 機器／引擎 | A | P | b | c | p |
|---|---|---|---|---|---|---|
| confirm1 | 1003／llama.cpp 2.73.0 | 89/170 | 105/170 | 13 | 29 | 0.0195 |
| confirm1c | 1004／llama.cpp 2.46.0 | 80/170 | 103/170 | 6 | 29 | 0.000117 |

兩批都 EFFECTIVE、方向一致。P 臂都裝了 Vacant 的 pi 擴充，增益不能單獨歸給重開或 hook；歸因留給 unused40（P 不載入擴充）。

## 後端速度（2026-11-21 補；事後量測，不改結論）

用 `ops/redo/analysis/turn_latency.py`（redo/nonpy-bank 分支）從日誌量：每輪模型回應時間，是 pi session 裡每則 assistant 訊息與前一則訊息的時間差；P 內層撞上限的比例來自 restart 的 result.json；原生單次的數字來自 cell.json。本批是 **confirm1c**（本機），表中其他批是對照。

| 批 | 後端 | 每輪回應 中位／平均／p90（秒） | P 內層撞 600 秒 | 原生單次中位牆鐘、逾時 |
|---|---|---|---|---|
| confirm1c | 1004 llama.cpp，jobs 1 | 5.6／11.8／21.8 | 118/328＝36% | 367 秒、19/170 |
| unused40 | 1004 llama.cpp，jobs 1 | 1.3／5.4／10.9 | 14/225＝6% | 12 秒、3/200 |
| hardpy26 | Colab L4 vLLM，jobs 6 | 6.7／24.5／57.9 | 44/169＝26% | 118 秒、6/130 |
| W3-5 Python | Colab L4 vLLM，jobs 6 | 11.9／43.8／91.7 | 63/100＝63% | 791 秒、9/45 |

讀法：
- 本機（3090、llama.cpp、jobs 1）每輪平均 5–12 秒；Colab（L4、vLLM、jobs 6）中位數相近，但平均與 p90 是本機的 2–4 倍。
- 撞上限不等於沒效：本批 P 的內層嘗試有一部分撞上限，結果仍是 EFFECTIVE。
- 單次上限本身的效果由預註冊的 atimeout 量，不從這張表推。
