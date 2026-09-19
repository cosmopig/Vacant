# DECISION 2026-08-27（round140, Opus 5）：判準先寫死，再量

> 本檔的「判準」段落寫在**本輪任何數字產出之前**（時間戳：見下方 `date -u`）。
> 之所以先寫，是因為記憶裡的規則：量完再訂判準，數字高低兩個方向都會誘導你。
> 人類另外明講：不要為了「有成效」去挑對自己有利的設定。

本輪被交棒的任務（round139 指定 Opus）：**判斷證據夠不夠寫結論停下來**。

---

## 先寫死的判準（PRE-REGISTERED，量測之前）

### R1 — 新增分析：ON-final vs ON-initial（機制本身的效果）

讀 `gain_run.py` 得到的結構事實（不是假設）：

- `arm_off()` L179-184：`a = rng.choice(agents)`；`a.generate(task["prompt"], role="gen")`，1 呼叫。
- `arm_on()` L436-440：`worker = _route_agent(agents, rep, rng)`；
  `worker.generate(task["prompt"], role="gen", phase="initial")`，1 呼叫。
  **prompt 逐字元同一個 `task["prompt"]`。**
- L877-880：`initial_meets_demand = meets_demand(initial_code, hidden_check)`，
  **與最終 `truth` 同一把隱藏尺**。

⇒ ON 的每一列都自帶一組「同題、同草稿、只差有沒有跑審查＋修訂」的配對。
⇒ 這是全部證據裡**唯一零跨 run 風險**的配對：同一列、同一次抽樣、同一把尺。

**⚠ 它不等於 ON vs OFF。** 兩者的差別是 agent 挑選方式：
OFF 是 `rng.choice`（均勻亂挑），ON-initial 是 `_route_agent`（信譽路由）。
信譽路由**本身就是 Vacant 機制的一部分**。所以三層要分開講：

| 量 | 是什麼 | 呼叫數 |
|---|---|---|
| OFF | 均勻亂挑 1 個 agent，1 次生成 | 1 |
| ON-initial | 信譽路由挑 agent，1 次生成 | 1 |
| ON-final | ＋K=3 審查＋1 次修訂＋抽樣稽核 | 5 |

R1 只回答第三層對第二層的增益＝**「那 4 次額外呼叫有沒有把答案改對」**。

**判準（先寫）**：McNemar 精確雙尾檢定，證據單位＝discordant pair
（b=`improved`、c=`harmed`，取自 runner 自己記的 `revision_transition`）。
- p < 0.05 且 improved > harmed ⇒ 審查＋修訂這一段機制**可量到**增益。
- p ≥ 0.05 ⇒ **那 4 次呼叫對正確率沒有可量到的影響**，不論點估計往哪邊倒，照實寫。
- 兩種情況都要附 improved／harmed 的絕對數，不只寫 p。

### R2 — ON vs OFF5（等預算，判準 3）

沿用 round138/139 的做法，只把 n 推到目前可得的最大值。
**規則：只報 p 與方向，不重新詮釋。** 「分不出來」是答案，但必須寫成
「在 n=X 下量不到 ON 的優勢，檢定力有限」，不可以寫成「已證明兩者相等」。

### R3 — ON vs OFF（判準 2）：主要配對**事先指定**，不看數字再挑

存在兩種可能的配對，本輪**在看到任何數字之前**指定何者為主：

- **主要 =（a）`g_on371` 的 ON（n=167）vs `g_off371` 的 OFF**。
  理由：四項條件 sha（pool／instrument／calibration／request_policy）**逐項相同**，
  是唯一零條件落差的配對。它的結果已知：p=0.0574（round138 量的）。
- 次要 =（b）live run 的 ON（n≈365）vs `g_off371` 的 OFF。
  只有在能逐鍵驗證「`request_policy` 的差異**只有** `review_timeout_s`」
  且「OFF 臂確實 0 筆 review 角色呼叫」時才計算，且**標記為次要**。

**事先承諾：若（b）跨過 p<0.05 而（a）沒有，本輪不會據（b）宣告判準 2 達成。**
理由：看到哪一邊顯著才決定用哪一邊，正是人類禁止的「挑對自己有利的設定」。

### R4 — 三條「有成效」判準的達成門檻（先寫）

1. **量測有訊號**：OFF 失敗率落在 20–60%。此數字已由 round94 全庫定案
   （21.53%），本輪不重量、不重新詮釋。
