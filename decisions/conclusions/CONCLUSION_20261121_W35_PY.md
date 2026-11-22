# CONCLUSION 2026-11-21 — W3-5 PYTHON（篩選 106 題 → 入選 9 題；`vacant do pi` rc4 對原生 pi，Colab L4 vLLM，9 題×5，jobs 6）

state＝**UNRESOLVED**（而且**檢定力不足**：入選 9 題 < 預註冊下限 15，照規則照跑），harness_changed_mid_run＝false，harness＝**3c74139794f1**（nonpy 分支）。
數字來源：確認批 [`ops/redo/results/w35py_confirm_REPORT.json`](../../ops/redo/results/w35py_confirm_REPORT.json)、篩選批 [`ops/redo/results/w35py_screen_REPORT.json`](../../ops/redo/results/w35py_screen_REPORT.json)。

## 0. 一句話（含完整分母）

- **篩選**：exercism Python 池 106 題，每題原生 pi 跑 2 次（A、A2 完全相同），106 題兩次都有效、void 0 題；2/2 過 **97** 題、1/2 過 **6** 題、0/2 過 **3** 題。篩選批整體 A 101/106、A2 99/106。
- **入選**：過 ≤1 次的 9 題全部入選（沒有超過 N=30，salt `:w35-py-2026-11-21` 沒用到排序）：ex_resistor_color_expert, ex_ocr_numbers, ex_palindrome_products, ex_camicia, ex_alphametics, ex_rectangles, ex_relative_distance, ex_kindergarten_garden, ex_tournament。
- **確認**（9 題 × 5 次全新 rep）：A 27/45、P 25/45，b=6 c=4，p=0.75。**方向是 A 略多**（差 −4.4 個百分點），未達門檻，檢定力不足。
- 原生本來就穩過的 97 題：這批**沒有量** P（設計上只在入選題上跑確認），所以對那 97 題既不能說有增益、也不能說沒多花——只能說它們不在這次的問題範圍內。

## 1. 確認批 REPORT.md（原樣）

# w35_vacantdo_rc4_pypool_colab — UNRESOLVED

計畫 sha256 `69377a9843ddedb9…`　完成 45/45 對（有效 45，infra_void 0）　產生於 2026-11-21T11:07:09Z

| 臂 | 通過／有效格 | 比率 | 平均嘗試數 | 平均 agent 牆鐘 | 逾時次數 | 驗收放行卻錯 | 平均模型呼叫 |
|---|---|---|---|---|---|---|---|
| A | 27/45 | 0.6 | 1.0 | 884.5s | 9 | 0 | 13.7 |
| P | 25/45 | 0.5556 | 1.0 | 1079.2s | 0 | 0 | None |

**配對（A 對 P）**：只有對照過 b＝6、只有處理過 c＝4、都過 21、都沒過 14；精確 McNemar 雙尾 p＝0.753906；差 -4.44 個百分點；題數上淨正 1／淨負 2。

| rep | 對數 | 對照過 | 處理過 | b | c | p |
|---|---|---|---|---|---|---|
| 1 | 9 | 6 | 6 | 1 | 1 | 1.0 |
| 2 | 9 | 5 | 3 | 2 | 0 | 0.5 |
| 3 | 9 | 6 | 6 | 1 | 1 | 1.0 |
| 4 | 9 | 6 | 4 | 2 | 0 | 0.5 |
| 5 | 9 | 4 | 6 | 0 | 2 | 0.5 |

**驗收訊號對評分器（每一次嘗試）**：放行且對 52、放行卻錯 0、擋下卻對 0、擋下且錯 38。

引用規則：只有 state=EFFECTIVE 且 harness_changed_mid_run=false 的整批數字可以引用；引用時要同時講：模型、agent、題庫、對數、等預算的定義、mean_attempts。INCOMPLETE／UNRESOLVED 不是負結果。


## 2. 篩選批 REPORT.md（原樣）

# screen_native_pypool_colab — UNRESOLVED

計畫 sha256 `f4efbe63249f687e…`　完成 106/106 對（有效 106，infra_void 0）　產生於 2026-11-21T06:20:57Z

