# DECISION 2026-09-01（round428，Sonnet 5）：為什麼 off5v 顯著（p=0.0312）而主判準（demand=output）不顯著（p=0.77）——兩者不矛盾，量的是不同東西

## 觸發

`analyze_off5v.py` 從 round401（n=78）起沒有人重跑過（26 輪只重跑 `analyze_paired.py`
的 ON vs OFF5），儘管 ON 列數從 83 長到 100。本輪重跑，n 從 78 長到 90，
discordant 仍是 **b=0, c=6**（跟 round392、round401 逐字元相同，12 個新配對全部
一致，沒有新增任何一個 discordant）——`mechanism_contributes` 判定在 3 個獨立
檢查點、n 從最初到 90 的成長過程中完全沒有動搖過。但這個顯著結果與 R411
的「ON vs OFF5 無顯著差異」（p=0.77，同一批資料）表面上矛盾，值得查清楚
是不是量具不一致。

## 查法：直接讀兩支分析工具的原始碼與 rows.jsonl，不猜

`analyze_paired.py`（R411 用的主判準）：`a_ok = sum(meets_demand for common
tasks)`——**不管 accepted 是 True 還是 False，只看 `meets_demand` 這個欄位**。
`analyze_off5v.py` 的 `leaked()`：`leaked = accepted AND NOT meets_demand`——
**accepted=False 的任務一律 `leaked=False`，不管 meets_demand 是什麼**。

兩者的分母都是「兩臂都量到的題目」，但對「ON 拒絕交付（review 攔下、
沒有修好）」這件事的計分完全相反：`analyze_paired` 把它算成失敗（跟
「答錯又交出去」同分），`analyze_off5v` 完全不算它是漏出（因為根本沒交出去）。

## 實測驗證（本輪，`runs/g_r356_3arm_20260830`，ON n=101 列）

```
ON accepted=True   86 列，其中 meets_demand=True  77 (89.5%)
ON accepted=False  15 列，其中 meets_demand=True   0
                        meets_demand=False  15（review 全部抓對，0 誤殺）
```

**review 機制的精確度是 100%**（15/15 次拒絕都拒對了，`DECISION_20260831_R381`
已證明 ON 的高 void 率是 retry 預算不對稱的量測偽影、跟這裡的「拒絕」是
兩件事——void 根本不進 rows.jsonl，這裡的 15 筆是有進 rows.jsonl 的
`accepted=False`，是 review 主動判斷後的結果，不是 infra 雜訊）。

但這 15 筆「攔對的壞答案」在 `analyze_paired.py` 裡跟「沒攔住、答錯又交出去」
一樣算 `meets_demand=False`、拖低 ON 的 demand=output rate；在
`analyze_off5v.py` 裡因為 `accepted=False` 完全不計入漏出，所以不影響
ON 的漏出率。**這就是兩個判準分裂的完整機制解釋，不是巧合也不是 bug。**

## 結論：兩個判準在回答兩個不同的問題，都成立，不衝突

1. **「使用者拿到正確答案的機率」**（`analyze_paired`／R411 的主判準）：
   ON 與 OFF5 在等預算下無顯著差異（p=0.7744，n=90，25+ 個檢查點穩定）。
   ON 把一部分「答錯的候選」轉成「拒絕交付」而不是「交錯的答案」，
   但拒絕交付本身在這個判準下**跟答錯同分**——因為使用者兩種情況下
   都沒拿到能用的程式碼。

2. **「一旦系統交付了答案，那個答案是不是錯的（漏出風險）」**
   （`analyze_off5v`）：ON 顯著更安全（漏出 8.89% vs OFF5V 15.56%，
   gap=6.67pp，p=0.0312，3 個檢查點穩定、12 個新配對零反例）。
   ON 的 review 機制在「決定要不要交付」這一步確實比免費的可見測試閘
   更準（能抓到通過可見測試但沒通過隱藏測試的壞答案），且目前為止
   0 筆誤殺（沒有錯誤攔下本來正確的答案）。

**這兩個結論都是真的，不是取捨後選一個。** SPEC_GAIN 的「有成效」判準
第 3 條問的是「等預算下打不打得贏」——用的是第 1 個判準（R411 已答：
沒有顯著贏）。但如果部署情境更在意「絕不要交付錯誤答案」（例如寧可
沒有答案也不要錯答案），off5v 顯示 Vacant 的審查機制確實提供可測量、
可歸因、統計穩定的安全邊際——只是這個邊際目前完全被「拒絕交付」的
機會成本抵銷，沒有轉化成整體正確交付率的優勢。

## 這推翻了什麼、沒推翻什麼

- **不推翻 R411**：「ON vs OFF5 等預算下無顯著差異」的結論不變，
  這裡只是解釋了為什麼「無顯著差異」跟「off5v 顯著」能同時為真。
- **不推翻 `mechanism_contributes` 判定本身**：off5v 判準下 ON 確實
  顯著更安全，這是真的、可重現的、有機制解釋的（review 精確度
  100%，不是雜訊）。
- **修正的是判定的話術**：`analyze_off5v.py` 印出的 `mechanism_contributes`
  容易被讀成「機制整體有加值」，但精確地說應該是「機制在『避免交付
  錯誤答案』這個子問題上有加值，但這個加值目前被覆蓋在整體正確交付率
  的無差異結果之下，因為交付率的判準不區分『拒絕』與『答錯』」。

## 推翻條件

若之後某輪發現：(a) ON 的「accepted=False」列裡開始出現
`meets_demand=True`（誤殺非 0），削弱「review 機制精確」這個前提；
或 (b) off5v 的 discordant 在後續資料成長中開始出現新的 b（只有 ON 漏出）
配對，讓 gap 縮小到不顯著——上面「review 精確度 100%」與「off5v 穩定
顯著」的兩個經驗前提就要重新檢查，不能假設它們對未來的資料繼續成立。

## 沒做的事

- 沒有修改 `analyze_paired.py` 或 `analyze_off5v.py` 的邏輯（兩者的定義
  差異是本輪要解釋的現象，不是要修的 bug）
- 沒有 kill 或干預背景 run（PID 2266603）
- 沒有因為這個發現去更改「有效」判準第 3 條的裁決——R411 的字面結論
  （用 demand=output 判準）依然是本實驗的正式答案，off5v 是補充的機制
  層級發現，不是替代結論
