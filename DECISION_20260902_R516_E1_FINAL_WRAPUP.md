# DECISION R516（2026-09-02 21:00 UTC，Fable 5.1 稽核輪）：E1 收官——照 R483 §3d 寫死的判準裁決

稽核輪，**沒改任何實驗程式碼**，沒起任何 run，沒動 E1 目錄裡的原始資料。
判準是 `DECISION_20260902_R483_E1_A3_INTERIM_AUDIT.md` §3d 在 E1 跑完之前寫死的，本輪只套用。

所有數字可用下面這份終態資料逐字重算（run 已結束，PID 2572085 不存在，不需要另外凍結快照）：

| 資料 | 行數 | sha256 前 8 碼 |
|---|---|---|
| `runs/g_r441_gemma_only_mbpp_b/rows.jsonl` | 525 | `440d973c` |
| `runs/g_r441_gemma_only_mbpp_b/calls.jsonl` | 1986 | `3d24b73d` |
| `runs/g_r441_gemma_only_mbpp_b/notes.jsonl` | 13（1 probe＋12 infra_void） | `06fd2a71` |

重算腳本與輸出：`runs/g_r441_gemma_only_mbpp_b/analysis_round516/audit_r516.py`、`audit_r516.json`
（R483 那輪只留了 JSON 沒留腳本，本輪把腳本一起 commit，下次不必再重建）。

## 0. 收官訊號：`run_complete` 永遠是 false，這不是「還沒跑完」

`summary.json` 頂層 `run_complete=false`、`arms.ON.complete=false`，而 OFF／OFF5 都是 `complete=true`。
`gain_run.py:1040` 定義 `complete = n_void==0 and processed==len(tasks)`；ON 臂 `n_void=12` 是單調計數器，
**這個 run 的 `run_complete` 結構上不可能變 true**。R483 §3d 開頭寫的觸發句「E1 `run_complete=true` 後的 fable 輪」
以為旗標會翻，那個前提對這個 run 是錯的（round515 的 commit 訊息已指出）。本輪採用的收官訊號：

- `pgrep -af gain_run` 沒有 E1 的行程；
- 三臂 `processed==179==len(tasks)`；
- `rows.jsonl` 三臂 `i` 的最大值都是 179。

⚠ **一個要更正的說法**：交棒句裡寫「void 的題目後來被重試補上了」——**不對**。`processed` 在 `try` 之前就 `+=1`
（`gain_run.py:1076`），`InfraVoid` 分支只記 note、不寫 row、`continue`。所以 ON 臂 rows 是 **167 行不是 179**，
12 個 void 題在 ON 臂**沒有資料**，`i` 序列缺口 {10,21,79,102,127,141,146,151,156,162,171,173} 與 notes.jsonl 的 12 個
task_id **逐一對得上**（`gaps_equal_void_notes=true`）。ON 的所有比率分母是 167，配對分母也是 167。

## 1. 對帳

- `calls.jsonl` 1986 筆：`model_configured`＝`model`＝`gemma-4-12b-it-qat` **1986/1986**。伺服端回報的 `meta.model` 仍然
  只有 preflight 那 1 筆有（R483 §5 給 opus 的落盤缺口，本輪未修，也不該由稽核輪修）。
- 失敗呼叫 55 筆（TimeoutError 49、HTTPError 6），54 筆在 review、1 筆在 revise；attempt=2 共 43 筆。
- `rows.jsonl` 的 `err` 欄非空 149 筆，**全部**是 `sandbox_check_failed`（unexpected_err 0/525）。
- 三臂按 `i` 對齊題目 **0 筆不一致**；`(arm, task_id)` 無重複。
- void：12 筆全在 ON 臂、全部是 review 階段「重試 2 次仍失敗」（timeout 10、HTTP 400 2）。
  **ON void 率 12/179＝6.70%**（R483 期中 3.0%）。

## 2. 三臂終態（n=179；ON 量到 167）

| 臂 | rows | meets | 通過率 | 失敗率（Wilson 95%） | accepted | leaked | void | calls |
|---|---|---|---|---|---|---|---|---|
| OFF | 179 | 122 | 68.16% | **31.84%** [25.46, 38.99] | 179 | 57 | 0 | 179 |
| ON | 167 | 122 | 73.05% | 26.95% [20.79, 34.14] | 136 | 14 | 12（6.70%） | 856 |
| OFF5 | 179 | 132 | 73.74% | 26.26% [20.36, 33.15] | 179 | 47 | 0 | 895 |

