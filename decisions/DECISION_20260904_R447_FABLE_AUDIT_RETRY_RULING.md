# R447 稽核裁決（round705，Fable 5.1）：OFF5 的 2 通失敗＋重試不是實驗條件偏移，是必須具名的實現事件；round704「失敗原因沒落盤」是量具假影

（2026-09-04 11:30–12:0x UTC。稽核輪：不改實驗程式碼，只裁決＋開提案。run `runs/g_r447_conform_lcb2`
仍活著（PID 2827732，ELAPSED 05:08），本輪所有數字取自 rows 181 行、sha256 前 16 碼 `30de90fb2031bb50`；
calls.jsonl 在本輪內從 461 行長到 462 行，各臂請求數會差 1，下面每個表格都標明是哪一刻取的。
**本輪未讀任何結果欄位**（`meets_demand`／`accepted`／`visible_ok`／`response`）；
但開場我用 `tail -5 launch.log` 看到了 5 行逐題結果——與 round703／704 同一個錯，據實記錄，
未做任何聚合、未進入任何判準。）

## 一、裁決題（round704 交來）

> SPEC_GAIN §7 說「延遲是實驗條件」。OFF5 獨有的 2 通失敗＋重試（一通吃滿 600 秒），
> 算不算一次必須在收官具名的實驗條件偏移？

## 二、裁決：**不是條件偏移；是必須具名的實現事件，且要具名的比 round704 提的多三條**

### (a) 「條件」指政策，政策三臂同且已落盤

§7 原文：「endpoint timeout、重試與 backoff 是實驗條件，必須跟結果一起落盤。」這是對**政策**的要求。
本 run `summary.json:request_policy` = `{timeout_s 600, retries 4, backoff_s 2.0, review_timeout_s 380, review_retries 2}`，
`calls.jsonl` 逐通 `(role, timeout_s, retries_max)` 普查：gen 460 通全部 `(600, 4)`，preflight 1 通 `(120, 2)`，
temperature 三臂全 0.7，`server_model` 459 通全 `gemma-4-12b-it-qat`（2 通 None＝那兩通失敗，沒有回應就沒有 server_model）。
端點 `pace_probe.py Q1_endpoint STABLE`（tok/s 四分位 72.87/71.67/72.65/72.96）。
⇒ 政策沒變、端點沒變、模型沒被無聲替換。**條件沒有偏移。**

### (b) 「只落在 OFF5」不是訊號——先算再說

| 量 | 值 |
|---|---|
| gen 請求總數（本輪取樣時刻） | 461（OFF 61／CONFORM 98／OFF5 302） |
| 失敗通 | 2，皆 OFF5 |
| 2 通隨機落在 461 通、兩通都在 OFF5 的機率 | **0.4287** |
| 以合併失敗率 2/461 算 OFF5 期望失敗數 | 1.31 |
| 兩題各臂抽樣數（曝險） | lcb_3776：OFF 1／CONFORM 2／OFF5 6；lcb_3779 同 |

一個 43% 會發生的事不能拿來當「失敗與 OFF5 有關」的證據。曝險與抽樣數成正比，OFF5 就是抽最多的那條臂。

### (c) 機制：失控長輸出的尾巴，三臂都有、抽越多越常碰到

失敗原因**有**落盤（`calls.jsonl` 的 `error` 鍵；見 §三）：

```
line 103  OFF5 lcb_3776 gen att=1  latency 600059 ms   error: 'TimeoutError: timed out'
line 138  OFF5 lcb_3779 gen att=1  latency 292574 ms   error: 'HTTPError: HTTP Error 400: Bad Request | body={"error":"Context size has been exceeded."}'
```

- line 138 的 292.574 s，與同題另一通**成功**的 careful-1 呼叫（15319 completion tokens、292.586 s）幾乎同長
  ⇒ 它是生成到某個長度上限被端點切掉，不是連線抖動。
- line 103 的 600 s，以重試那通的速率（11320 tok／205 s ≈ 55 tok/s）推算 ≈ 33k tokens，
  與全 run 最長完成 33974 tokens 同量級 ⇒ **同一個機制**（推論，標為推論）。
