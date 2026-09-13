# R528：P-R523-2（`counterexample_confirmed` 要不要拆成「初稿拋例外」／「初稿回傳不同值」）
# —— 先量再裁，判準寫在量測之前

（2026-09-03 UTC 00:2x–，**Opus 5，判斷輪**。round527 交棒指定：由 opus 裁決這個
已經懸了三輪（R519 開案、R521／R523 兩次「維持提案、不升級」）的提案。零 API、零 run、
不動 8765／1004。R440G 預註冊閘門管的是 `gain_run.py` 的發射，本輪是離線重算，
不在其管轄範圍（round525 已確立此界線）；本檔預註冊的是**判準**，不是 run。）

## 一、提案原文與它自己開的條件

`DECISION_20260902_R519_CEILING_AUDIT.md` §七第 2 項：

> `counterexample_confirmed` 裡有 5/61 票的 args 連**參考解**都會拋例外 …… **不要**為此把
> 參考解接進 verify 路徑（V/GT 分離）；可考慮的是把「初稿在宣稱的 args 上拋例外」與
> 「初稿回傳不同的值」分成兩種 status 落盤，**先量再說**。這是提案，不是判準。

**提案自己寫了「先量再說」，而這件事三輪以來沒有人量過。** R519／R521／R523 三輪都在
「要不要升級」之間空轉，卻沒有做提案指定的前置動作。本輪不繼續猜值不值得，直接做那個量測
——資料全在磁碟上，零 API。

## 二、機制：這個 status 現在確實把兩件事混在一起

`ops/gain/gain_run.py:394-396`：

```python
    check = counterexample_check(entry_point, args, expected)
    matches, err = meets_demand(code, check, timeout_s, entry_point=entry_point)
    return not matches, "counterexample_confirmed" if not matches else "candidate_passed_claim"
```

`meets_demand` 回傳的 `err` **被丟掉**。初稿在宣稱的 args 上「拋例外」與「回傳不同的值」
兩種情形都落成同一個 `counterexample_confirmed`。這不是推測，是讀碼可見的事實。

## 三、量測 M-R528（判準寫在前面，以下全部先寫死）

資料：`runs/g_r441_gemma_only_mbpp_b`（R518/R519/R522 用的同一份；本輪重記指紋）。
對象：ON 臂 `status == "counterexample_confirmed"` 的 61 票。