2. **三臂有差異**：需要**某一個條件一致的配對**在 ON-vs-OFF 或 OFF5-vs-OFF
   上達到 p<0.05。ON-vs-OFF5 不算（那是判準 3 的題目）。
3. **等預算的答案**：ON vs OFF5 在等預算下有**跨獨立樣本方向一致**的答案。
   人類明講「打不贏也算有成效」⇒ 方向一致的「打不贏」可以算達成，
   但必須同時寫出檢定力限制。

**停下來寫結論的條件**：三條同時達成。**任一條沒達成就不停**，且要寫清楚缺什麼。

---

# 量測結果（判準寫死之後才產生）

工具：`ops/gain/analyze_paired.py`（round138 建、round139 驗過）。
本輪先重跑它自己的健全性檢查：`exact_mcnemar_p(11,3)=0.057373046875`、
`exact_mcnemar_p(4,7)=0.548828125`，與 round138/139 落盤值**逐位元相同** ⇒ 工具沒被動過。

落盤：`runs/_analysis_r140/`。

## 資料現況（2026-08-27 16:11 UTC）

`g_onoff5_371_r123_20260825`（PID 1875845，已跑 1 天 17:29:58）：

```
ON   臂：371/371 題已處理完 —— rows 365 ＋ infra_void 6   ⇒ ON 臂已完成
OFF5 臂：193/371 已處理     —— rows 190 ＋ infra_void 3
infra_void 合計 9（ON 6 ＋ OFF5 3），分別是 1.6%／1.6%，遠低於 SPEC 10% 門檻
```

⚠ 更正 round137/138 的紀錄：infra_void 現在是 **9 筆不是 3 筆**，且**多了第二種失敗模式**——
OFF5 的 3 筆全是 `HTTPError: HTTP Error 400: Bad Request`（重試 4 次），
與 ON 那 6 筆的 `finish_reason=length` 截斷是不同成因。round138 判斷「不是逾時、
是輸出 token 被 reasoning 燒光」對 ON 那 6 筆仍成立；OFF5 那 3 筆是新的，本輪未診斷。

## R1（先寫死的判準）：ON-final vs ON-initial —— 審查＋修訂那 4 次呼叫買到什麼

同一列內配對，零跨 run 風險。獨立重算與 runner 自己的 `revision_transition`
計數器**逐格相符**（`independent recount agrees: True`）。

```
n = 365
improved (b) = 4      harmed (c) = 0      stayed_correct = 297   stayed_wrong = 64
ON-initial  需求=產出  297/365 = 81.37%   CI95 [77.1, 85.0]
ON-final    需求=產出  301/365 = 82.47%   CI95 [78.2, 86.0]
McNemar 精確雙尾 p = 0.1250
```

**照 R1 先寫死的判準：p ≥ 0.05 ⇒ 那 4 次額外呼叫對正確率沒有可量到的影響。**
點估計 +1.10pp、且 harmed=0（機制一次都沒把對的改壞），但 4/365 沒有跨過門檻。

代價換算：ON 每題多花 4 次呼叫 × 365 題 = **1460 次額外呼叫換到 4 個額外正確交付
＝ 每多對一題要 365 次呼叫**。可捕捉的上限是 `stayed_wrong=64`（初稿錯、機制沒救回來），
轉換率 4/68 = 5.9%。

## 判準 2 的三個配對：**沒有一個跨過 p<0.05**

| 配對 | n | A | B | b/c | p | 條件 |
|---|---|---|---|---|---|---|
| **主要** ON(`g_on371`) vs OFF | 167 | 88.62% | 83.83% | 11/3 | **0.0574** | 四項 sha 全同 ✓ |
| 次要 ON(live) vs OFF | 362 | 82.60% | 79.28% | 23/11 | **0.0576** | request_policy 差 |
| OFF5(live) vs OFF | 187 | 81.28% | 77.01% | 12/4 | **0.0768** | request_policy 差 |

**照 R3 事先承諾**：主要配對 p=0.0574 沒過 ⇒ 不用次要配對翻案。（本輪次要配對
也沒過，所以這個承諾這次沒有被實際考驗到，但規則照樣先寫先算。）

`request_policy` 逐鍵比對，差異**只有** `review_timeout_s`（250 vs 60），
其餘 `timeout_s=600`／`retries=4`／`backoff_s=2.0`／`review_retries=2` 全同。
且 `calls.jsonl` 逐筆統計：`g_off371` 只有 `(OFF,gen)` 379 筆、live-OFF5 只有
`(OFF5,gen)` 966 筆——**OFF 與 OFF5 都不發 review 呼叫**，`review_timeout_s`
對這兩臂在結構上不適用。ON 臂則有 `review` 1118 筆，所以次要配對的 ON 側
確實是「另一種 ON 設定」，維持次要標籤是對的。

