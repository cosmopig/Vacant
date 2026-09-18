# DECISION round437：決定性 run（PID 2266603）跑完——ON vs OFF5 等預算最終結論

**2026-09-01 UTC ~04:41-05:10，Sonnet 5。**

## 發生了什麼

`runs/g_r356_3arm_20260830`（PID 2266603，`--n 179 --arms OFF,ON,OFF5`，
seed=`g-r212-route-20260828`，models=`qwen/qwen3.6-35b-a3b,gemma-4-12b-it-qat`）
從 round356（2026-08-30）起跑了約 **1 天 11 小時**，本輪 05:07 UTC 確認
PID 已自然結束（`ps -p 2266603` 找不到；`tail --pid=2266603 -f /dev/null`
正常退出 rc=0，不是 timeout）。三臂 `processed` 全部 = 179/179（tasks 總數），
迴圈本身沒有 while True，最後一題跑完就自然結束——**這是決定性 run 的終點，
不會再有新資料**。`summary.json` 的 `complete` 欄位仍是 `false`，但那個欄位
定義是 `n_void==0 and processed==len(tasks)`（見 `ops/gain/gain_run.py:958`），
即「零 void」而非「跑完全部題目」；infra_void 是預期內的 HTTP 400 重試耗盡，
不代表還有題目沒跑。**不要被這個欄位名稱誤導成「還沒跑完」。**

## 最終數字（完整 179 題、三臂全部 processed=179）

### OFF baseline（量測窗口確認，鐵律：判準先於量測）

```
processed=179 infra_void=5 measured=174
f(失敗率)=26.44%  Wilson CI95=[20.4%, 33.4%]
```
仍在 SPEC_GAIN 定義的 20–60% 可用窗口內——量測從頭到尾都有訊號，這條
判準在 371 輪的整個過程中沒有動搖過。

### raw 版配對（`analyze_paired.py`，未修 R393 typing 白名單漏洞）

```
ON vs OFF5:  n=101  ON=75.25%(76/101)  OFF5=77.23%(78/101)
             b(ON only)=6  c(OFF5 only)=8  McNemar p=0.7905
             gap(ON-OFF5) = -1.98pp（OFF5 略領先）
             等預算=True（ON=505 calls, OFF5=505 calls）
             void率  ON=36.2%(64/177)  OFF5=16.9%(30/177) ⚠VOID-GATE-WARNING

ON vs OFF:   n=108  ON=75.00%(81/108)  OFF=76.85%(83/108)
             McNemar p=0.8145  gap=-1.85pp
             等預算=False（ON=540 calls, OFF=108 calls，ON 貴 5 倍）
```

### typing 修正版配對（`reanalyze_typing_fix_r393.py`，修正
`_GAIN_ALLOWED_IMPORTS` 缺 `typing` 這個零副作用白名單漏洞——
見 `DECISION_20260831_R393_TYPING_IMPORT_WHITELIST_BUG.md`）

```
ON vs OFF5:  n=101  ON=84.16%(85/101)  OFF5=81.19%(82/101)
             b=5  c=2  McNemar p=0.4531
             gap(ON-OFF5) = +2.97pp（ON 略領先）

ON vs OFF:   n=108  ON=83.33%(90/108)  OFF=79.63%(86/108)
             McNemar p=0.2891  gap=+3.70pp

OFF vs OFF5: n=143  OFF=77.62%(111/143)  OFF5=80.42%(115/143)
             McNemar p=0.4240  gap=-2.80pp（self-consistency 贏單發，符合預期）
```

**這是 round430 起第 7 個連續檢查點，typing 修正版的 b/c/p 完全複製
（b=5, c=2, p=0.4531）——本輪 n_paired 從 99 漲到 101，b/c 一個都沒變。**
這不是抽樣運氣：新增的 2 題（run 收尾的最後兩題）沒有貢獻任何新的
discordant pair，配對集合在這個資料量級已經飽和。

### 交叉驗證：off5va（同稽核 hash 控制版）

```
n=101（其中 28 題被同一顆 hash 抽中稽核）
ON 漏出 8/101=7.92%   OFF5VA 漏出 11/101=10.89%
b(ON only)=0  c(OFF5VA only)=3  McNemar p=0.2500
gap(OFF5VA-ON)=+2.97pp（方向與 typing 修正版一致：ON 領先）
```

### reviewer_family（評審與被評審同家族的盲區檢查）

```
同家族: 116/150=77.33%（真失敗題上抓到 6/40=15.00%）
不同家族: 140/189=74.07%（真失敗題上抓到 6/44=13.64%）
精確超幾何單尾 p=0.6883
```
無顯著同源盲區——與 round352 起的歷次重跑一致。

### 評審準確率（鐵律 3 要求單獨報）

`ON` 臂 `summary.json` 記錄 `reviewer_accuracy=0.7552`（GROUNDED 票）。
與 round411 記錄的 0.7582（n=82 時）幾乎沒動，仍只比「無腦全過」基線
（≈0.747-0.7473）高約 1pp——評審辨識力弱，這與 ON/OFF5 拿不到顯著優勢
彼此印證（弱評審 ⇒ 機制帶來的增益上限本來就低）。

