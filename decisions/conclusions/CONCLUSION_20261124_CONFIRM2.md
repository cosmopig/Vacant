# CONCLUSION 2026-11-24 — CONFIRM2（要發布的 0.9.2 候選 `vacant do pi` 對原生 pi，gemma-4-12b QAT，1004 llama.cpp jobs 1，polyglot_py 34×5）

計畫：`ops/redo/plans/confirm2_vacantdo_rel092_pi_gemma12b_1004.json`（第一通模型呼叫前 commit）；REPORT：`ops/redo/results/confirm2_REPORT.{md,json}`（原樣複製自 run root）。

P 臂＝當時的發布候選 wheel `37005ec2…`（`~/dev/ops/release_0.9.2/2c9791759`，rc4 程式碼），裝在 `~/dev/ops/release_0.9.2_venv`；pi 不載入任何 Vacant 擴充。

**量的是 `37005ec2`（rc4 程式碼），要發的是 rc6-final（`release/0.9.2-prep` tag `rc6-final`＝`b1ca9b1ff`，wheel `a575c661…`）。** rc5 相對 rc4 的改動與「交付政策不變」的證據見 `docs/RC5_CHANGES_VS_RC4.md`（10/10 相同＋3/3 預期不同）；rc6 相對 rc5-final 只差訊息、輸出、中斷處理與 gc 留存（13/13 相同）。這一批的數字是 `37005ec2` 的數字，引用時照這樣講。

## 0. 一句話

**EFFECTIVE**：原生 pi 86/170 → `vacant do pi` 109/170，b＝11、c＝34，精確 McNemar 雙尾 p＝0.000824；170/170 對完成、infra_void 0、放行卻錯 0、harness 沒有中途變更。同一台 1004、同樣 jobs 1 的 confirm1c（80→103，b＝6、c＝29，P＝當時的 checkout）在同一份題上複製了方向與大小（只並列，不合併）。

## 1. REPORT.md（原樣）

## confirm2_vacantdo_rel092_pi_gemma12b_1004 — EFFECTIVE

計畫 sha256 `2593712a74ceb533…`　完成 170/170 對（有效 170，infra_void 0）　產生於 2026-11-23T19:31:42Z

| 臂 | 通過／有效格 | 比率 | 平均嘗試數 | 平均 agent 牆鐘 | 逾時次數 | 驗收放行卻錯 | 平均模型呼叫 |
|---|---|---|---|---|---|---|---|
| A | 86/170 | 0.5059 | 1.0 | 459.0s | 12 | 0 | 40.7 |
| P | 109/170 | 0.6412 | 1.0 | 749.6s | 0 | 0 | None |

**配對（A 對 P）**：只有對照過 b＝11、只有處理過 c＝34、都過 75、都沒過 50；精確 McNemar 雙尾 p＝0.000824；差 13.53 個百分點；題數上淨正 17／淨負 3。

| rep | 對數 | 對照過 | 處理過 | b | c | p |
|---|---|---|---|---|---|---|
| 1 | 34 | 16 | 22 | 1 | 7 | 0.070312 |
| 2 | 34 | 17 | 22 | 2 | 7 | 0.179688 |
| 3 | 34 | 17 | 25 | 1 | 9 | 0.021484 |
| 4 | 34 | 14 | 21 | 2 | 9 | 0.06543 |
| 5 | 34 | 22 | 19 | 5 | 2 | 0.453125 |

**驗收訊號對評分器（每一次嘗試）**：放行且對 195、放行卻錯 0、擋下卻對 0、擋下且錯 145。

引用規則：只有 state=EFFECTIVE 且 harness_changed_mid_run=false 的整批數字可以引用；引用時要同時講：模型、agent、題庫、對數、等預算的定義、mean_attempts。INCOMPLETE／UNRESOLVED 不是負結果。


## 2. 可以說的句子（逐字抄自 `prereg.states.EFFECTIVE`，數字照本批填）

170 對全部完成（扣 infra_void）、c > b 且 p < 0.05、驗收放行卻錯＝0。可以說：「在這 34 題、pi、gemma-4-12b（1004，llama.cpp 2.46.0）、同樣 1800 秒上限下，要發布的 0.9.2（`vacant do pi`，零設定重開；pi 不載入任何 Vacant 擴充）交出通過的成果，比原生 pi 一次跑到底多（數字、P 的內層平均嘗試數、模型呼叫數一起講）」。不可以說：不帶條件的「Vacant 讓 agent 更好」、外推到別的模型／題庫／沒有可執行測試的工作；這 34 題用過多次，是同一批題上的複製，不是泛化證據。

> **註（結案時加，不改上面的逐字句）**：句中「要發布的 0.9.2」是預註冊當時的字眼，指的是當時的候選 wheel `37005ec2…`（rc4 程式碼）。現在要發的是 **rc6-final**（`b1ca9b1ff`，wheel `a575c661…`）：rc5 相對 rc4 的改動見 `docs/RC5_CHANGES_VS_RC4.md`（政策差分 10/10 相同＋3/3 預期不同），rc6 相對 rc5-final 只差訊息、輸出、中斷處理與 gc 留存。這一批的數字是 `37005ec2` 的數字，不是 rc6-final 的；引用這句時連這一行一起引用。

本批數字：**86/170 → 109/170（b＝11、c＝34，p＝0.000824）；P 的內層平均嘗試 1.98；平均模型呼叫 A 40.7、P 64.1（p_model_calls 補算，170/170 格可算）。**