**值得記一筆**：n 從 167 翻倍到 362，p 幾乎沒動（0.0574→0.0576）——
點估計差距同時從 +4.79pp 縮到 +3.32pp。**這個效應沒有隨 n 往顯著收斂**，
差距縮小的速度跟精度提升的速度打平。不要期待「再多跑一點就會顯著」。

## 判準 3：ON vs OFF5（等預算）—— 兩個獨立樣本方向一致

```
本輪 live run   n=185  ON 80.54% vs OFF5 82.16%  b/c=4/7   p=0.5488  等預算 True（925 vs 925）
round138 v3 run n= 56  ON 69.64% vs OFF5 73.21%  b/c=4/6   p=0.7539  等預算 True（280 vs 280）
```

**等預算下 ON 沒有打贏 OFF5**，兩次獨立樣本點估計都略輸（-1.6pp、-3.6pp）。
照 R2 的措辭規則：這是「在 n=185 下量不到 ON 的優勢，檢定力有限
（discordant 只有 11 個）」，**不是「已證明兩者相等」**。

---

# 本輪的主要發現：ON 臂 60% 的預算花在一個從未觸發的關卡

這是本輪唯一沒被前面 14 輪做過、而且改變結論詮釋的東西。

人類的鐵律：「評審準確率單獨報。評審若接近亂猜，ON 的任何增益都不是機制帶來的。」

`summary.json` 寫 `reviewer_accuracy = 0.8136986301369863`。
ON-initial 的正確率是 297/365 = 0.8136986301369863。**逐位數相同。**
去 `rows.jsonl` 逐票重建混淆矩陣：

```
--- 生效的票（grounded_pass，就是決定 passed_review 的那個） ---
  n=1095   投 FAIL 只有 2 票（0.18%）
  TP=890  FP=203  FN=1  TN=1
  accuracy = 0.8137     always-PASS 基線 = 0.8137     差 = +0.0000
  初稿是錯的時候評審抓到 = 1/204 = 0.49%
```

**評審不是「接近亂猜」——它是一個常數函數。** 1095 票裡 1093 票投 PASS。
它的 81.37% 準確率**全部來自基線**，資訊量恰好 0.0000。
`passed_review` 在 365 列裡 **365 列都是 True**——這道關卡一次都沒有擋下任何東西。

## 這是 bug 還是設計？—— 是設計，但設計把訊號掐死了

`gain_run.py:477`：`grounded_pass = raw_pass or not confirmed`。
評審投 FAIL 只有在 `verify_review_counterexample` **用機器跑出反例確認**時才算數，
否則當棄權、判給原稿。所以要分兩層報：

```
--- RAW 評審主張（過關卡之前） ---
  投 FAIL 56 票（5.11%）   TP=870 FP=169 FN=21 TN=35
  accuracy = 0.8265   基線 0.8137   差 = +0.0128
  抓到錯初稿 = 35/204 = 17.16%      FAIL 票的精確度 = 35/56 = 62.50%

--- 過完關卡（實際生效） ---
  投 FAIL 2 票（0.18%）    差 = +0.0000    抓到錯初稿 = 1/204 = 0.49%
```

**原始評審是有訊號的**：56 次 FAIL 主張裡 35 次是真的錯（精確度 62.5%，
遠高於 18.6% 的亂猜基準），召回 17.2%。**關卡把它清成 0。** 為什麼：

```
verify_review_counterexample 的 status 分佈：
  review_not_fail          1039
  outside_input_contract     53   ← 56 個 FAIL 主張裡的 53 個死在這
  counterexample_confirmed    2
  unparseable_claim           1
```

**56 個 FAIL 主張有 53 個（94.6%）是因為反例的測資落在宣告的 input contract 之外
而被丟掉，不是因為主張錯。**

## 那 4 個 improved 不是評審做的

```
4 個 improved 的 passed_review = [True, True, True, True]
4 個 improved 的 selected_version = ['revised','revised','revised','revised']
selected_version 全體：initial 343、revised_both_visible_fail 17、revised 5
```

