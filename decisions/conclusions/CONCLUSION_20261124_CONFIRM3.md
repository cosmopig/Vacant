# CONCLUSION 2026-11-24 — CONFIRM3（rc5-final `vacant do pi` 對原生 pi，gemma-4-12b QAT，Colab A100 vLLM jobs 4，polyglot_py 34×5）

計畫：`ops/redo/plans/confirm3_vacantdo_rc5_pi_gemma12b_a100.json`（第一通模型呼叫前 commit）；REPORT：`ops/redo/results/confirm3_REPORT.{md,json}`（原樣複製自 run root）。

P 臂＝發布版 rc5-final wheel（`5bbc57af…`，`757ade62f`），由 `launch_batch --extra-wheel` 裝進 VM；pi 不載入任何 Vacant 擴充。

**量的是 rc5-final，要發的是 rc6-final（`release/0.9.2-prep` tag `rc6-final`＝`b1ca9b1ff`，wheel `a575c661…`），只差訊息、輸出、中斷處理與 gc 留存；交付政策相同（政策差分兩邊用 wheel 跑：13/13 相同，`docs/RC5_CHANGES_VS_RC4.md` 的 rc6 節）。**

## 0. 一句話

**EFFECTIVE**：原生 pi 104/170 → `vacant do pi` 120/170，b＝7、c＝23，精確 McNemar 雙尾 p＝0.005223；170/170 對完成、infra_void 0、放行卻錯 0。同一份 34 題上，本機 confirm1／1c／2 都是 EFFECTIVE、Colab L4 的 confirm2c 是 UNRESOLVED（慢後端）；這一批是發布版 rc5-final 在 Colab A100 上的確認（只並列，不合併）。

## 1. REPORT.md（原樣）

## confirm3_vacantdo_rc5_pi_gemma12b_a100 — EFFECTIVE

計畫 sha256 `bf5fb94b5c8c1ed7…`　完成 170/170 對（有效 170，infra_void 0）　產生於 2026-11-23T01:44:17Z

| 臂 | 通過／有效格 | 比率 | 平均嘗試數 | 平均 agent 牆鐘 | 逾時次數 | 驗收放行卻錯 | 平均模型呼叫 |
|---|---|---|---|---|---|---|---|
| A | 104/170 | 0.6118 | 1.0 | 552.3s | 9 | 0 | 17.8 |
| P | 120/170 | 0.7059 | 1.0 | 770.0s | 0 | 0 | None |

**配對（A 對 P）**：只有對照過 b＝7、只有處理過 c＝23、都過 97、都沒過 43；精確 McNemar 雙尾 p＝0.005223；差 9.41 個百分點；題數上淨正 11／淨負 1。

| rep | 對數 | 對照過 | 處理過 | b | c | p |
|---|---|---|---|---|---|---|
| 1 | 34 | 20 | 23 | 3 | 6 | 0.507812 |
| 2 | 34 | 22 | 25 | 0 | 3 | 0.25 |
| 3 | 34 | 21 | 22 | 3 | 4 | 1.0 |
| 4 | 34 | 21 | 25 | 0 | 4 | 0.125 |
| 5 | 34 | 20 | 25 | 1 | 6 | 0.125 |

**驗收訊號對評分器（每一次嘗試）**：放行且對 224、放行卻錯 0、擋下卻對 0、擋下且錯 116。

引用規則：只有 state=EFFECTIVE 且 harness_changed_mid_run=false 的整批數字可以引用；引用時要同時講：模型、agent、題庫、對數、等預算的定義、mean_attempts。INCOMPLETE／UNRESOLVED 不是負結果。


## 2. 可以說的句子（逐字抄自 `prereg.states.EFFECTIVE`，數字照本批填）

170 對全部完成（扣 infra_void）、c > b 且 p < 0.05、驗收放行卻錯＝0。可以說：「在這 34 題、pi、gemma-4-12b QAT（Colab A100，vLLM 0.30.0，w4a16，每輪時間接近本機）、同樣 1800 秒上限下，要發布的 0.9.2（rc5-final，`vacant do pi`，零設定重開；pi 不載入任何 Vacant 擴充）交出通過的成果，比原生 pi 一次跑到底多（數字、P 的內層平均嘗試數、模型呼叫數一起講）」。不可以說：不帶條件的「Vacant 讓 agent 更好」、外推到別的模型／題庫／沒有可執行測試的工作；這 34 題用過多次（e001／e002／e016／realrun／confirm1／1c／2／2c），是同一批題上的複製，不是泛化證據。