### 運算成本

```
OFF:  calls=174  calls_per_correct_delivery=1.36（accepted_and_meets_demand=128）
ON:   calls=660  calls_per_correct_delivery=7.67（accepted_and_meets_demand=86，
      但 accepted 只有 95/179=53%——void+reject 吃掉近一半的題目）
OFF5: calls=804  calls_per_correct_delivery=6.93（accepted_and_meets_demand=116）
```
ON 的「每個正確交付的呼叫數」(6.53-7.67，隨口徑微幅浮動) 與 OFF5
(6.45-6.93) 在同一量級，沒有誰系統性划算——這與等預算配對分析的
「無顯著差異」是同一個結論的兩種算法。

## 結論——三條「有成效」判準逐條收尾

1. **量測有訊號** ✓：OFF 失敗率 26.44%，全程在 20–60% 窗口內，
   從 round?（smoke 6 題天花板）到現在 371→179 題的決定性 run，
   這條判準從第一次量到就沒有動搖過。
2. **三臂有差異**：**沒有統計上可分辨的差異**（ON vs OFF5：raw p=0.79，
   typing 修正版 p=0.45；兩種修正方向都不顯著，且點估計方向本身
   會因為要不要修 typing 漏洞而**翻轉**——raw 版 OFF5 略領先 2pp，
   typing 修正版 ON 略領先 3pp。這個「連方向都不穩定但幅度都很小」
   本身就是「無實質差異」最直接的證據，不是「還沒測準」。
3. **等預算答案**：**已經出來，是「打不贏」這一種答案**（更精確：
   在等呼叫數下，Vacant 機制的 review+revise 迴路沒有讓需求=產出率
   顯著高於 self-consistency 多數決）。R411（round411, n=82）的結論
   在 n=101（完整 179 題資料的極限）**依然成立、從未接近顯著**。

**這是 R411 結論的最終、資料量已達上限的確認版，不是新結論。**
這條主線問題——「Vacant 機制在等預算下打不打得贏 self-consistency」——
到這個 run 的範圍內**已經回答完**：打不贏（無法證明贏，也無法證明輸，
點估計方向本身不穩定）。繼續在**同一個 run、同一批題目**上重跑配對分析
不會再產生新資訊——`runs/g_r356_3arm_20260830` 這個資料集本身的邊際
價值已經耗盡。

## 沒做的事

- 沒有 kill 這個 run（它自己正常結束，不需要）
- 沒有修改 `ops/gain/` 任何邏輯
- 沒有重新定義「有成效」的判準以配合這個結果（三條判準是預先寫死的，
  結果符合就照實寫，不符合也照實寫——這裡是符合）
- 沒有把「打不贏」加強成「Vacant 沒用」——那需要更大 n 或不同任務分布
  才能排除「等預算下差異真的很小、只是這個 n 量不到」的可能性；
  R411 已經警告過這條措辭邊界，本輪延續同樣的克制

## 下一輪該做什麼（推翻條件與延伸方向）

這個 run 的資料已經榨乾，下一輪不該再重跑同一批配對分析（純同步進度
的檢查點已經連續 7 次逐位元不動，繼續跑第 8 次不會有新資訊）。
有意義的下一步（人類交辦「沒有『做完了』這個狀態」）：

1. **新的決定性 run**：更大 n 或更快的 worker 池組合，目的是把 ON/OFF5
   的 95% CI 收窄到能區分 ±3pp 等級的差異（目前 CI 寬達 ±8-9pp，
   遠大於觀察到的 gap）。這需要 sonnet/opus 判斷 n 要多大、
   要不要換 worker 池（換池是實驗條件變更，要記 DECISION）。
2. **評審準確率與 ON 增益的相關性**（SPEC 建議的延伸方向）：用現有
   `runs/g_r356_3arm_20260830` 資料，看 `revision_transition`
   （improved/harmed/stayed_correct/stayed_wrong）是否與 audit 命中
   有關——這是**現有資料就能做**的分析，不需要新 run，local 可勝任
   起手的資料整理，但判讀「這是不是機制訊號」需要 sonnet。
3. **難題子集**：OFF 失敗的 45 題（26.44% 的那批）單獨拉出來看
   ON/OFF5 在「難題」上是否有差異（天花板效應在簡單題上會稀釋掉
   任何真實效應）——這是最有機會挖出訊號的方向，因為簡單題兩臂
   都接近 100%，差異只可能在難題上。

**推翻條件**：如果新 run（方向 1）或難題子集（方向 3）在更大 n 或
更集中的難度上出現 p<0.05 的顯著差異，本輪「打不贏」的結論需要更新為
「在完整題庫等預算下打不贏，但在難題子集上有/沒有優勢」——是否推翻
取決於效應量與方向，不是自動的。
