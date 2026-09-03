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
