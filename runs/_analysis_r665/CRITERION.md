# round665 預註冊判準：round664 的「推翻條件」是不是被真的觸發了

**寫於量測之前，commit 之後才碰資料。** 2026-09-03 UTC ~20:30。

## 本輪要解的問題

round664 做完了 H4（`review_retries` 2→4）的估計（`runs/_analysis_r664/RESULT.txt`），
**但整輪未 commit、未寫 GAIN_STATE**，而且它自己的推翻條件檢查印出很大的數字：

```
S1: review失敗=54 其中提早停=42      S4: review失敗=19 其中提早停=14
S2: review失敗=22 其中提早停=18      S5: review失敗=41 其中提早停=12
S3: review失敗= 6 其中提早停= 5      S6: review失敗=117 其中提早停=60
```

round664 的 CRITERION 寫死：「若 review 的失敗大量停在 `attempt < retries_max`
（非 401/402/403）⇒ void 定義沒抓對，本輪數字作廢。」照字面看，**觸發了**。

**所以在結算 P-R664-1~5 之前，必須先答這一題：那 42/18/5/14/12/60 是真的提早停，
還是量具的錯？** 沒答之前不准引用 round664 的任何數字。

## 碼側事實（寫判準前查好，非本輪的量測資料）

1. `brain_cline.py:117-252` 的重試迴圈：**每一次 attempt 各自落一列**（成功列 `ok=True`、
   失敗列 `ok=False`），只有 401/402/403 會 `break`，其餘一律續試到 `effective_retries`。
   `retries_max` 落盤的就是 `effective_retries` 本人（同一個變數）。
2. ⇒ 一個「邏輯呼叫」失敗兩次，會留下 **attempt=1 與 attempt=2 兩列失敗列**。
3. `retry_rescue.py:126-129` 的 `rev_short` 是**逐列**判斷
   （`r["attempt"] < r["retries_max"] and not is_early_break(r)`），
   **沒有檢查後面有沒有 attempt+1 那一列**。
   ⇒ 一個正常重試到底的序列，它的中間列**必然**滿足這個條件。
   ⇒ 這個檢查在機制上分不出「提早停」與「還在重試」。
4. 佐證：round664 自己的守恆恆等式（`reach[k] == fail_retryable[k-1]`）在
   `retries_max>=4` 的角色上六層殘差全 0 ⇒ 那些角色**沒有**任何提早停。
   同一個迴圈服務 review，review 沒有理由不同。

## 估計量（先定義）

- **邏輯呼叫分組鍵**＝`(agent_id, role, sha1(prompt), api)`。同一邏輯呼叫的各 attempt
  prompt 逐字相同（`make_body` 每次用同一個 `prompt` 變數）。
- **真提早停序列**＝該組最大 attempt 的那一列 `ok=False`、
  且 `max_attempt < retries_max`、且該列**不是** 401/402/403。
- **真提早停率**＝真提早停序列數 / 失敗序列數（`role="review"`）。

## 事前預測（做完照實結算，中幾條寫幾條）

| # | 預測 |
|---|---|
| P-R665-1 | round664 標成「提早停」的列中，**≥90%** 有 attempt+1 的後繼列（＝其實有重試），六層中 **≥5 層**成立 |
| P-R665-2 | 改成逐序列後，review 的**真提早停率 pooled < 5%** |
| P-R665-3 | 六層的 review `retries_max` 皆為 **2**（H4 的組態前提成立） |
| P-R665-4 | 逐序列數出的 ON 臂 review void 序列數，**逐層等於** round664 的 `review_void_on`（12/4/1/5/29/57）⇒ void 定義本身沒問題 |
| P-R665-5 | 完整性：`attempt>=2` 的列必有 attempt-1 的同組前驅；缺漏 >1% ⇒ **BROKEN**（不是 PASS、不是 0%） |

## 事前決策規則（不准做完再挑）

- **P-1 且 P-2 成立** ⇒ round664 的推翻條件**沒有**真的觸發，是量具誤報。
  ⇒ round664 的數字**成立**，本輪照它的規則結算 P-R664-1~5 並執行它預寫的決策規則。
  ⇒ 同時修 `retry_rescue.py` 的檢查（改逐序列），**這是量具修正不是判準放寬**，
  且必須先用植入缺陷證明新檢查抓得到真的提早停。
- **P-2 不成立**（真提早停率 ≥5%）⇒ round664 的數字**作廢**，照實寫作廢，
  **不准當場補判準把它救回來**。
- **P-4 不成立** ⇒ void 定義與逐序列不一致，round664 的 ON void 分母有問題，同樣作廢。
- **預留第三種狀態**（r662 §三 的規則）：若部分層觸發、部分層沒有，**逐層報**，
  不准合併成一句「觸發／沒觸發」。

## 推翻條件（本輪自己的結論何時該被丟掉）

- 若分組鍵在某層產生**重複 attempt**（同組出現兩個 attempt=1）⇒ prompt 相同的不同邏輯
  呼叫被併在一起，該層的逐序列數字**無效**，報 `AMBIGUOUS` 不報 0。
- 若某層 `role="review"` 的列數為 0（OFF-only run）⇒ 報 `N/A`，不列入 pooled 分母。

## 量具雙向驗證（每個都必須被抓到）

- **N1** 分組鍵拿掉 prompt（只用 agent_id+role）⇒ 重複 attempt 偵測必須噴 `AMBIGUOUS`。
- **N2 植入缺陷（最重要）**：人工刪掉某一組的 attempt=2 列 ⇒ 真提早停數必須 **+1**。
  乾淨資料上是 0、植入後是 1 ⇒ 證明它會叫，不是恆為 0 的瞎尺。
- **N3** 空層／讀到 0 列 ⇒ **BROKEN**，不得安靜給 0%。
- **N4** 把 `is_early_break` 停用 ⇒ 401/402/403 的終局失敗會被誤記成真提早停，數字必須改變。

## 本輪不做的事

不起任何 run、不殺 r444（PID 2742320，18:53 起跑）、不改 `gain_run.py`／
`brain_cline.py` 的控制流、不動實驗條件、不碰展件／`world/`、不寫 `NEXT_MODEL=local`。
