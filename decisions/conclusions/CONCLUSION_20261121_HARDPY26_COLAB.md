# CONCLUSION 2026-11-21 — HARDPY26（`vacant do pi` rc3.1 對原生 pi，gemma-4-12b QAT，Colab L4 vLLM，exercism difficulty ≥4 的 26 題×5，jobs 6）

state＝**UNRESOLVED**，harness_changed_mid_run＝false，harness＝**3c74139794f1**（nonpy 分支；不是主 checkout 的 c7c6f5842dbf）。
數字來源：[`ops/redo/results/hardpy26_colab_REPORT.json`](../../ops/redo/results/hardpy26_colab_REPORT.json)。

## 0. 一句話

A 114/130（87.7%）、P 116/130（89.2%），b=3 c=5，p=0.73。方向略偏 P、差 1.5 個百分點、未達門檻；原生 87.7% 接近天花板（計畫的 UNRESOLVED 定義含「A 接近天花板」）。**不是負結果**，照預註冊停在這裡，不加 rep、不換題。

## 1. REPORT.md（原樣）

# hardpy26_vacantdo_rc3_pi_gemma12b_colab — UNRESOLVED

計畫 sha256 `a0ac681d29cc8586…`　完成 130/130 對（有效 130，infra_void 0）　產生於 2026-11-21T06:50:49Z

| 臂 | 通過／有效格 | 比率 | 平均嘗試數 | 平均 agent 牆鐘 | 逾時次數 | 驗收放行卻錯 | 平均模型呼叫 |
|---|---|---|---|---|---|---|---|
| A | 114/130 | 0.8769 | 1.0 | 343.8s | 6 | 0 | 10.9 |
| P | 116/130 | 0.8923 | 1.0 | 336.3s | 0 | 0 | None |

**配對（A 對 P）**：只有對照過 b＝3、只有處理過 c＝5、都過 111、都沒過 11；精確 McNemar 雙尾 p＝0.726562；差 1.54 個百分點；題數上淨正 4／淨負 1。

| rep | 對數 | 對照過 | 處理過 | b | c | p |
|---|---|---|---|---|---|---|
| 1 | 26 | 23 | 24 | 0 | 1 | 1.0 |
| 2 | 26 | 23 | 22 | 1 | 0 | 1.0 |
| 3 | 26 | 24 | 24 | 0 | 0 | 1.0 |
| 4 | 26 | 22 | 23 | 1 | 2 | 1.0 |
| 5 | 26 | 22 | 23 | 1 | 2 | 1.0 |

**驗收訊號對評分器（每一次嘗試）**：放行且對 230、放行卻錯 0、擋下卻對 0、擋下且錯 30。

引用規則：只有 state=EFFECTIVE 且 harness_changed_mid_run=false 的整批數字可以引用；引用時要同時講：模型、agent、題庫、對數、等預算的定義、mean_attempts。INCOMPLETE／UNRESOLVED 不是負結果。


## 2. 這個 state 的規則（逐字抄自 `prereg.states.UNRESOLVED`）

> 完成但 p ≥ 0.05（不論方向），或 A 接近天花板／地板。只記方向與大小；不是負結果。停下來回報，不准加 rep、換題、改時限之後再看一次。

## 3. 已知限制（逐字抄自 `prereg.known_limits`）

- P 臂是 rc3.1（redo/rc2 5d8892020，wheel sha256 490a90516a44…）裝在獨立 venv；config_dir 只複製 models.json，不載入 Vacant 的 pi 擴充：量的是零設定重開模式＋產品自己的驗收。
- P 的模型呼叫數 harness 量不到（usage=none），結案時用 ops/redo/analysis/p_model_calls.py 從 {logs}/vacant-work 補算。
- 選題規則只用 exercism 自己的 difficulty 標籤（≥4）與事先寫死的 sha256 排序；從沒給任何模型跑過。
- 數字不與其他批併表、不合併 p 值。
- 10 題與 exercism_py_unused 重疊（unused40 那批正在 1004 跑）：overlap 見 ops/redo/banks/exercism_py_hard.json。
- 可見測試＝評分器（visible_equals_grader）。
- jobs 6：vLLM 連續批次，6 格共用一張 GPU；兩臂受同樣壅塞，配對照常。KV 不夠時 vLLM 搶占重算，不回錯。
- 產品臂是 rc3.1 wheel（sha256 記在 launch metadata），裝在 VM 的 /opt/redo/rc_venv。
- Colab 單元用完或 VM 被回收：那就是 INCOMPLETE，照實報告，不改計畫。

