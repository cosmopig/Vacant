# CONCLUSION 2026-11-22 — CONFIRM2C（發布候選 wheel 37005ec2 的 `vacant do pi` 對原生 pi，gemma-4-12b QAT，Colab L4 vLLM，polyglot_py 34 題×5，jobs 6）

state＝**UNRESOLVED**，harness_changed_mid_run＝false，harness＝**3c74139794f1**（nonpy）。數字來源：[`ops/redo/results/confirm2c_REPORT.json`](../../ops/redo/results/confirm2c_REPORT.json)。
P 臂的 wheel 在 VM 上驗過 sha256 `37005ec2aa91af874f6697d7ea55434ba6889c5e116ad9de05eb06aca7d4ac2c`（launch metadata）。

## 0. 一句話

原生 96/170（56.5%）、`vacant do pi`（37005ec2）98/170（57.6%），b=18 c=20，p=0.87；infra_void 0、放行卻錯 0。
**沒有量到差別**（不是負結果）。這是 confirm2（1004，同 wheel、同題）在 Colab 上的獨立複製，兩批各自判 state、不併表；1004 那批還在跑。

## 1. REPORT.md（原樣）

# confirm2c_vacantdo_rel092_pi_gemma12b_colab — UNRESOLVED

計畫 sha256 `3da3a7eeaecbda2f…`　完成 170/170 對（有效 170，infra_void 0）　產生於 2026-11-22T05:58:38Z

| 臂 | 通過／有效格 | 比率 | 平均嘗試數 | 平均 agent 牆鐘 | 逾時次數 | 驗收放行卻錯 | 平均模型呼叫 |
|---|---|---|---|---|---|---|---|
| A | 96/170 | 0.5647 | 1.0 | 1038.8s | 51 | 0 | 15.4 |
| P | 98/170 | 0.5765 | 1.0 | 1054.2s | 0 | 0 | None |

**配對（A 對 P）**：只有對照過 b＝18、只有處理過 c＝20、都過 78、都沒過 54；精確 McNemar 雙尾 p＝0.871415；差 1.18 個百分點；題數上淨正 11／淨負 8。

| rep | 對數 | 對照過 | 處理過 | b | c | p |
|---|---|---|---|---|---|---|
| 1 | 34 | 19 | 20 | 4 | 5 | 1.0 |
| 2 | 34 | 20 | 19 | 4 | 3 | 1.0 |
| 3 | 34 | 19 | 18 | 4 | 3 | 1.0 |
| 4 | 34 | 20 | 20 | 5 | 5 | 1.0 |
| 5 | 34 | 18 | 21 | 1 | 4 | 0.375 |

**驗收訊號對評分器（每一次嘗試）**：放行且對 194、放行卻錯 0、擋下卻對 0、擋下且錯 146。

引用規則：只有 state=EFFECTIVE 且 harness_changed_mid_run=false 的整批數字可以引用；引用時要同時講：模型、agent、題庫、對數、等預算的定義、mean_attempts。INCOMPLETE／UNRESOLVED 不是負結果。


## 2. 這個 state 的規則（逐字抄自 `prereg.states.UNRESOLVED`）

> 完成但 p ≥ 0.05（不論方向）。只記方向與大小；不是負結果。停下來回報，不准加 rep、換題、改時限之後再看一次。

## 3. 已知限制（逐字抄自 `prereg.known_limits`）

- 等預算是牆鐘的；R3 的模型呼叫數可能比 A 多或少，報告照實列，不當成主張的一部分。
- polyglot_py 的可見測試就是評分器，驗收訊號在這個題庫上是真的；換題庫要先看報告的 signal.accept_fail。
- 34 題在 e001／e002／e016／realrun 都用過：這是同一批題上的確認，不是沒看過的題。
- A 的時限 1800 秒與 e001／e002 相同，但那些批次的格子環境（vlab cell）與本 harness 不同，數字不可併表。
- P 臂的內層嘗試沒有 harness 的 infra 重試（模型崩潰會吃掉一次嘗試），A 臂有；這個不對稱只會壓低 P。
- P 的模型呼叫數 harness 量不到（usage=none），結案時從 {logs}/vacant-work 的 pi 日誌補算。
- 34 題在 e001／e002／e016／realrun／confirm1／confirm1c 都用過：同一批題上的複製，不是沒看過的題。
- P 的模型呼叫數 harness 量不到（usage=none），結案時用 p_model_calls.py 補算。
- 與 confirm1／confirm1c 只並列、不併表、不合併 p 值。
- 跑在 Colab L4（vLLM 0.30.0，gemma-4-12b-it-qat-w4a16-ct，jobs 6——與 hardpy26／W3-5 同設定，兩批 infra_void 皆 0）；量化與推論引擎都和 1004（llama.cpp 2.46.0，GGUF QAT）不同，絕對數字不與 1004 併表。
- P 臂＝發布 wheel（~/dev/ops/release_0.9.2/2c9791759/vacant_network-0.9.2-py3-none-any.whl，sha256 37005ec2aa91af874f6697d7ea55434ba6889c5e116ad9de05eb06aca7d4ac2c）由 launch_batch --extra-wheel 上傳、在 VM 上裝進 /opt/redo/rc_venv；config_dir 只複製 models.json，不載入 Vacant 的 pi 擴充。
- P 臂用產品預設 --attempt-timeout 600（與 confirm2 相同）；W3-5 Python 批顯示需要單次跑超過 600 秒的題，這個切法會壓低 P——照原樣量，不為這批改。
- harness 是 nonpy 分支的 redo.py（3c74139794f1），1004 的 confirm2 是 c7c6f5842dbf；兩版在本計畫用到的路徑（A/P 單次臂、workspace_tests 驗收、visible_tests_pristine 評分）相同，差別寫在結論檔。
- Colab VM 被回收（idle reclaim／配額）而中斷時：同計畫、同 wheel、同 harness 重新發射，未完成的格重做；已完成的格保留。