配對（McNemar 精確二項，`vacant.research.mcnemar_exact`）：

| 配對 | n | b（前者對後者錯） | c | p | 配對差 |
|---|---|---|---|---|---|
| **ON vs OFF5** | 167 | 11 | 12 | **1.0000** | **−0.60pp** |
| ON vs OFF | 167 | 17 | 7 | 0.0639 | +5.99pp |
| OFF5 vs OFF | 179 | 12 | 2 | **0.0129** | +5.59pp |

期中（301 行）→ 終態：ON vs OFF5 從 b=8 c=5 p=0.581（+3.06pp）走到 b=11 c=12 p=1.0（−0.60pp）——期中之後新增的
69 對是 b=3 c=7，方向翻了。**這是第二個乾淨 run（void 在窗內、三臂交錯同 seed）給出「ON 不贏 OFF5」**，
第一個是 `g_r356_3arm_20260830`（R437：b=5 c=2 p=0.4531）。

## 3. 評審票（E1：gemma 評 gemma 初稿；真值＝`initial_meets_demand`）

n=167 題 × 3 票＝501 票，評審模型 501/501 都是 `gemma-4-12b-it-qat`。

| 層 | TP | FP | FN | TN | accuracy | always-PASS 基線 | **(TN−FN)/n** | 叢集 bootstrap 95% | FAIL 票精確度 |
|---|---|---|---|---|---|---|---|---|---|
| raw_pass | 246 | 66 | 102 | 87 | 0.6647 | 0.6946 | −2.99pp | [−11.38, +5.59] | 46.0% |
| **grounded_pass** | 328 | 112 | 20 | 41 | 0.7365 | 0.6946 | **+4.19pp** | **[+0.00, +8.58]** | 67.2% |

方法（與 R483 逐字相同）：`vacant.research.boot_ci(rows_ON, stat, n_boot=4000, seed=483)`，重抽單位＝ON 列（題），
stat＝pooled 票的 100·(TN−FN)/n，百分位 2.5／97.5。**本輪先在 `/dev/shm/r483/rows.jsonl`（sha `eb324b06`）上驗過
這個呼叫逐位重現 R483 的 [+0.00, +12.59]（grounded）與 [−12.59, +13.27]（raw）**，所以「同一把尺」不是口頭說的。

期中 → 終態：grounded 點估計 **+6.12 → +4.19pp**，區間 [0, 12.59] → [0, 8.58]。n 從 98 題加到 167 題，
點估計往 0 縮、區間變窄、下界仍卡在 0。

下界「＝0」是什麼意思（非預註冊的附帶量，不進判準、只是說明）：seed 483 的 2.5 百分位未四捨五入就是 0.0；
bootstrap 分佈落在 ≤0 的比率 2.62%；換 seed 1–5 的下界＝[+0.20, 0.00, 0.00, 0.00, 0.00]。
也就是說它是「剛好貼在 0 上」，不是「深深跨過 0」——但 §3d 寫的是嚴格 `> 0`，而且點估計那一條（>+5pp）
**獨立地**也不成立，換 seed 也救不回來。

`verify_review_counterexample` status：review_not_fail 312、counterexample_confirmed 61、candidate_passed_claim 64、
unparseable_claim 33、outside_input_contract 31。revision_transition：stayed_correct 116、stayed_wrong 45、
**improved 6、harmed 0**（r356 是 1 improved）。

## 4. 裁決（R483 §3d，逐條）

**第 4 條（推翻條件）先看**：ON void 率 6.70% ≤ 10% ⇒ **推翻條件沒有觸發**，第 1–3 條正常適用，不是「不可裁」。

**第 1 條**：grounded (TN−FN)/n 叢集 bootstrap 95% 下界 **0.00，不 > 0**；點估計 **+4.19pp，不 > +5pp**。
兩個條件都不成立 ⇒ **不寫附註進 CONCLUSION**。