`gain_run.py:517` 是 `if passed_review and initial_visible_ok: code = initial_code`。
這 4 題 `passed_review=True`，所以它們走到 `revised` 的唯一路徑是
`initial_visible_ok=False` ⇒ 落到 `elif revised_visible_ok`。
⇒ **是「可見測資」抓到壞初稿、修訂者修好的，評審對這 4 題全部投了 PASS。**

## 合起來看：為什麼 ON 打不贏 OFF5

ON 每題 5 次呼叫，其中 **3 次是 review（1095/1834 = 59.7% 的預算）**，
而 review 這一關 `passed_review` 365/365 全 True ⇒ **它從未改變過任何交付**。
ON 實際起作用的只有「可見測資 ＋ 1 次修訂」，那買到 4/365。
OFF5 則把 5 次呼叫全部拿去做多樣化生成。

**這不是「Vacant 的想法錯了」，是「Vacant 的審查關卡在這個設定下沒有通電」。**
原始評審有 62.5% 精確度的訊號擺在那裡沒被用。

---

# 三條「有成效」判準的裁決（照 R4 先寫死的門檻）

| # | 判準 | 裁決 | 根據 |
|---|---|---|---|
| 1 | 量測有訊號（OFF 失敗率 20–60%） | **✓ 達成** | 本輪 n=362 配對上 OFF=79.28% ⇒ 失敗 20.72%，在窗口內（下緣）。round94 全庫 21.53%。 |
| 2 | 三臂有差異（某個配對 p<0.05） | **✗ 未達成** | 三個配對 p = 0.0574／0.0576／0.0768，**沒有一個跨過**。 |
| 3 | 等預算的答案 | **✓ 達成** | ON 沒打贏 OFF5，兩個獨立樣本方向一致（p=0.5488、p=0.7539）。人類明講「打不贏也算有成效」。 |

**⇒ 2 未達成 ⇒ 照 R4 先寫死的規則「任一條沒達成就不停」⇒ 本輪不寫結論、不停下。**

我沒有把三個 p≈0.06–0.08 的配對合併去湊顯著。它們**共用同一份 OFF 資料**，
事後合併是製造顯著，不是發現顯著。

## 還缺什麼、以及要不要繼續等（本輪的建議）

**建議：不要 kill，讓 OFF5 跑完。** 根據是投影計算（**這是投影不是結果**）：
OFF5-vs-OFF 目前 b=12/c=4 @ n=187，OFF5 跑到 371 時 discordant 大約翻倍：

```
b=12 c= 4 -> p = 0.0768   （現況）
b=18 c= 6 -> p = 0.0227
b=24 c= 8 -> p = 0.0070
b=20 c=10 -> p = 0.0987   （比例變差的情況）
```

⇒ **OFF5 跑完是目前唯一還可能讓判準 2 過關的路徑**，而且不用改任何實驗條件。
反之 ON-vs-OFF 那條已經到頂了：**ON 臂 371/371 已完成，n 不會再長**，p=0.0576 是終值。

剩餘時間估計：OFF5 還有 178 題；ON 臂 371 題花了 `wall_s=91960`（25.5 小時）
⇒ 約 248 秒/題 ⇒ **還要約 12 小時**。（這是用 ON 的速率推 OFF5，OFF5 也是 5 呼叫/題，
但沒有實測 OFF5 的速率，所以是估計不是量測。）

## 什麼條件下該推翻本輪的判斷

- OFF5 跑完後 OFF5-vs-OFF 仍 p ≥ 0.05 ⇒ 判準 2 在**現行設定下拿不到**，
  那時該面對的是「要不要改設定」而不是「再多跑一點」。
- 若 infra_void 比率升破 10%（目前 1.6%）⇒ 分母失真，上面所有數字要重算。
- 若有人改動 `gain_run.py` 或 relay 後端 ⇒ live run 前後段條件不一致，
  `request_policy` 的 sha 擋不住這種改動（它只記啟動參數）。

## 本輪**不做**的事，以及為什麼

- **不改 `verify_review_counterexample` 的 input-contract 判定。** 這是本輪最想動的旋鈕
  （53/56 的 FAIL 主張死在它手上），但：(a) live run 還在跑，中途改 runner 會讓
  同一個 run 的前後段條件不一致；(b) 改判定＝改實驗條件，要獨立 DECISION ＋
  植入缺陷測試證明放寬之後不會把 FP 一起放進來。**未驗證就改，是把慢的實驗換成壞的實驗。**
- 不 kill、不重啟任何 run；不刪任何 run 目錄。
- 不改任何實驗參數。