| 臂 | 通過／有效格 | 比率 | 平均嘗試數 | 平均 agent 牆鐘 | 逾時次數 | 驗收放行卻錯 | 平均模型呼叫 |
|---|---|---|---|---|---|---|---|
| A | 101/106 | 0.9528 | 1.0 | 222.6s | 4 | 0 | 12.6 |
| A2 | 99/106 | 0.934 | 1.0 | 209.0s | 1 | 0 | 8.1 |

**配對（A 對 A2）**：只有對照過 b＝4、只有處理過 c＝2、都過 97、都沒過 3；精確 McNemar 雙尾 p＝0.6875；差 -1.89 個百分點；題數上淨正 2／淨負 4。

| rep | 對數 | 對照過 | 處理過 | b | c | p |
|---|---|---|---|---|---|---|
| 1 | 106 | 101 | 99 | 4 | 2 | 0.6875 |

**驗收訊號對評分器（每一次嘗試）**：放行且對 200、放行卻錯 0、擋下卻對 0、擋下且錯 12。

引用規則：只有 state=EFFECTIVE 且 harness_changed_mid_run=false 的整批數字可以引用；引用時要同時講：模型、agent、題庫、對數、等預算的定義、mean_attempts。INCOMPLETE／UNRESOLVED 不是負結果。


## 3. 這個 state 的規則（逐字抄自 `prereg.states.UNRESOLVED`）

> 完成但 p ≥ 0.05（不論方向），或 A 接近天花板／地板。只記方向與大小；不是負結果。停下來回報，不准加 rep、換題、改時限之後再看一次。

完整分母的要求（逐字抄自 `prereg.denominator`）：

> 結論必須報完整分母：篩選幾題、各題原生 2 次過幾次（2/2、1/2、0/2 各幾題）、void 幾題、入選幾題；「原生本來就穩過的題沒有增益也沒有多花」與「入選題上的差距」分開講，不得只報確認批的差距。

## 4. 已知限制（逐字抄自 `prereg.known_limits`）

- P 臂是 rc4 wheel（sha256 28e5480c84aa…，~/dev/ops/rc4_dist），裝在 VM 的 /opt/redo/rc_venv；config_dir 只複製 models.json。
- 被選中的題原生在確認批會往上回歸，縮小差距、對 P 不利。
- P 的模型呼叫數 harness 量不到（usage=none），結案時用 p_model_calls.py 補算。
- jobs 6：兩臂受同樣壅塞，配對照常。
- 數字不與其他批併表、不合併 p 值。
- 入選只有 9 題（< 15）：照預註冊照跑，檢定力不足，結論要寫明。

## 5. A 逾時 9 次、P 外層逾時 0 次：查過日誌（事後、非預註冊）

review 提出的猜測是「這幾題需要單次超過 600 秒，被產品的 3×600 切法卡住」。逐格查了 harness 的 cell.json（A）與產品的 restart result.json（P）：

- A 通過的 27 格裡有 **10 格**單次跑超過 600 秒（736–1640 秒）才通過；A 的 9 次逾時是 1800 秒整批用完。
- P 的 100 次內層嘗試有 **63 次**撞產品預設的 600 秒單次上限（`vacant do --attempt-timeout` 預設 600；第三次只剩約 480 秒），45 格裡 30 格至少撞一次。P 的「外層逾時 0」只是因為產品自己在 1800 秒內收尾，不代表沒被時間卡住。
- 6 個 b（只有 A 過）裡有 **5 個** A 單次跑 841–1640 秒才過、同一對 P 的內層嘗試幾乎全部撞 600 秒（ex_ocr_numbers r2/r4、ex_rectangles r1/r3/r4；剩下 ex_kindergarten_garden r2 的 A 是 579 秒，P 三次都逾時）。
- 反方向：4 個 c 裡 ex_tournament r1、ex_kindergarten_garden r3 是 P 第一次嘗試在 600 秒內就過、A 跑 1100–1300 秒卻沒過。

