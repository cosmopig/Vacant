# DECISION round438：難題子集配對檢定（零成本）＋ revise 機制反事實——
把「打不贏」從統計結論推進到機制解釋

**2026-09-01 UTC ~05:16-06:10，Sonnet 5。**

## 背景

round437 確認決定性 run（`runs/g_r356_3arm_20260830`，179/179 全臂 processed）
已經跑完，ON vs OFF5 等預算配對檢定在完整資料上不顯著（typing 修正版
p=0.4531，raw 版 p=0.7905，兩者連方向都不一致）。round437 留下三個延伸方向，
**方向 3（難題子集）與方向 2（reviewer 準確率／revision_transition 相關性）
都能用已收集的資料零成本完成**，本輪把兩個都做了，因為它們互相補強：
方向 3 回答「有沒有差異」，方向 2 回答「為什麼沒有」。

## 方向 3：難題子集配對檢定

新增 `ops/gain/analyze_hard_subset.py`（唯讀、零成本，離線重放
`calls.jsonl`，邏輯與 `reanalyze_typing_fix_r393.py` 一致但抽成可重用的
`compute_typing_fixed_truth()`）。

**難題子集定義（先於量測寫死）**：task_id 落在 **OFF 臂**（最便宜、無審查
機制、typing 修正版）hidden_check 判 False 的集合。只依賴 OFF 臂本身，不
依賴 ON/OFF5 自己的結果，避免「用結果定義子集」的循環論證。

```
OFF 臂可重放題數 = 172，難題子集大小 = 42（24.4%）

難題子集上 ON vs OFF5（n_paired = 21，因為 ON/OFF5 各自的可重放集合
（113／147 題，見下）與難題子集取交集後只剩 21 題——ON 需要 initial+
revision 兩段候選碼都在，OFF5 需要 5 份 gen 候選碼都在，任一段缺失就
被排除，這跟 round393 起就有的已知方法論限制一致，不是本輪新引入的漏洞）

ON    需求=產出  6/21 = 28.57%  CI95 [13.8, 50.0]
OFF5  需求=產出  6/21 = 28.57%  CI95 [13.8, 50.0]
discordant：只有 ON 對 b=1，只有 OFF5 對 c=1（證據單位 = 2）
McNemar 精確雙尾 p = 1.0000
```

**點估計完全相同（28.57%＝28.57%），只有 2 個 discordant pair。** n=21 統
計檢定力很低（能分辨的效應量遠大於任何合理的真實 gap），**不能單獨當成
「兩臂在難題上也沒差異」的證據**——但它是這個資料集能給出的全部證據，
且證據單位（2）遠比全資料集的（7-14）少，繼續在**同一批**資料上換分析
角度不會再擠出更多資訊。

## 方向 2：revise 機制的反事實分解

重跑 `ops/gain/analyze_review_gate.py` 與 `ops/gain/analyze_revise_counterfactual.py`
（兩支既有唯讀工具，此前只在 round56/72 附近的小 n smoke run 上跑過，
**這是第一次在完整 179 題決定性 run 上跑**，且 `analyze_revise_counterfactual.py`
用現行 `_GAIN_ALLOWED_IMPORTS`（已含 typing）重算 meets_demand，等同 typing
修正版口徑）。

### 評審關卡（`analyze_review_gate.py`，n=339 票、113 題 ON）

```
RAW 評審主張（關卡之前）：accuracy=0.7316，always-PASS 基線=0.7522，差=-0.0206
GROUNDED 生效票（決定 passed_review）：accuracy=0.7552，always-PASS 基線=0.7522，差=+0.0029

revision_transition：stayed_correct=85  stayed_wrong=27  improved=1  harmed=0
```

生效評審票的準確率**幾乎等於「無腦全過」基線**（+0.29pp），這與 round437
記錄的 `reviewer_accuracy=0.7552` 全域數字一致，但這裡看到的是**逐票**層級
——評審對關卡放行後的判定幾乎不比常數函數多帶訊號。113 題裡，revision
把錯的改對的只有 **1 題**，改對的改錯的 **0 題**。

### revise 反事實分解（`analyze_revise_counterfactual.py`，n=113）

```
categories: no_opportunity=93  dead_branch=13  discarded_harm_avoid=6  other=1
discarded_win=0（未出現在輸出中＝計數為 0）

initial_hidden_pass=93/113=82.3%
revised_hidden_pass=89/113=78.8%
```

**這是本輪最重要的數字**：如果系統不做「選 initial 還是 revised」的
選擇、盲目一律採用 revised 版本，hidden_check 通過率會從 82.3% **掉到**
78.8%（-3.5pp）——單獨看，revise 這一步本身是淨負值。系統目前的選擇邏輯
（`passed_review and iv` 就用 initial，否則用 revised）把這個負值大部分
擋掉了：`discarded_harm_avoid=6` 是「initial 對、revised 錯，選擇邏輯正確
地留住 initial」；而 `discarded_win`（initial 錯、revised 對、卻選了
initial）在 113 題裡**一次都沒發生**——也就是說，選擇邏輯沒有錯殺任何
一次 revise 帶來的真正修正，因為 revise 幾乎從來不產生真正的修正
（113 題裡只有 1 題的 `revision_transition=improved`，與上面 review_gate
的數字完全對得上）。

## 為什麼「打不贏」不是量測噪音——機制上的解釋

把三層證據疊起來看：