## 4. 代價與後端速度（事後量測，不改結論）

- 原生：平均模型呼叫 15.4；單次中位牆鐘 1016 秒；**逾時 51/170**。
- P：`p_model_calls.py` 170 格可算 170、UNKNOWN 0，平均模型呼叫 **19.7**（中位數 17）、平均內層嘗試 **2.094**；內層嘗試撞 600 秒 **268/356（75%）**，至少一次 111/170 格、每次都撞 85 格。
- 每輪回應（`turn_latency.py`）：中位 11.7／平均 46.7／p90 106.4 秒（本機 1004 的 confirm2 前 23 對：平均 10.8；confirm1c：平均 11.8）。
  勘誤（2026-11-25）：這裡引用的 confirm2「前 23 對：平均 10.8」是當時的中途數；全批終值（170/170 對，[`CONCLUSION_20261124_CONFIRM2.md`](CONCLUSION_20261124_CONFIRM2.md)）是每輪 5.8／11.1／20.9 秒、P 撞上限 35.4%（119/336）。另：第 9 行寫的「1004 那批還在跑」已於 11/23 跑完，EFFECTIVE（86/170 → 109/170，p＝0.000824）。讀法不變。

**觀察（不是結論）**：同樣 34 題，1004 的 confirm1c（舊碼＋擴充）原生逾時 19 次、P 撞 600 秒 36%，EFFECTIVE；這個慢後端上原生逾時 51 次、P 撞 600 秒 75%，沒有量到差別。
原生在慢後端卡得更多，但 P 每次嘗試也更常在 600 秒被切斷，重開的好處被吃掉——這和 W3-5／hardpy26 的觀察一致，也正是預註冊的 atimeout（900 對 600）要量的東西。
「增益和推論速度有關」在這裡只是線索；兩批的程式碼（舊碼＋擴充 vs 37005ec2）與後端都不同，不能歸因。

## 5. 量的是哪個程式碼

- P＝37005ec2（rc4 程式碼）。要發布的是 rc5（`redo/rc5` tag `rc5-final`＝1d764cc69），相對它的改變見 `docs/RC5_CHANGES_VS_RC4.md`（發布分支）：交件政策不變（差分 10/10 相同），
  3 個預期不同的情境是修正（專案模組與標準函式庫同名、tests/ 套件）；polyglot_py 34 題都是平的、沒有和標準函式庫同名的模組，所以這兩個修正不影響這批的題。
- rc5 另外多了只在異常時才生效的行為（寫回衝突 exit 43、砍脫離行程等），這批的 170 對裡 P 臂沒有這類事件可比（rc4 不記錄），不做推論。

## 6. 中斷與作廢紀錄

- 12:45Z 發射、05:58Z 完成、05:59Z 取回並停機；infra_void 0。
- 11/22 00:48Z 起加了獨立的守門 unit 與每小時唯讀快照（不碰 keepalive、不碰 runner），都沒有觸發動作；守門在取回後自行結束。

## 7. 同題其他批（只並列，不合併）

| 批 | 後端 | P 是哪版 | 原生 | P | b | c | p | state |
|---|---|---|---|---|---|---|---|---|
| confirm1 | 1003 llama.cpp | 舊碼＋pi 擴充 | 89/170 | 105/170 | 13 | 29 | 0.0195 | EFFECTIVE |
| confirm1c | 1004 llama.cpp | 舊碼＋pi 擴充 | 80/170 | 103/170 | 6 | 29 | 0.000117 | EFFECTIVE |
| confirm2c（本批） | Colab L4 vLLM jobs 6 | 37005ec2，不載入擴充 | 96/170 | 98/170 | 18 | 20 | 0.87 | UNRESOLVED |
| confirm2 | 1004 llama.cpp | 37005ec2，不載入擴充 | （跑中） | | | | | INCOMPLETE |