## 3. 代價

- A：平均模型呼叫 40.7、平均 agent 牆鐘 459.0 秒、逾時 12 次。
- P：`p_model_calls.py` 補算 170/170 格可算；平均模型呼叫 **64.1**（中位數 51.5）、平均內層嘗試 **1.98**；平均 agent 牆鐘 749.6 秒、外層逾時 0。

## 4. 後端速度（`ops/redo/analysis/turn_latency.py <run root>`，本批自己的數字）

- 每輪模型回應：中位 5.8／平均 11.1／p90 20.9 秒（n＝17814；A 6.5／11.2／18.7，P 5.2／11.1／21.7）。
- P 內層撞 600 秒上限：**119/336（35.4%）**；至少一次 67/170 格、每次都撞 14 格。
- A 單次：中位牆鐘 300.1 秒、逾時 12/170。
- 並列：本機 confirm1c 每輪 5.6／11.8／21.8 秒、P 撞上限 36%；Colab 12B confirm2c 平均 46.7 秒、75%。本批就是本機快後端的基準之一。

## 6. 已知限制（逐字抄自 `prereg.known_limits`）

- 等預算是牆鐘的；R3 的模型呼叫數可能比 A 多或少，報告照實列，不當成主張的一部分。
- polyglot_py 的可見測試就是評分器，驗收訊號在這個題庫上是真的；換題庫要先看報告的 signal.accept_fail。
- 34 題在 e001／e002／e016／realrun 都用過：這是同一批題上的確認，不是沒看過的題。
- A 的時限 1800 秒與 e001／e002 相同，但那些批次的格子環境（vlab cell）與本 harness 不同，數字不可併表。
- P 臂的內層嘗試沒有 harness 的 infra 重試（模型崩潰會吃掉一次嘗試），A 臂有；這個不對稱只會壓低 P。
- P 的模型呼叫數 harness 量不到（usage=none），結案時從 {logs}/vacant-work 的 pi 日誌補算。
- 跑在 1004（llama.cpp 2.46.0，與 redo1 同一台、同一個引擎），但 P 臂與 A 臂的定義與 confirm1 相同；1004 的 gemma 與實驗室助手共用。
- P 臂＝發布 wheel（~/dev/ops/release_0.9.2/2c9791759，sha256 37005ec2aa91af874f6697d7ea55434ba6889c5e116ad9de05eb06aca7d4ac2c）裝在 ~/dev/ops/release_0.9.2_venv；config_dir 只複製 models.json，不載入 Vacant 的 pi 擴充。
- 34 題在 e001／e002／e016／realrun／confirm1／confirm1c 都用過：同一批題上的複製，不是沒看過的題。
- P 的模型呼叫數 harness 量不到（usage=none），結案時用 p_model_calls.py 補算。
- 與 confirm1／confirm1c 只並列、不併表、不合併 p 值。

### 結案時補記

- **本機 OOM（11/23 16:23–17:37Z）**：kernel 的 OOM killer 殺了 4 個 python3（RSS 5.4–6.9 GB），都在 redo-queue-1004 的 cgroup 裡，時間落在 `pg_sgf_parsing/r5/P`（16:11–16:39，一次）與 `pg_variable_length_quantity/r5/P`（17:24–17:44，三次）。jobs 1，同時只有這一格在跑。
  - `pg_variable_length_quantity/r5/P`（**已確認**，讀到原始碼）：agent 第 2 次嘗試寫出的 `encode()` 是沒有出口的 `while True` 迴圈（不斷 append），agent 自己跑測試時被殺兩次（17:31、17:33，第 2 次嘗試的 agent 階段），驗收時又被殺一次（17:37:54），所以第 2 次嘗試記為 `runner_no_output`、不放行；第 3 次嘗試 3/26，交回第 1 次（22/26），rc＝40。A 那格通過，所以這一對算進 b。
  - `pg_sgf_parsing/r5/P`：16:23 那次落在第 2 次嘗試的 agent 階段。**這一格是推定**：只有時間與 cgroup 對得上，原始碼裡找不到能確認的失控寫法（vlq 那格是讀到原始碼確認的）；兩臂都沒過，這一對不進 b／c。
  - **照 harness 既有規則判斷**：infra_void 只在「工作區沒動＋0 次成功的模型回應，或做到一半的連線類錯誤」時成立；兩格工作區都改過、模型呼叫都成功，所以**不算 void**，照計。被殺的是那個吃掉記憶體的行程本身（OOM killer 選最大的那個），沒有波及別的格。
  - **敏感度分析（拿掉這兩對）**：b＝10、c＝34，p＝0.000388；state 不變（EFFECTIVE），方向與大小不變。
  - 這個 OOM 也讓 systemd 把佇列 unit 判 failed（OOMPolicy 預設 stop），佇列腳本死掉、confirm2oc 沒有接著發（runner 本身照跑完）。之後的佇列 unit 加 OOMPolicy＝continue 並設記憶體上限（見結論以外的 ops 修正）。

## 7. 中斷與作廢紀錄

- 11/21 10:23Z 由 1004 佇列發射、11/23 19:31Z 完成；infra_void 0。
- 11/22 一次記憶體壓力讓 Claude Code 停掉等候 confirm2 結束的監看（不是批次本身）。
- 11/23 16:23–17:37Z 的 OOM 見上一節。
