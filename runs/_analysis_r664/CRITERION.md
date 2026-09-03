# round664 預註冊判準：r662 的 H4（`review_retries` 2→4）值不值得花一個 run

**寫於量測之前，commit 之後才碰 void 資料。** 2026-09-03 UTC ~19:25。

## 背景與本輪要解的問題

r662 §四 H4 觀察到 ON 臂結構性較易 void，歸因於 `role="review"` 的 `retries_max=2`
（`gen`／`revise` 是 4），並排定「r444 收官後做決定二：`review_retries` 2→4」。
r662 自己註明 **H4 是組態＋跨池觀測的推論，不是量測到的因果**。

本輪不等 r444、不碰 r444、零 API，問一件在磁碟上就能答的事：
**如果真的把 review 的重試從 2 加到 4，救得回多少 void？**
若救得回的量微不足道，那個改動就只是「改變實驗條件換來近乎零的收益」，不該做。

## 碼側事實（寫判準前查好，非 void 資料）

1. 每一次 attempt 各自落盤一列，帶 `role`／`attempt`／`ok`／`retries_max`／`timeout_s`
   （`brain_cline.py:169,204`）⇒ **每一列都代表「確實走到了第 k 次嘗試」**。
   ⇒ 條件回復率可直接算，**不需要把 attempt 併回邏輯呼叫**（無分組＝少一個易碎點）。
2. `review` 與 `gen`／`revise` 有 **兩個** 差異，不是一個：
   - `retries=review_retries`（預設 2）vs `retries=4`（`gain_run.py:696,1008,1012`）
   - `timeout_s=review_timeout_s` vs `request_timeout_s`（r444 是 380 vs 600）
   ⇒ **H4 把 ON 的 void 全歸給重試次數，與「review 逾時上限較短」混淆。**
   對 Group A（void 87.5% 是 `TIMEOUT`，r662 §一）逾時差異在機制上更可能是主因。
3. 重試會輪換 model variant（`brain_cline.py:118`）；單模型 run 中所有 attempt 打同一個模型。
4. 401/402/403 不重試會提早 break（`brain_cline.py:238`）⇒ void 未必都停在 `attempt==retries_max`。

## 估計量（先定義）

- **條件回復率** `p_k` ＝ `#(attempt==k 且 ok)` / `#(attempt==k)`，只取 `retries_max>=4` 的角色。
  這是「已經走到第 k 次的呼叫，在第 k 次成功的比例」。
- **void 呼叫序列**（每角色）＝ `ok==False` 且（`attempt==retries_max` 或 錯誤為 401/402/403）。
- **寬鬆救援估計** `rescue = void_review × (1 − (1−p3)(1−p4))`。
  ⚠ 這裡**假設** review 失敗的每次回復率與 gen／revise 相同。這是假設不是量測，
  且方向對 H4 有利（gen／revise 的失敗多為可重試型）⇒ **寬鬆估計小，結論才穩。**

## 事前預測（做完照實結算，中幾條就寫幾條）

| # | 預測 |
|---|---|
| P-R664-1 | 六層 pooled，ON 臂的 void 呼叫序列中 `role="review"` 佔 **≥50%** |
| P-R664-2 | pooled `p_3` **< 5%** 且 `p_4` **< 5%** |
| P-R664-3 | 失敗列上 review 的 `timeout_s` < gen 的 `timeout_s`，在 **≥4/6** 層成立（逾時混淆確實存在） |
| P-R664-4 | 寬鬆救援估計 < ON void 數的 **20%**，**每一層皆然** |
| P-R664-5 | 完整性：六層每一列的 `role`/`attempt`/`ok`/`retries_max`/`timeout_s` 皆非 null，缺漏 >1% ⇒ **BROKEN**（不是 PASS、不是 0%） |

## 事前決策規則（不准做完再挑）

- **P-2 且 P-4 都成立** ⇒ 建議**撤掉**排定的 `review_retries` 2→4：收益 <20% void 缺口，
  代價是改變實驗條件。改把 `review_timeout_s` 列為證據較強的候選（但仍**不是**本輪要動的）。
- **P-2 不成立**（p3/p4 ≥5%）⇒ 該修法有實質空間，維持 r662 的計畫。
- **P-1 不成立** ⇒ H4 的前提（ON 的 void 來自 review）在角色層級就錯了。
  **這與「修法沒用」是兩件事，分開報，不准合併成一句。**
- **預留第三種狀態**（r662 §三 的規則）：若 review 確為多數、回復率又不低、
  但逾時混淆同時很大 ⇒ **兩個機制並存**，照實寫，不要硬塞成二選一。

## 推翻條件（本輪自己的結論何時該被丟掉）

- 若 review 的失敗大量停在 `attempt < retries_max`（非 401/402/403）⇒ void 定義沒抓對，本輪數字作廢。
- 若 `retries_max>=4` 的角色在某層完全沒有 attempt≥3 的列 ⇒ 該層 `p_3`/`p_4` **無定義**，
  必須報 `undefined` 而不是 0（0 會讓寬鬆估計假性變小，方向剛好偏袒本輪結論）。

## 量具雙向驗證（突變體，每個都必須被抓到）

- **M1** 回復率改用「全 attempt 的 ok 比例」而非逐 k ⇒ 自檢：`#(attempt==k)` 對 k 必須非遞增。
- **M2** void 改成「所有 ok==False 的列」 ⇒ 與 `summary.json` 的 `infra_void` 數對不上。
- **M3** 拿掉 role 過濾（全角色當 review）⇒ 救援估計改變。
- **M4** 某層讀到 0 列時必須報 **BROKEN**，不得安靜給 0%。

## 本輪不做的事

不起任何 run、不殺 r444、不改 `gain_run.py`／`brain_cline.py` 的控制流、
不動頭條數字、不碰展件／`world/`、不寫 `NEXT_MODEL=local`。