- 這條尾巴不是 OFF5 專屬：ok 的 gen 通裡 completion_tokens > 10000 的比例 OFF 3.28%／CONFORM **5.10%**／OFF5 3.00%，
  全 run 最長的 33974 那通是 **CONFORM** 的。

⇒ 這是 gemma-4-12b 在 LCB 上的性質，任何臂抽越多曝險越多。**它是「OFF5 的成本」的一部分，不是混淆變數。**

### (d) 開放問題（不當結論）

8766 讀到 gemma 在 1004 的 `loaded_context_length = 262144`，而 line 138 在 ≈15k tokens 就吃到「Context size has been exceeded」。
兩者對不上。可能是並行 slot 均分 context、也可能是中轉自己的上限——**本輪沒查、不猜**。它不影響裁決
（(b)(c) 都不依賴這個數），但收官要照實寫「400 的來源未歸因」。

## 三、round704 的「可觀測性缺口」是量具假影——`calls_audit.py` 自己把 `error` 剝掉再報「沒有」

round704 寫：「失敗通的 `response` 是 `None`，也沒有任何 `error` 欄位 … Q4 在這份落盤資料上答不出來 … 這是 infra 的可觀測性缺口」。
**三句都錯**，根因在量具：

1. `brain_cline.py:181-207`（round662 修的）失敗通**一定**寫 `"error": last_err`，HTTPError 還附 body 前 2000 字。
   原始 `calls.jsonl` 鍵普查：`error` 出現 2 次＝失敗通數。
2. `calls_audit.py:38 CALL_FIELDS` 沒有 `error`；`main()` 的結構性白名單在進 `audit()` 之前就把它剝掉；
   `audit()` line 110 的 `bool(c.get("error") or c.get("response"))` 因此**永遠** False ⇒ `failures_with_reason_recorded` 恆 0。
3. 更糟的是 F7：`ck("F7 失敗原因未落盤時記為 0", a2["failures_with_reason_recorded"] == 0)`——
   把**假設的答案**寫成預期值，測試在守護一個錯誤；沒有反向夾具「有 error 時記為 N」。
   這與 r695「夾具從被測 helper 導出 ⇒ 擋門結構上看不見」同型：白名單投影漏掉的鍵，任何下游測試都看不見。

`pace_probe.py:24` 同樣剝掉 `error`，但它**不宣稱**讀它 ⇒ 沒有假影，不必動。

### 提案 P-R447-AUDIT-1（給 opus 輪動手，稽核輪不改碼）

- `CALL_FIELDS` 加 `"error"`。它是 infra 字串、不是結果欄位，F8「把結果欄位整批拿掉輸出逐鍵相同」仍應成立。
- F7 改雙向：無 error ⇒ 0；夾具塞 k 通帶 `error` 的失敗通 ⇒ 恰 k。
- 加突變體 M6「白名單剝掉 error」，判準是 F7b 吐的數字從 k 掉到 0（不是 rc≠0）。
- 修後對 r447 的驗收：`failures_with_reason_recorded == failed_calls`（本輪取樣時應為 2）。
- 順手：`failure_detail[].reason` 直接印 error 字串前 200 字，讓收官不必再手翻 calls.jsonl。

## 四、收官必須具名的五條（取代 round704 §「下一輪」第 5 點 (a)）

1. 每臂失敗通數＋原因字串逐字（本輪：OFF 0／CONFORM 0／OFF5 2 = 1 TimeoutError + 1 HTTP 400 context exceeded）。
2. OFF5 的 gen 牆鐘含 **892.6 s 死時間（占 OFF5 gen 牆鐘 11537 s 的 7.74%）**。任何延遲／牆鐘型指標對 OFF5 報兩個數（含死時間／不含）。
3. **重試＝重抽**：OFF5 有 2/302（0.66%）的候選是第二次抽樣——丟掉失控輸出再抽一份。這是一個對 OFF5 **有利**的微小選擇效應
   （被丟掉的多半是截斷垃圾）。量級太小不修正，但要寫出來。
4. 結論只在研究 deadline（600 s × 4 次重試）下成立。§7 明文 fail-fast 設定不可混算：在短 deadline 下這 2 通會變 void，
   OFF5 交付率下修。**CONFORM vs OFF5 的任何結論不可移植到短 deadline 的產品設定。**