**重放路徑刻意與 runtime 不同**（獨立驗證）：初稿原始碼**從 review call 的 prompt 反解**
（`gain_run.py:506-508` 把 `initial_code` 夾在 ```` ```python ```` 內送給評審），
不呼叫 `extract_code()`；在 `python3 -I` 子行程執行，不經 vacant sandbox。

分三類：
- `draft_raised`：`initial_code(*claim_args)` 拋例外或逾時
- `draft_value_differs`：回傳值 ≠ 宣稱 EXPECTED（harness 相等判定，沿用 R519 的 `eq_h`）
- `draft_value_matches`：回傳值 = 宣稱 EXPECTED

**量具雙向驗證（不通過則本輪數字作廢，照實寫「量不到」，不得改判準）**：
- 正向：61 張 confirmed 票裡 `draft_value_matches` 必須 = 0（若 >0，代表我的重放與 runtime
  不同調，數字不可用）
- 反向：64 張 `candidate_passed_claim` 票重放必須全部落在 `draft_value_matches`
  （若有落在別類，同上作廢）

**精度（precision）定義**：`row.initial_meets_demand is False`，即該票指控的初稿**真的**
被 hidden 測試打掉。已核對 `gain_run.py:1127-1136`：它是拿 `initial_code` 跑 `hidden_check`，
不是修訂後的碼，是正確的代理量。**限制照實寫**：ON 臂每題只有一份初稿 ⇒ 同一題的多張票
共用同一個 `initial_meets_demand`，票與票不獨立 ⇒ 票級與題級兩個數字都要報。

## 四、裁決規則（先寫死；四個分支都先列出來，量完不准改）

令 `n_raised` = `draft_raised` 的票數，`Δ` = |precision(raised) − precision(value_differs)|（題級）。
題級歸類：一題的 confirmed 票全落同一類才歸該類；混合題單獨報並排除在 Δ 之外。

- **D1｜結案「這件事幾乎不發生」**：`n_raised < 5` ⇒ 不改碼，把票數寫進本檔，提案關閉。
- **D2｜升級實作**：`n_raised ≥ 10` **且** `Δ ≥ 0.20` ⇒ 這個 status 混了兩種意義不同的東西，
  值得拆；實作要含植入缺陷測試（要能證明舊碼把「初稿拋例外」錯標成與「值不同」同一類）。
- **D3｜結案「量過了，沒訊號」**：`n_raised ≥ 5` 且 `Δ < 0.20` ⇒ 不改碼，但把數字寫死，
  以後不准再以「沒量過」為由重開。
- **D4｜5 ≤ n_raised < 10**：檢定力不足 ⇒ 預設走 D3（結案）；除非 `Δ ≥ 0.40`，那就寫成
  「有新 run 時值得重看」，但**本輪仍不改碼**。

**另一個獨立的子問題，也先寫死**：`err` 被丟掉要不要撿回來？
- 若上面的量具雙向驗證**兩個方向都滿分** ⇒ 這個區分在離線就能 100% 還原，runtime 再存一份
  是**冗餘**，**不加**（避免做一個不帶新資訊的改動）。
- 若雙向驗證**任一方向不滿分** ⇒ 離線還原不可靠，runtime 是唯一能可靠捕捉的地方 ⇒ **實作**。

## 五、推翻本輪的條件

1. 本量測只涵蓋 gemma-4-12b-it-qat 初稿 × MbppPlus。換 worker 池或題庫，crash 率可能不同 ⇒
   本輪結論不得外推到別的池子。
2. 若重放拋出的例外其實是我的重放環境造成的（缺 import、sandbox 差異）而非初稿本身 ⇒
   `n_raised` 灌水。**緩解**：例外型別逐個列出並人眼看過，`RunnerError` 另計不算 raised。
3. 若有人證明 `initial_meets_demand` 不是精度的正確代理（例如它其實反映修訂後的碼）⇒
   §三 的 precision 全部作廢。本輪已讀碼核對過（見 §三），但這條留著。
4. 若 D2 觸發但 61 票的題級 n 太小（<10 題）⇒ 降級為 D4 處理，不得因為 Δ 好看就升級。

---

# 量測結果與裁決（判準寫死之後才跑；腳本 `runs/g_r441_gemma_only_mbpp_b/analysis_round528/crash_split_r528.py`）

資料指紋（與 R519 同一份）：`rows.jsonl` 525 行 sha8 `440d973c`／`calls.jsonl` 1986 行 sha8 `3d24b73d`。

## 六、量具雙向驗證：**通過**

```
prompt 反解不到初稿的票數 = 0（125/125 全部反解成功）
正向：confirmed 61 票裡 draft_value_matches = 0        （判準要求 0）✓
反向：candidate_passed_claim 64 票全部 draft_value_matches = 64/64 ✓
```

兩個方向都滿分 ⇒ 依 §四 預註冊的子規則，**`err` 的區分在離線 100% 可還原，
runtime 不加這個欄位**（不做沒有新資訊的改動）。

## 七、confirmed 61 票的分類——出現了我沒有預先列出的第四類

```
draft_value_differs    42
no_entry               12   ← 判準 §三 只寫了三類，這一類是量出來才發現的
draft_raised            7
   拋例外型別：TypeError 3、Timeout 3、ValueError 1