> **註（結案時加，不改上面的逐字句）**：句中「要發布的 0.9.2」是預註冊當時的字眼。這一批量的是 **rc5-final**（wheel `5bbc57af…`）；現在要發的是 **rc6-final**（`release/0.9.2-prep` tag `rc6-final`＝`b1ca9b1ff`，wheel `a575c661…`），兩者只差訊息、輸出、中斷處理與 gc 留存，交付政策相同（政策差分兩邊用 wheel：13/13 相同）。引用這句時連這一行一起引用。

本批數字：**104/170 → 120/170（b＝7、c＝23，p＝0.005223）；P 的內層平均嘗試 1.85；平均模型呼叫 A 17.8、P 26.4（p_model_calls 補算，170/170 格可算）。**

⚠ 預註冊句子裡的「每輪時間接近本機」要照第 4 節讀：中位數在本機範圍內，平均與長尾比本機慢。

## 3. 代價

- A：平均模型呼叫 17.8、平均 agent 牆鐘 552.3 秒、逾時 9 次。
- P：補算 170/170 格可算；平均模型呼叫 **26.4**（中位數 20.0）、平均內層嘗試 **1.85**；平均 agent 牆鐘 770.0 秒、外層逾時 0。
- 算力：Colab A100（第二個帳號）約 16.5 小時（11/22 09:21Z 發射、11/23 01:44Z REPORT）。

## 4. 後端速度（`ops/redo/analysis/turn_latency.py <run root>`，本批自己的數字）

- 每輪模型回應：中位 **8.3**／平均 **27.4**／p90 **55.0** 秒（n＝7499；A 8.9／29.6／60.3，P 7.8／25.9／49.7）。
- P 內層撞 600 秒上限：**136/314（43.3%）**；至少一次 65/170 格、每次都撞 28 格。
- A 單次：中位牆鐘 375.6 秒、逾時 9/170。
- 並列：本機 confirm1c 每輪 5.6／11.8／21.8 秒、P 撞上限 36%；Colab 12B confirm2c 平均 46.7 秒、75%；本機 confirm2 5.8／11.1／20.9、35.4%。
- **讀法（不要只引中位數）**：中位 8.3 秒在本機範圍（5–12 秒）內，但平均 27.4 秒約為本機的 2.4 倍、p90 是 2.6 倍，長尾明顯比本機慢；P 撞上限 43%，高於本機的 30–36%、遠低於 confirm2c 的 75%。所以這一批是「介於本機與慢後端之間」的後端，不是本機速度——36 對時的快照（35%）比全批樂觀。A 單次中位 376 秒在本機 300–423 秒之間。

## 5. 真模型 W4 整理（P 臂的 170 份 result.json）

- **收據**：170/170 份 result.json 的收據都記錄成功（`receipt.recorded`）。簽章鏈在 VM 的 `$VACANT_HOME` 裡、沒有隨結果取回，所以這一批**沒辦法在本機跑 `vacant audit list --strict`**；之後的 Colab 批次要一起取回 `$VACANT_HOME/trace`（記進 ops 待辦）。
- **驗收完整性**：170/170 `traced`、0 `untraced`；NOTE（驗收輸入被改動）0 次——polyglot_py 是單檔 unittest，預期如此，這一批對 NOTE 路徑沒有鑑別力。
- **exit 43**（寫回衝突、不可讀、不可寫）：0。
- **subreaper**：2 次 run 偵測到脫離的子孫行程，砍掉 1 個。
- **孤兒**：Colab VM 上沒有本機的孤兒看門；批次結束後 VM 已停。
- **內層嘗試狀態**：ok 289、load_error 23（agent 寫出無法匯入的模組，計為不放行）、timeout 2。
- **交件結果分布**（170 份 result.json 逐份計）：放行 120 格，交回的是第 1／2／3 次嘗試各 86／24／10 格；未放行 50 格，交回第 1／2／3 次各 11／21／18 格。訊息第一行對應「acceptance passed on attempt K (up to 3 allowed; N/M tests); delivered that attempt」（放行）與「not all tests pass after 3 attempt(s); delivered attempt K (N/M tests)」（未放行）。

## 6. 已知限制（逐字抄自 `prereg.known_limits`）