另外（結案時補，不改計畫）：
- 產品臂 wheel：launch metadata 記 sha256 490a90516a44a48459577b107742494558818c183f6d578b695a2f93a415ca3b（＝~/dev/ops/rc3_dist），VM 上 /opt/redo/rc_venv。vLLM 0.30.0、google/gemma-4-12B-it-qat-w4a16-ct、max_num_seqs 16、max_model_len 262144。
- 3 個 b（只有 A 過）全在 ex_complex_numbers（r2/r4/r5）：P 的 3 次內層嘗試都撞產品預設的 600 秒單次上限（--attempt-timeout 600），最後一次 42/43 或 35/43 通過，A 單次跑 468–1370 秒後通過。這與 W3-5 Python 看到的現象一致（見那份結論 §5），是觀察、不是這批的結論。

## 4. 代價

- A：平均模型呼叫 10.9、平均 agent 牆鐘 343.8s、逾時 6 次；A 通過的 114 格裡 13 格單次跑超過 600 秒。
- P：`p_model_calls.py` 補算 130 格可算 **130**、UNKNOWN 0；平均模型呼叫 **12.4**（中位數 7.0）、平均內層嘗試 **1.3**；平均 agent 牆鐘 336.3s、外層逾時 0；169 次內層嘗試有 44 次撞 600 秒上限（25 格至少一次）。

## 5. 中斷與作廢紀錄

- 2026-11-21 01:03Z、01:35Z、01:38Z 三次前置發射在 VM 就緒前中斷（OOM 收掉本機背景程式、Colab session 上限），poll 沒有任何 STATUS 快照、沒有格子；保留在 redo_runs_colab/old/，不進結論。
- 正式批 02:11Z 發射（L4）、06:50Z 完成、07:02Z 取回 sha256 驗過後關 VM；infra_void 0。
- 同題的 1004 版（hardpy26_vacantdo_rc3_pi_gemma12b_1004）從未發射即撤回，撤回時看過本批前 11 對（兩臂全過），見該 WITHDRAWN.md。

## 同日結案的其他批（只並列，不合併）

| 批 | 後端／harness | P 是哪版 | 題 | A | P | b | c | p | state |
|---|---|---|---|---|---|---|---|---|---|
| unused40 | 1004 llama.cpp／c7c6f584 | rc1 | exercism 沒用過 40×5 | 184/200 | 192/200 | 1 | 9 | 0.0215 | EFFECTIVE |
| hardpy26 | Colab L4 vLLM／3c741397 | rc3.1 | 難 Python 26×5 | 114/130 | 116/130 | 3 | 5 | 0.73 | UNRESOLVED |
| W3-5 Python 確認 | Colab L4 vLLM／3c741397 | rc4 | 篩選入選 9×5 | 27/45 | 25/45 | 6 | 4 | 0.75 | UNRESOLVED |

三批的題、後端、產品版本都不同；這張表只讓讀者看到同一天的全部結果，不構成合併的估計，也不能只挑 unused40 單講。

## 後端速度（2026-11-21 結案後補；事後量測，不改結論）

用 `ops/redo/analysis/turn_latency.py` 從日誌量：每輪模型回應時間，是 pi session 裡每則 assistant 訊息與前一則訊息的時間差；P 內層撞上限的比例來自 restart 的 result.json；原生單次的數字來自 cell.json。本批是 **hardpy26**。

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