**第 2 條**（下界 ≤ 0）⇒ 照 §3d 原句寫：**「n=179 仍分不出 0」**。`CONCLUSION_20260830_G_EXPERIMENT.md` **不動**。
補一句照實的解讀（不是判準的一部分）：R483 §3b 的結論「家族歸因不成立、同一個 gemma 評審在 r356 是 +0.00pp」
仍然站得住，而 E1 把 n 加到 167 題之後點估計從 +6.12 縮到 +4.19，**沒有**朝「真發現」的方向走。
R440B L2 的門檻（> +5pp）在 E1 條件下沒過。

**第 3 條**（ON vs OFF5 另裁）：McNemar **p=1.0000**（b=11 c=12，n=167，配對差 −0.60pp）⇒
**等預算下 Vacant 的機制沒有勝過 self-consistency。答案是「沒有贏」**，而且不是邊緣沒贏，是 discordant pair
幾乎對半分。這是 R440C P3 翻盤窗的後半，沒開。

## 5. R440C 預註冊預測收官打分

| 預測 | 期中（R483） | 終態 | 裁決 |
|---|---|---|---|
| P0 ON void <35% | 3.0% ✓ | 6.70% | **✓** |
| P1 OFF 失敗率 >26.44%（R440B L0 窗 35–60%） | 33.3% ✓／不在窗 | 31.84%，Wilson [25.46, 38.99] | **✓ 過 26.44%；不在 35–60% 窗**（點估計差 3.2pp，區間上緣進窗） |
| P2 評審準確率 ≈ 基線 ±2pp | +6.1 ✗ | +4.19pp，區間 [0, 8.58] | **點估計在 ±2pp 之外，但區間含 ±2pp 帶** ⇒ 既不能說「≈基線」也不能說「顯著高於」；照 §3d 就是「分不出 0」 |
| P3 評審顯著上升 **且** ON>OFF5 顯著 | ✗ | 前半下界=0、後半 p=1.0 | **✗ 兩半都不成立** |

## 6. 描述性數字（非預註冊，不當結論用；供下一個 DECISION 引用時知道在哪）

- 漏出（accepted 且 not meets）配對 ON vs OFF5，n=167：ON 14 vs OFF5 44，b=1 c=31，p=1.5e-8。
  ON 拒收 31 題、**拒收裡答案其實是對的＝0/31**。方向與 CONCLUSION round342 那節（「唯一顯著對 ON 有利的是漏出量，
  但功勞在可見測試閘」）一致，本輪沒有重做拆帳。
- ON vs OFF p=0.0639、OFF5 vs OFF p=0.0129：五倍預算下顯著贏 OFF 的還是 OFF5，跟 r356／371-era 同型。

## 7. 沒做的事（照實）

- 沒改 `CONCLUSION_20260830_G_EXPERIMENT.md`（§3d 第 2 條分支，規定不動）。
- 沒改任何實驗碼、分析碼（`ops/gain/*`、`vacant/*`）；沒起 run；沒殺任何行程；沒動 1004；沒查 win1003 B 軌；
  沒寫 `NEXT_MODEL=local`。
- 沒重放 r356 在修好量尺下的評審票（R483 §4 同一條，仍需改分析碼）。
- 沒做「E1 與 r356 合併」的跨 run 比較——兩個 run 量尺版本不同（R393 前後），合併沒有意義。
- 沒對 12 個 void 題做 void-proof bound（`analyze_void_bounds.py` 規則 A）——6.70% 在 §3d 自己的 10% 門檻內，
  §3d 沒要求；若有人要用「最壞情況」口徑，12 題全翻也只是 b 或 c 各 +12，寫在這裡讓下一輪不用猜。
- `boot_ci` 的百分位用的是 `round(p/100·(B−1))` 取索引，沒有插值；本輪沒換成別的百分位定義，因為換了就不是 R483 那把尺。

## 8. 給 opus 輪的提案（不是本輪做的）

- 同 R483 §5：runner 每筆呼叫落盤伺服端 `model`；`finalize()` 的 `complete` 定義改成區分「void 但已處理完」與「還沒處理完」
  （例如另加 `terminal: processed==len(tasks)`），否則每個有 void 的 run 都會永遠 `run_complete=false`，
  下游的自動收官觸發全部失效（這輪就是靠人讀 commit 訊息才收官的）。
- E1 的答案已經是「同族評審在 n=167 下分不出 0、等預算不贏」。R440B 梯子的下一格是 L1（有反例才修）或 L2（異質評審），
  兩者都要新 run；哪一格先跑是人類／opus 的事，本輪不排。
