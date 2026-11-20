# CONCLUSION 2026-11-20 — CONFIRM1（`vacant do pi` 對原生 pi，gemma-4-12b，1003，polyglot_py 34 題×5）

state＝**EFFECTIVE**，harness_changed_mid_run＝false（harness c7c6f5842dbf）。數字來源：[`ops/redo/results/confirm1_REPORT.json`](../../ops/redo/results/confirm1_REPORT.json)。
這是**產品指令**的數字（T05），與 redo1（harness 裡的機制）分開講。

## 1. REPORT.md（原樣）

### confirm1_vacantdo_pi_gemma12b_1003 — EFFECTIVE

計畫 sha256 `e10843db6bdbb13a…`　完成 170/170 對（有效 170，infra_void 0）　產生於 2026-11-20T01:27:23Z

| 臂 | 通過／有效格 | 比率 | 平均嘗試數 | 平均 agent 牆鐘 | 逾時次數 | 驗收放行卻錯 | 平均模型呼叫 |
|---|---|---|---|---|---|---|---|
| A | 89/170 | 0.5235 | 1.0 | 743.4s | 38 | 0 | 48.2 |
| P | 105/170 | 0.6176 | 1.0 | 902.6s | 1 | 0 | None |

**配對（A 對 P）**：只有對照過 b＝13、只有處理過 c＝29、都過 76、都沒過 52；精確 McNemar 雙尾 p＝0.01952；差 9.41 個百分點；題數上淨正 12／淨負 5。

| rep | 對數 | 對照過 | 處理過 | b | c | p |
|---|---|---|---|---|---|---|
| 1 | 34 | 19 | 24 | 3 | 8 | 0.226562 |
| 2 | 34 | 16 | 19 | 3 | 6 | 0.507812 |
| 3 | 34 | 15 | 22 | 0 | 7 | 0.015625 |
| 4 | 34 | 17 | 21 | 2 | 6 | 0.289062 |
| 5 | 34 | 22 | 19 | 5 | 2 | 0.453125 |

**驗收訊號對評分器（每一次嘗試）**：放行且對 194、放行卻錯 0、擋下卻對 0、擋下且錯 146。

引用規則：只有 state=EFFECTIVE 且 harness_changed_mid_run=false 的整批數字可以引用；引用時要同時講：模型、agent、題庫、對數、等預算的定義、mean_attempts。INCOMPLETE／UNRESOLVED 不是負結果。

⚠ 有嘗試以模型錯誤結束、但沒被歸成基礎設施失敗（照常計入分母）。看原文決定是不是該歸成 void：`{"A": {"Engine protocol predict stream returned an error: {\"code\":500,\"message\":\"Context size has been exceeded.\",\"type\":\"server_error\"}": 2}}`

## 2. 這個 state 可以說的話（逐字抄自計畫檔 `prereg.states.EFFECTIVE`）

> 170 對全部完成、c > b 且 p < 0.05。可以說：「在這 34 題、pi、gemma-4-12b（1003，llama.cpp 2.73.0）、同樣 1800 秒上限下，用產品指令 `vacant do pi`（零設定重開模式，本機已安裝 Vacant 的 pi 擴充）交出通過的成果，比原生 pi 一次跑到底多（數字、P 的內層平均嘗試數一起講）」。不可以說：不帶條件的「Vacant 讓 agent 更好」、外推到別的模型／題庫／沒有可執行測試的工作；也不能把增益單獨歸給重開或單獨歸給 hook（兩者在 P 臂裡同時存在）。

## 3. 已知限制（逐字抄自 `prereg.known_limits`）

- 等預算是牆鐘的；R3 的模型呼叫數可能比 A 多或少，報告照實列，不當成主張的一部分。
- polyglot_py 的可見測試就是評分器，驗收訊號在這個題庫上是真的；換題庫要先看報告的 signal.accept_fail。
- 34 題在 e001／e002／e016／realrun 都用過：這是同一批題上的確認，不是沒看過的題。
- A 的時限 1800 秒與 e001／e002 相同，但那些批次的格子環境（vlab cell）與本 harness 不同，數字不可併表。
- P 臂的 pi 讀使用者自己的 ~/.pi/agent（含 `vacant install` 裝的 extensions/vacant.ts 與壓縮設定），A 臂是 harness 的乾淨設定目錄：比的是「沒裝 Vacant 的原生 pi」對「裝了 Vacant、打 `vacant do pi`」。screen16p4 的 P 日誌裡 hook 沒有注入過任何訊息。
- P 臂的內層嘗試沒有 harness 的 infra 重試（模型崩潰會吃掉一次嘗試），A 臂有；這個不對稱只會壓低 P。
- 跑在 1003（llama.cpp 2.73.0），redo1 在 1004（2.46.0）；1003 上 A 臂較常跑滿 1800 秒卡在循環，兩批的絕對數字不可併表。
- P 的模型呼叫數 harness 量不到（usage=none），結案時從 {logs}/vacant-work 的 pi 日誌補算。

## 4. 代價

- A：平均模型呼叫 48.2、平均 agent 牆鐘 743.4s（`per_arm`）。
- P：harness 量不到（usage=none）；`ops/redo/analysis/p_model_calls.py` 從 pi 日誌補算：170 格可算 169、UNKNOWN 1（`pg_sgf_parsing/r3/P`：外層 1900 秒逾時把 `vacant do` 砍掉、沒寫 result.json），可算的格平均 **65.9** 次（中位數 42）、平均內層嘗試 2.006；平均 agent 牆鐘 902.6s（`per_arm`）。
- 這一層換到的是交付率，不是省算力：P 的模型呼叫多於 A。

## 5. 敏感度分析（事後、非預註冊；主結論以 §1 為準）

兩條同時跑時共用 KV（262144）會被 `pg_forth` 的長對話擠滿，同時在跑的另一格收到 `Context size has been exceeded`。任一臂日誌出現此錯誤的對：`pg_forth/r3`、`pg_forth/r5`、`pg_rest_api/r3`、`pg_scale_generator/r5`（結果 A/P：沒/沒、沒/沒、沒/沒、過/沒）。
拿掉這 4 對：166 對、b=12、c=29、精確 McNemar p=0.0115（全部：170 對、b=13、c=29、p=0.0195）。方向與結論不變。

## 6. 中斷與作廢紀錄

- 2026-11-19 03:48:27Z–14:13:33Z 停批（本機 ext4 錯誤，重開機 fsck）；SIGTERM 停、同計畫同 harness 續跑，中斷那格整格重做。
- 同一產品主張的先前批次作廢、不進任何結論：screen16p（ctx 65536）、screen16p2（1004 jobs 2 bad allocation）、screen16p3（1004 磁碟滿）、confirm1b（見 `ops/redo/results/void/confirm1b/VOID.md`，含計畫偏離）。
- 篩選 screen16p4（GO）：`ops/redo/results/screen16p4_REPORT.md`。1004 的獨立複製批 confirm1c 跑中，結案後另寫，不與本批合併。