- 等預算是牆鐘的；R3 的模型呼叫數可能比 A 多或少，報告照實列，不當成主張的一部分。
- polyglot_py 的可見測試就是評分器，驗收訊號在這個題庫上是真的；換題庫要先看報告的 signal.accept_fail。
- 34 題在 e001／e002／e016／realrun 都用過：這是同一批題上的確認，不是沒看過的題。
- A 的時限 1800 秒與 e001／e002 相同，但那些批次的格子環境（vlab cell）與本 harness 不同，數字不可併表。
- P 臂的內層嘗試沒有 harness 的 infra 重試（模型崩潰會吃掉一次嘗試），A 臂有；這個不對稱只會壓低 P。
- P 的模型呼叫數 harness 量不到（usage=none），結案時從 {logs}/vacant-work 的 pi 日誌補算。
- 34 題在 e001／e002／e016／realrun／confirm1／confirm1c 都用過：同一批題上的複製，不是沒看過的題。
- P 的模型呼叫數 harness 量不到（usage=none），結案時用 p_model_calls.py 補算。
- 與 confirm1／confirm1c 只並列、不併表、不合併 p 值。
- P 臂用產品預設 --attempt-timeout 600（與 confirm2 相同）；W3-5 Python 批顯示需要單次跑超過 600 秒的題，這個切法會壓低 P——照原樣量，不為這批改。
- P 臂＝發布版 rc5-final：~/dev/ops/release_0.9.2/757ade62f/vacant_network-0.9.2-py3-none-any.whl（sha256 5bbc57afda540466b8dde88dba5f225b00a52185045541b79f8cb54c79888899，rc5-final＝redo/rc5 1d764cc69），由 launch_batch --extra-wheel 上傳、裝進 VM 的 /opt/redo/rc_venv；config_dir 只複製 models.json，不載入 Vacant 的 pi 擴充。
- 11/22 量測（第二個 Colab 帳號、短命 A100 session，ops/redo/colab/vllm_concurrency_probe.py，不吃 prefix cache、輸出 400 token 的保守上界）：12B 每輪 6k 上下文 c1 6.6／c2 8.4／c3 9.7／c4 11.6／c6 15.7 秒；24k 上下文 c1 17.5／c2 29.6／c3 41.6／c4 54.0／c6 78.3 秒。對照：L4 jobs 6 量測 6k＝53.6 秒、confirm2c 實測平均每輪 46.7 秒（約 0.87 倍），據此 A100 jobs 4 的實際每輪平均約 10 秒，落在本機 3090（llama.cpp jobs 1）實測 5–12 秒的範圍。
- 選 jobs 的規則（vacant-hope 11/22）：每輪時間落在本機範圍（平均 5–12 秒）的最大並行數 ⇒ jobs 4。只用 A100；配不到 A100 就不發、不退到 L4（L4 上 12B 即使 jobs 1 每輪也要 19 秒以上，達不到本機範圍）。
- 跑在 Colab A100（第二個帳號），量化與推論引擎（vLLM w4a16）和本機（llama.cpp GGUF QAT）不同；絕對數字不與 1003／1004／L4 的批次併表，只並列。
- harness 是 nonpy 分支的 redo.py（3c74139794f1）。
- 發射前先用同一個 wheel、同一種 GPU 跑 2 對冒煙（smoke_confirm3_rc5_a100）；發射時帶獨立守門、每小時唯讀快照、連續三次確認版 keepalive。VM 中途遺失時照 harness 續跑規則，用快照在新開的 A100 上以同計畫、同 root 接著跑（已完成的格不重跑），結論記一筆中斷。
- 34 題都是平的、沒有和標準函式庫同名的模組，所以 rc5 相對 rc4 的兩個修正（P1、N1）不影響這批的題；rc5 其他只在異常時才生效的行為照常記錄（收據、traced／untraced、脫離行程、寫回衝突），結案時整理。

## 7. 中斷與作廢紀錄

- 11/22 09:19Z 第一次要 A100 回 503，同日 09:21Z 重試配到；主批 09:21Z 發射、11/23 01:44Z REPORT，取回後停機。
- 快照：10:37Z 一次連線失敗、之後照常；守門沒有重啟過。
- 同時在同一個帳號跑的 W3-5 JS 重跑結果沒有取回（另見其 VOID）；它的 VM 在 confirm3 取回之後空燒，第二個帳號餘額歸零——不影響本批結果。
