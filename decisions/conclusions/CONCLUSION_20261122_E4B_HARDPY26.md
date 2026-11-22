# CONCLUSION 2026-11-22 — E4B HARDPY26（`vacant do pi` rc5-final 對原生 pi，gemma-4-E4B QAT，Colab L4 vLLM jobs 2，exercism difficulty ≥4 的 26 題×5）

計畫：`ops/redo/plans/e4b_hardpy26_vacantdo_rc5_colab.json`（第一通模型呼叫前 commit）；REPORT：`ops/redo/results/e4b_hardpy26_REPORT.{md,json}`（原樣複製自 run root）。
P 臂＝發布版 rc5-final wheel（sha256 `5bbc57af…`，`757ade62f`），由 `launch_batch --extra-wheel` 裝進 VM；pi 不載入任何 Vacant 擴充。

**量的是 rc5-final，要發的是 rc6-final。** rc6-final（`release/0.9.2-prep` tag `rc6-final`＝`b1ca9b1ff`，wheel `a575c661…`）相對 rc5-final 只差訊息、輸出、中斷處理與 gc 留存；交付政策相同（政策差分兩邊用 wheel 跑：13/13 相同，見 `docs/RC5_CHANGES_VS_RC4.md` 的 rc6 節）。這一批的數字是 rc5-final 的數字，引用時照這樣講，不寫成 rc6 量到的。

## 0. 一句話

**EFFECTIVE**：原生 pi 61/130 → `vacant do pi` 84/130，b＝8、c＝31，精確 McNemar 雙尾 p＝0.000294；130/130 對完成、infra_void 0、驗收放行卻錯 0、harness 沒有中途變更。
同一份題、同一個後端換成 12B（hardpy26_colab）是 114 vs 116、UNRESOLVED（接近天花板）——**弱模型上量得到重開的增益**，和「強的 agent 很少用到重開、增益在弱的本機模型」的定位一致（只並列，不合併 p 值）。

## 1. REPORT.md（原樣）

## e4b_hardpy26_vacantdo_rc5_colab — EFFECTIVE

計畫 sha256 `cb0012349ce91daa…`　完成 130/130 對（有效 130，infra_void 0）　產生於 2026-11-22T15:09:35Z

| 臂 | 通過／有效格 | 比率 | 平均嘗試數 | 平均 agent 牆鐘 | 逾時次數 | 驗收放行卻錯 | 平均模型呼叫 |
|---|---|---|---|---|---|---|---|
| A | 61/130 | 0.4692 | 1.0 | 91.6s | 0 | 0 | 9.7 |
| P | 84/130 | 0.6462 | 1.0 | 271.3s | 0 | 0 | None |

**配對（A 對 P）**：只有對照過 b＝8、只有處理過 c＝31、都過 53、都沒過 38；精確 McNemar 雙尾 p＝0.000294；差 17.69 個百分點；題數上淨正 13／淨負 3。

| rep | 對數 | 對照過 | 處理過 | b | c | p |
|---|---|---|---|---|---|---|
| 1 | 26 | 13 | 16 | 1 | 4 | 0.375 |
| 2 | 26 | 14 | 15 | 4 | 5 | 1.0 |
| 3 | 26 | 9 | 21 | 0 | 12 | 0.000488 |
| 4 | 26 | 11 | 14 | 2 | 5 | 0.453125 |
| 5 | 26 | 14 | 18 | 1 | 5 | 0.21875 |

**驗收訊號對評分器（每一次嘗試）**：放行且對 145、放行卻錯 0、擋下卻對 0、擋下且錯 115。

引用規則：只有 state=EFFECTIVE 且 harness_changed_mid_run=false 的整批數字可以引用；引用時要同時講：模型、agent、題庫、對數、等預算的定義、mean_attempts。INCOMPLETE／UNRESOLVED 不是負結果。

## 2. 可以說的句子（逐字抄自 `prereg.states.EFFECTIVE`，數字照本批填）

「在這 26 題沒用過、difficulty ≥ 4 的 Python 題（exercism_py_hard，與 hardpy26_vacantdo_rc3_pi_gemma12b_colab 同題同後端）、pi、gemma-4-E4B-it QAT（Colab，vLLM 0.30.0，w4a16）、同樣 1800 秒上限下，發布候選版 `vacant do pi`（rc5-final 0.9.2，零設定重開；pi 不載入任何 Vacant 擴充）交出通過的成果，比原生 pi 一次跑到底多」——**61/130 → 84/130（b＝8、c＝31，p＝0.000294）；P 的內層平均嘗試 1.92；平均模型呼叫 A 9.7、P 21.5（p_model_calls 補算，130/130 格可算）**。

不可以說：不帶條件的「Vacant 讓 agent 更好」、外推到別的模型／語言／沒有可執行測試的工作。

## 3. 代價

- A：平均模型呼叫 9.7、平均 agent 牆鐘 91.6 秒、逾時 0；通過的 61 格沒有一格單次超過 600 秒。
- P：`p_model_calls.py` 補算 130 格可算 **130**、UNKNOWN 0；平均模型呼叫 **21.5**（中位數 17.0）、平均內層嘗試 **1.92**；平均 agent 牆鐘 271.3 秒（約 A 的 3 倍）、外層逾時 0。
- 算力：Colab L4 約 7 小時（08:18Z 發射、15:19Z 取回並停機），第一個帳號；停機後該帳號 `colab usage` 餘額 41.78。