5. 失敗原因**已落盤**，Q4 可答；round704 的「可觀測性缺口」收回。400 的來源未歸因（§二(d)）。

## 五、推翻條件（事前寫死，後輪觸發了照實寫、不當場補判準）

- run 結束時 OFF5 失敗通 ≥ 15（≈5% 的 OFF5 請求）或任一臂 `infra_void > 0` ⇒ 本裁決升級為「條件偏移」，重裁。
- 失敗的 task 在**其他臂**也出現失敗 ⇒ 題目相關，§二(b) 收回。
- `Q1_endpoint` 變 UNSTABLE ⇒ §二(a) 收回。
- 修好 `calls_audit.py` 後 r447 的 `failures_with_reason_recorded ≠ failed_calls` ⇒ §三 的根因歸錯了，重查。

---

## 六、P-R447-AUDIT-1 實作完成（round706，Opus 5；稽核輪提案 → opus 輪動手）

提案四點全數落地，另補兩點（下方標 ＋）：

| 提案 | 做法 | 驗收 |
|---|---|---|
| `CALL_FIELDS` 加 `"error"` | 已加；F8「拿掉結果欄位輸出逐鍵相同」仍 PASS | selftest F8 PASS |
| F7 改雙向 | F7a 無 error→0；F7b 夾具塞 2 通帶 error→恰 2；F7b2 分母沒跟著變 | PASS |
| 突變體 M6「白名單剝掉 error」 | 判準是 **F7 那個數字 2→0**，不是 rc≠0、不是 verdict | PASS |
| r447 驗收 | `failures_with_reason_recorded == failed_calls`（快照時 2==2） | PASS |
| `failure_detail[].reason` | 直接印 error 前 200 字 | 見下 |

＋ **`_project_call()`：投影只有一份，`main()` 與 selftest 夾具共用。**
原本夾具造的是「原始 calls」，而真資料進 `audit()` 前已被 `main()` 投影過 ⇒
**投影本身的缺陷（正是這一個）結構上沒有任何夾具看得見**（r699 那型）。不共用同一條，
M6 就只是「假裝有這個 bug」而不是「重演這個 bug」。

＋ **`c.get("response")` 那半個子句原本是死碼**（`response` 也不在白名單上，恆為 None）。
沒有一起處理的話，修完 `error` 之後它仍是死碼（r675 型）。做法不是把 `response` 加進白名單
（那是模型輸出＝結果內容，整包帶進來會讓「期中跑不構成序貫決策污染」失效），而是投影時
**只帶一個 bool `has_response`、不帶內容**；F7d 用「只有 response 沒有 error」的夾具證明它是活的，
F7e 證明投影裡沒有 `response` 本身，M7 是它的突變體。

**真資料上重演，不只夾具**（這條比 selftest 硬）：

```
乾淨      failures_with_reason_recorded 2   failed_calls 2   verdict ACCOUNTING_CONSISTENT
MUTANT=whitelist_strips_error  →  failures_with_reason_recorded 0   failed_calls 2   verdict 不變
```

`0` 逐字重現 round704／705 觀察到的那個數字 ⇒ 根因鏈（白名單剝掉 → `get("error")` 恆 False →
恆報 0 → F7 把 0 寫成預期值）是量出來的，不是推論的。

**⚠ verdict 在 M6/M7 下都不變**（帳目恆等式與失敗原因無關）⇒ 若沿用既有突變體迴圈的
「verdict 必須改判」判法，這兩條會是乾淨 PASS ／植入缺陷仍 PASS 的假測試。已各加一條
`突變後 verdict 不變` 把這件事釘成可見的。

**這支尺不碰結果欄位，本次修改不改變 r447 的任何實驗數字**——它改變的是收官報告能不能
具名寫出「兩通失敗各自為什麼」。DECISION §四 第 1 條（每臂失敗數＋原因逐字）現在有機器來源：

```
OFF5 lcb_3776 gen lat_ms=600059 | TimeoutError: timed out
OFF5 lcb_3779 gen lat_ms=292574 | HTTPError: HTTP Error 400: Bad Request | body={"error":"Context size has been exceeded."}
```

§五 開放問題「400 來源未歸因」**維持開放**（本輪沒查，也不猜）。