**寫進已知限制**：在需要單次長時間探索的題上，產品預設的 600 秒單次上限會切斷原本 1800 秒內做得完的嘗試，壓低 P。這是證據支持的觀察，但沒有對照實驗（沒有跑過 --attempt-timeout 900 或不切的 P），所以**不能**說「換掉切法 P 就會贏」。同樣的現象在 hardpy26（3 個 b 全在 ex_complex_numbers，P 三次都撞 600 秒）也看得到。這是產品預設值的候選缺陷，之後要改需先另外預註冊一批量它，不回頭改這批。

## 6. 代價

- A：平均模型呼叫 13.7、平均 agent 牆鐘 884.5s、逾時 9 次。
- P：`p_model_calls.py` 補算 45 格可算 **45**、UNKNOWN 0；平均模型呼叫 **21.0**（中位數 18）、平均內層嘗試 **2.222**；平均 agent 牆鐘 1079.2s。

## 7. 中斷與作廢紀錄

- 篩選批 02:38Z 發射、05:37Z 完成；自動取回的 RUN.json 檢查因 `pipefail`＋`grep -q` 的 SIGPIPE 假失敗（tarball 完整、sha256 與 BATCH_DONE 相符），之後手動解開；腳本已修（b4f834d6c）。篩選 VM 已被 Colab 回收。
- 確認批計畫 cab3a8fdc 在第一通模型呼叫前 commit；06:24Z 發射、11:07Z 完成、11:15Z 取回並關 VM；infra_void 0。

## 同日結案的其他批（只並列，不合併）

| 批 | 後端／harness | P 是哪版 | 題 | A | P | b | c | p | state |
|---|---|---|---|---|---|---|---|---|---|
| unused40 | 1004 llama.cpp／c7c6f584 | rc1 | exercism 沒用過 40×5 | 184/200 | 192/200 | 1 | 9 | 0.0215 | EFFECTIVE |
| hardpy26 | Colab L4 vLLM／3c741397 | rc3.1 | 難 Python 26×5 | 114/130 | 116/130 | 3 | 5 | 0.73 | UNRESOLVED |
| W3-5 Python 確認 | Colab L4 vLLM／3c741397 | rc4 | 篩選入選 9×5 | 27/45 | 25/45 | 6 | 4 | 0.75 | UNRESOLVED |

三批的題、後端、產品版本都不同；這張表只讓讀者看到同一天的全部結果，不構成合併的估計，也不能只挑 unused40 單講。

## 後端速度（2026-11-21 結案後補；事後量測，不改結論）

用 `ops/redo/analysis/turn_latency.py` 從日誌量：每輪模型回應時間，是 pi session 裡每則 assistant 訊息與前一則訊息的時間差；P 內層撞上限的比例來自 restart 的 result.json；原生單次的數字來自 cell.json。本批是 **W3-5 Python**。

| 批 | 後端 | 每輪回應 中位／平均／p90（秒） | P 內層撞 600 秒 | 原生單次中位牆鐘、逾時 |
|---|---|---|---|---|
| confirm1c | 1004 llama.cpp，jobs 1 | 5.6／11.8／21.8 | 118/328＝36% | 367 秒、19/170 |
| unused40 | 1004 llama.cpp，jobs 1 | 1.3／5.4／10.9 | 14/225＝6% | 12 秒、3/200 |
| hardpy26 | Colab L4 vLLM，jobs 6 | 6.7／24.5／57.9 | 44/169＝26% | 118 秒、6/130 |
| W3-5 Python | Colab L4 vLLM，jobs 6 | 11.9／43.8／91.7 | 63/100＝63% | 791 秒、9/45 |

讀法：
- Colab（L4、vLLM 0.30.0、jobs 6）上，每輪的**中位數**和本機差不多，但**平均與 p90 是本機的 2–4 倍**：長上下文那幾輪特別慢，牆鐘由這段尾巴決定。
- 所以在 Colab 上，產品預設的單次 600 秒能做的輪數比本機少，P 內層撞上限的比例也較高。本批量到的是「產品預設值在這個後端上」的表現，不能直接讀成「重開機制有沒有用」。
- 撞上限不等於沒效：confirm1c 在本機也有 36% 的內層嘗試撞上限，照樣 EFFECTIVE。
- 單次上限本身的效果由預註冊的 atimeout（`--attempt-timeout` 900 對 600）量，不從這張表推。