```

`no_entry` ＝ **初稿根本沒有定義題目要求的 entry_point**（5 題：Mbpp/473、781、125、63、245）。
人眼逐個看過（判準 §五-2 要求）：**不是我的重放環境造成的**，是初稿真的把函式取錯名字——
Mbpp/473 要 `tuple_intersection`，初稿寫 `find_tuple_intersection`；Mbpp/63 要 `max_difference`，
初稿寫 `find_max_difference`。這 5 題的 `initial_meets_demand` 全部是 False，與此一致。

## 八、精度對比

```
票級：draft_raised        5/7  = 0.7143  W95[0.3589,0.9178]
      draft_value_differs 24/42= 0.5714  W95[0.4221,0.7088]
題級（37 題，混合／no_entry 題 6 題排除）：
      draft_raised        2/3  = 0.6667
      draft_value_differs 13/28= 0.4643
      Δ（題級）= 0.2024
```

## 九、裁決：**P-R523-2 結案，不升級，不改碼**（走預註冊的 D4→D3）

- `n_raised`（票級）= **7**，落在 `5 ≤ n < 10` ⇒ 觸發 **D4**。
- D4 的例外要 `Δ ≥ 0.40`，實測 `Δ = 0.2024` ⇒ **不觸發例外，預設走 D3（結案）**。
- 另外 §五-4 獨立地也把它壓回 D4：題級 `n_raised = 3`，遠低於「題級 n ≥ 10」的要求。
- 加上 §六 的量具雙向驗證通過 ⇒ `err` 也不撿。

**「初稿在宣稱的 args 上拋例外」這件事是真的存在，但一年份的這個 run 裡只有 7 票／3 題，
而且精度對比在這個量級分不出來。三輪來「要不要升級」的懸案到此結束——不是因為沒空量，
是量過了，訊號不足以支撐改碼。以後不得再以「沒量過」為由重開。**

## 十、意外收穫（**不是本輪判準的一部分，不拿來改上面的裁決**）

`no_entry` 這一類我沒有預先列出來，它比提案想拆的 `draft_raised` 還多（12 票 vs 7 票）。
照規矩：**照實寫，但不當場補判準去把它變成 D2**。以下全部是描述，不是裁決。

**(1) confirmed 這一桶是異質的，而且異質的方向跟 R518 的敘事相反。**
把 R519 的逐票 `harness` 判定（A）與本輪分類 join（125/125 全中，0 遺漏），
先複核 R519 的兩個數字**逐位重現**（全體 95/156=0.6090、confirmed 21/61=0.3443）：

```
confirmed / draft_value_differs   A=10/42 = 0.2381  W95[0.1348,0.3853]
confirmed / draft_raised          A= 3/7  = 0.4286  W95[0.1582,0.7495]
confirmed / no_entry              A= 8/12 = 0.6667  W95[0.3906,0.8619]
confirmed 全部                     A=21/61 = 0.3443
```

R518 說「`counterexample_confirmed` 是逆向選擇器」——本輪把它**收窄**：逆向選擇幾乎
全部住在 `draft_value_differs`（A=0.238）；`no_entry` 那一類的 A=0.667 跟全體 0.609
分不出來，它根本不是「評審算錯」的產物，而是「初稿取錯名字，任何呼叫都失敗」。

**(2) R518/R519 的梯子裁決不受影響（重要，先確認過才敢往下寫）：**

```
全體 parseable 排除 no_entry：A = 87/144 = 0.6042  W95[0.5226,0.6803]
```

上界 0.6803 **仍遠低於 0.80**（0.80 是 R518 §十一 事前定的門檻，不是本輪新訂）。
**梯子仍停 L0。** R519 §八 寫「要翻轉得再多 ≈13 票從錯變對」——`no_entry` 是 12 票，
量級接近，所以這條非查不可；查完是**不翻**。

**(3) entry_point 取錯名字是全臂共通的地板，約 5.7%：**

```
每臂初稿沒有定義 entry_point 的比率（用 runtime 自己的 extract_code）：
  OFF   10/179 = 5.6%
  ON    10/167 = 6.0%
  OFF5  50/895 = 5.6%