1. **評審幾乎是常數函數**（生效準確率只比全過基線高 0.29pp）——它很少
   真的抓到錯，也很少誤殺對的。
2. **revision 本身淨負值**（82.3%→78.8%，-3.5pp）——即使評審放行了
   revision，寫出來的修訂版本並不比初稿可靠。
3. **選擇邏輯只能防守、不能得分**（discarded_harm_avoid=6 保護了系統
   不被 revision 拖累，但 discarded_win=0，代表**沒有任何一次**修正
   是靠這個機制才被保留下來的；round411/430-437 反覆量到的「ON 不比
   OFF5 好」，根源就是 ON 唯一比純 self-consistency 多出來的動作
   （review→revise）在這批資料上幾乎不產生淨修正）。

**這把「等預算下打不贏」從一個統計上的空結論，往前推進了一步：不是
「效應量太小量不到」，是「這個特定機制設定（審查關卡＋單輪修訂）在
這批 worker／這批題目上，可歸因的淨修正筆數趨近於零」**。這與難題子集
上兩臂點估計完全相同（方向 3）互相印證——如果 revise 幾乎不產生淨修正，
難題子集（正是最需要修正的地方）兩臂表現一樣，正是機制解釋預測會發生
的結果，不是巧合。

## 對三條「有成效」判準

無變化（round437 已收尾）：
1. 量測有訊號 ✓
2. 三臂有差異：沒有統計上可分辨的差異，**本輪補上機制解釋**：revise
   淨效應趨近於零，不是量測力不足的假象
3. 等預算答案：「打不贏」——本輪把這個答案的**原因**釘下來

## 沒做的事

- 沒有修改 `ops/gain/gain_run.py` 或任何跑分邏輯——本輪純分析，不碰
  已經跑完、資料已耗盡的決定性 run
- 沒有啟動新的長跑 run。**這是本輪明確的判斷取捨**：round437 列的方向 1
  （加大 n 的新 run）成本是另一輪 35-70 小時，而難題子集（方向 3）與
  機制分解（方向 2）已經給出一致的解釋性答案——花 35-70 小時去把難題
  子集的 n 從 21 擴大到 ~40，不太可能推翻「revise 淨效應趨近零」這個
  機制發現（機制發現不依賴難題子集的統計檢定力，它是對**已收集資料**
  的重新拆解）。如果未來要繼續深挖，更有效益的方向是**改機制設計**
  （例如換 revise 觸發條件、換更強的評審模型）再跑新 run 驗證改動後
  是否翻盤——那是設計變更，需要新的 DECISION，不是本輪的範圍。
- 沒有把「revise 淨效應趨近零」推廣成「Vacant 整個機制沒用」——這批
  資料只驗證了「審查關卡＋單輪修訂」這一種具體設計在這批 worker 池
  （qwen3.6-35b-a3b + gemma-4-12b-it-qat）上的效果，換 worker 池或改
  設計都可能翻盤，那需要新的實驗條件、新的 DECISION

## 推翻條件

若未來某輪改了 revise 觸發條件或評審模型並重新量到 `discarded_win>0`
且 `revised_hidden_pass > initial_hidden_pass`（revise 由淨負值轉正），
「revise 淨效應趨近零」這個機制結論需要更新為「舊設計無效，新設計
（見對應 DECISION）有效」。

## 下一輪該做什麼

主線問題（等預算下 Vacant 打不打得贏 self-consistency）**已經有統計
結論＋機制解釋兩層**，不需要再重跑同一批資料的配對分析或子集分析。
有意義的下一步（人類交辦「沒有做完了這個狀態」），三選一，**需要
sonnet/opus 判斷選哪個**：

1. **改機制設計再驗證**：既然 revise 淨效應趨近零，值得討論要不要
   改觸發條件（例如只在評審給出具體反例時才 revise，而不是每次都
   revise）或換更強的評審模型，然後跑一個新的小 n 驗證性 run 看
   `discarded_win` 會不會轉正——這是設計決策，會改變 `gain_run.py`
   的邏輯，要記新 DECISION。
2. **收尾**：三條「有成效」判準都已滿足（round437），本輪又補上機制
   解釋，這條實驗線可以視為**回答完整**（不是「做完了」，是「這一批
   問題答完了」）。下一輪可以把這份機制發現整理進一份對外可讀的總結
   （例如更新 `CONCLUSION_20260830_G_EXPERIMENT.md`），而不是繼續在
   同一個資料集上換角度重跑。
3. **換一個不同的實驗變因**：例如不同的任務分布（不只 MBPP+）或不同
   的等預算比例，看「revise 淨效應趨近零」是不是這個特定題庫／這個
   特定預算比例才有的現象。

## 落盤與驗證

```
git add -A ops/gain/analyze_hard_subset.py \
  DECISION_20260901_R438_HARD_SUBSET_AND_REVISE_MECHANISM.md
git commit -m "round438: hard-subset paired test (n=21, identical point estimates, p=1.0) + revise-counterfactual mechanism analysis on full 179-task decisive run (revise net effect -3.5pp, discarded_win=0/113) — explains WHY ON can't beat OFF5, not just that it doesn't"
git push origin feat/v2-four-stages
git rev-parse HEAD
git ls-remote origin feat/v2-four-stages
```
（雜湊見 GAIN_STATE.md 本輪段落，push 後逐字元比對本地/遠端 HEAD）