## 4. 後端速度（`ops/redo/analysis/turn_latency.py <run root>`，本批自己的數字）

- 每輪模型回應：中位 3.6／平均 10.3／p90 28.6 秒（n＝4060；A 3.2／9.0／24.7，P 3.8／10.9／30.4）。
- P 內層撞 600 秒上限：**5/250（2%）**；至少一次 4/130 格、每次都撞 0 格。
- A 單次：中位牆鐘 66.5 秒、逾時 0/130。
- 並列：本機 confirm1c 每輪 5.6／11.8／21.8、P 撞上限 36%；confirm2 5.4／11.1／21.4、30%；Colab 12B 的 confirm2c 平均 46.7、75%；hardpy26_colab（12B，jobs 6）6.7／24.5／57.9、26%。
- 讀法：E4B＋jobs 2 的每輪時間落在本機範圍內，600 秒上限幾乎沒有作用（2%）——這批量到的是重開本身，不是時限。預註冊選 jobs 2 時用的並行數量測（6k 上下文 c2 13.3 秒）是保守上界，實際平均 10.3 秒。

## 5. 已知限制（逐字抄自 `prereg.known_limits`）

- P 的模型呼叫數 harness 量不到（usage=none），結案時用 p_model_calls.py 補算。
- jobs 6：兩臂受同樣壅塞。
- E4B 的上下文上限是 131072（模型 config 的 max_position_embeddings），12B 是 262144；vllm_gemma4_e4b.json 照此設定，pi 的 contextWindow 也跟著是 131072。11/22 第一次發射冒煙時誤設 262144，vLLM 起不來、0 次模型呼叫，該次作廢不計。
- P 臂＝發布版 rc5-final：~/dev/ops/release_0.9.2/757ade62f/vacant_network-0.9.2-py3-none-any.whl（sha256 5bbc57afda540466b8dde88dba5f225b00a52185045541b79f8cb54c79888899，rc5-final＝redo/rc5 1d764cc69），由 launch_batch --extra-wheel 裝進 VM 的 /opt/redo/rc_venv；config_dir 只複製 models.json，不載入 Vacant 的 pi 擴充。
- 11/22 量測（另開短命 L4 session，ops/redo/colab/vllm_concurrency_probe.py，不吃 prefix cache、輸出 400 token 的保守上界）：E4B 每輪 6k 上下文 c1 10.1／c2 13.3／c3 15.1／c4 17.8／c6 23.2 秒；24k 上下文 c1 22.2／c2 36.8／c3 51.4／c4 66.3／c6 92.4 秒。本機 3090 llama.cpp jobs 1 實測平均每輪 5–12 秒。
- 選 jobs 的規則：每輪時間最接近本機範圍、而且付得起。jobs 1（10.1 秒，在本機範圍內）要約 22 小時／43 單元，超過餘額；jobs 2（13.3 秒，略高於本機上限）約 11 小時／21 單元——採用 jobs 2（vacant-hope 11/22 同意）。每輪時間仍略慢於本機，結果讀成「接近本機速度的後端」，不是本機。
- 主批前先用同一個 wheel 跑 2 對冒煙（smoke3_vacantdo_rc5_e4b_colab），過了才發。
- 發射時帶獨立守門 unit、每小時唯讀快照與「連續三次確認」版 keepalive；VM 中途遺失時照 harness 續跑規則用快照在同規格 VM 上接著跑，結論記一筆中斷。

## 6. 中斷與作廢紀錄

- 11/22 第一次冒煙誤設 `max_model_len` 262144（E4B 上限 131072），vLLM 起不來、0 次模型呼叫，該次作廢不計；修正設定、寫進 prereg 後重跑冒煙（smoke3_vacantdo_rc5_e4b_colab，2/2 對、0 void）才發主批。
- 主批：08:18Z 發射（L4）、15:09Z REPORT、15:19Z 取回並停機；守門 0 次重啟、每小時快照 7 份全成功、keepalive 的單次 exec 失敗 10 次（都在下一輪恢復，沒有 3 次連續查不到 session）。
- 第一個帳號的餘額看門（門檻 15）全程沒有動作；該帳號上同時有使用者其他專案的一個短 session，我們沒有碰。

## 7. 與其他批（只並列，不合併）

| 批 | 模型 | 後端 | 原生 → 產品 | b／c | p | state |
|---|---|---|---|---|---|---|
| hardpy26_colab | gemma-4-12b QAT | Colab L4 jobs 6 | 114/130 → 116/130 | 3／5 | 0.73 | UNRESOLVED |
| **e4b_hardpy26** | **gemma-4-E4B QAT** | **Colab L4 jobs 2** | **61/130 → 84/130** | **8／31** | **0.000294** | **EFFECTIVE** |

兩批的題相同，但模型、jobs、P 臂版本（rc3.1 對 rc5-final）都不同，不是同一個實驗的兩半；「換成弱模型增益變大」是並列觀察，不是檢定。