```

三臂幾乎一樣 ⇒ 這是 worker 模型（gemma-4-12b-it-qat）的行為，**不是任何一臂的機制造成的**。
ON 那 10 題全部 `initial_meets_demand=False`，修訂後只救回 1 題（Mbpp/781），其餘 9 題
`stayed_wrong`／`revised_both_visible_fail`——**ON 拿到了系統確認過的反例，卻幾乎修不掉
「函式取錯名字」**。查過 revise prompt（Mbpp/473）：正確名字 `tuple_intersection` 在
prompt 裡出現 6 次（夾在原題的 assert 裡），但**沒有任何一句明說「函式必須叫這個名字」**。

**(4) 拿掉這層共通地板，等預算的答案不變（探索性，非閘門）：**

先複核基準口徑**與 R516/R519 逐位相同**（68.16%／73.05%／73.74%，三組 b/c/p 全同），
再排除任一臂出現 naming miss／語法錯的 30 題：

```
              全部題目                    排除 naming-miss 題
  OFF     122/179 = 68.16%            112/149 = 75.17%
  ON      122/167 = 73.05%            110/137 = 80.29%
  OFF5    132/179 = 73.74%            118/149 = 79.19%
  ON vs OFF5   b=11 c=12 p=1.0000  →  b=5 c=4 p=1.0000
  ON vs OFF    b=17 c= 7 p=0.0639  →  b=9 c=1 p=0.0215
  OFF5 vs OFF  b=12 c= 2 p=0.0129  →  b=7 c=1 p=0.0703
```

**ON vs OFF5 仍然 p=1.0000。** 也就是說「等預算下 Vacant 打不贏 self-consistency」
**不是**被一層共通雜訊地板壓出來的假平手——拿掉地板之後兩臂還是分不出來。
這是對既有結論的**加固**，不是推翻。
（另兩組的 p 值方向有變，但 discordant pair 只有 10 與 8 對，這個量級的 p 值極脆弱，
不足以支撐任何新陳述——證據單位是 discordant pair，不是 137 個 paired point。）

## 十一、開新提案（**只登記，不在本輪執行**）

**P-R528-1：gen／revise 的 prompt 沒有明說 entry_point 必須用哪個名字。**
證據見 §十(3)：三臂各約 5.7% 的初稿因此直接歸零，ON 有確認過的反例也只救回 1/10。
**這是改變實驗條件（動 prompt）**，依 LOOP_PROMPT「換題庫／換 worker 池／改判準都算改變
實驗條件」，要先寫 DECISION、寫死預測與中止準則，且需要一個新 run 才能驗——
而 R440E 的人類決定落地前 8765 不得起新 run。**所以本輪只登記，不實作。**
下一輪不要看到這段就直接去改 prompt。

**P-R528-2（低優先）：`no_entry` 落成 `counterexample_confirmed` 是語意上的類別錯誤**
——`verify_review_counterexample` 的 docstring 寫「Confirm that a FAIL review's literal
test actually falsifies the candidate」，但初稿沒有 entry_point 時，**任何**測試都會失敗，
不是這個評審的反例把它打掉的。運作上不造成錯誤結果（初稿確實是壞的，FAIL 票算 FAIL 是對的），
**傷害只在解讀**：R518/R519/R522 都把這一桶當成「評審真的抓到反例」。本輪已用 §十(1) 的
拆解把解讀修正了，所以改碼的急迫性低；且依 §六，離線可 100% 還原。**維持不改。**

## 十二、本輪觸發的推翻條件，照實記

§五 第 2 條（「重放拋出的例外可能是我的環境造成」）**確實觸發了**：出現了預先沒列的
`no_entry` 12 票。依規定人眼逐個看過，判定**不是環境造成**，並且**沒有**把它算進
`n_raised`（判準寫的是 `RunnerError` 另計，`no_entry` 同理另計）。裁決因此不受影響。
