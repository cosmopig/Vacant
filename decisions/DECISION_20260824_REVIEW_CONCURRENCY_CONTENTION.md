# DECISION 2026-08-24（round 22）：不介入 review-timeout，只記錄成因——量到的是併發搶資源，不是新問題

**寫這份文件的時刻：`g_onoff5_qwenonly_v2_20260824`（PID 1782584，round 12 修好
`--review-timeout-s` 後重開的那支）仍在跑，本文只讀 `calls.jsonl`／`notes.jsonl`
既有紀錄分析，沒有殺行程、沒有改任何程式碼或參數。**

## 一、量到什麼（實測，`calls.jsonl` 37 筆全查不是抽樣）

review 角色的呼叫成功率遠低於 gen／revise：

```
('gen',    True)  7   ('gen',    False) 0
('revise', True)  4   ('revise', False) 0
('review', True) 13   ('review', False) 11   ← 24 筆裡 11 筆逾時失敗（46%）
('preflight', True) 1 ('preflight', False) 1
```

逐筆看 review 呼叫的 `ts_ms`，同一題的 3 個 reviewer **幾乎同時發出**
（時間差 <100ms），例如 `mbppplus_Mbpp/283` 第一次嘗試：
```
1787567114983 plain-1   False 250077ms
1787567114990 hasty-2   False 250085ms
1787567115000 careful-2 False 250095ms
```
三個全部卡滿 250s timeout。第二次重試（1787567367xxx）三個又同時卡滿 250s
⇒ 這一題判 `infra_void`。**即使成功的 review 呼叫，延遲也普遍在 100–240s**
（例：`mbppplus_Mbpp/111` 的 hasty-1 215s、plain-2 241s 才成功）。

## 二、為什麼這不是「250s 選錯了」，是新的成因

round 12（`DECISION_20260824_REVIEW_TIMEOUT_BUG.md`）把 250s 訂在
OFF baseline 量到的 p95(205032ms)～max(358838ms) 之間——**但那個分佈是
單一序列呼叫量到的**（OFF 沒有併發 reviewer）。`gain_run.py` 的 `arm_on()`
用 `ThreadPoolExecutor.map` **同時**送出 3 個 reviewer 的請求
（`gain_run.py:445-447`，round 12 已經指出這行，但當時只當成「任一個失敗
就整題 void」的機制描述，沒有推論併發本身會把延遲推高）。

本輪量到的證據：3 個併發請求打同一個中轉端點（很可能後面是單一
GPU/LM Studio 實例），實際延遲比 OFF 單發請求的 p95 還高很多——
`mbppplus_Mbpp/111` 的 hasty-1/plain-2 分別 215s／241s 才成功，
已經逼近甚至超過 250s 上限；`mbppplus_Mbpp/463`／`283` 直接全部卡死。
⇒ **250s 這個數字是照「不併發」的分佈校準的，套用在「3 個併發」的情境上
本來就偏樂觀。**

## 三、為什麼本輪不動它

1. **樣本還是太小**（n=24 review 呼叫、5 個完整 task-row）——跟 round21
   的判斷一致（「i=6 判 void(2/6≈33%)，n太小暫不升級」），這條規則本輪
   延續，不因為多算了一次併發機制就破例。
2. **改時間會製造新的實驗條件差異**：若現在拉高 `--review-timeout-s`，
   這支跑到一半的 run 會混進「前半用 250s、後半用更大值」兩種條件，
   之後沒辦法乾淨地說「ON 的 infra_void 率是多少」——比起讓它慢慢跑完，
   混條件的代價更高。
3. **`equal_budget_comparison_valid` 看的是 `calls_used`（=5）不是
   `wall_s`**——就算 review 因為併發搶資源而變慢，只要重試機制最終讓
   `calls_used` 精確等於 5，主要比較（等預算下 ON vs OFF5 的
   `correct_delivery_rate`）不會被這個現象污染，只有**完成這支 run 需要
   的真實時間**會被拉長。所以這是「要等更久」的問題，不是「量到的數字
   會失真」的問題。

## 四、如果 infra_void 最終超過門檻（>10%，呼應 OFF baseline 的
`infra_void > 6` 那條規則移植過來），下一輪該做的事，不是本輪

- 先確認 void 是不是集中在特定 reviewer/worker（呼應 OFF baseline 的
  `failure_concentration_flag` 邏輯）。
- 若 void 均勻分布在 6 個 agent ⇒ 併發搶資源是系統性的，那時候才值得
  考慮：(a) 把 3 個 reviewer 改成序列送出（會拉長 wall_s 但降低併發峰值），
  或 (b) 針對併發情境重新量測延遲分佈、重新校準 `--review-timeout-s`。
  這兩個都是**改變 ON 這隻手臂本身的實作**，要非常謹慎——(a) 會讓 ON
  的 wall_s 相對 OFF5 变得更不利，等於改變了正在被比較的東西本身。

## 五、這份決定什麼條件下該被推翻

- 若下一輪發現 infra_void 已經逼近或超過 10% 門檻 ⇒ 本文的「不動它」
  結論失效，要照第四節動作，而且要先把「條件改變」寫進新的 DECISION。
- 若之後發現併發並非 3 個 reviewer 同時送出而是別的原因（例如後端另有
  他人佔用、非本專案的流量）⇒ 本文的因果推論（併發 review 導致延遲）
  要撤回，需要另外用 `curl` 對端點做隔離測試才能分辨。本輪沒有做隔離
  測試（會佔用同一個資源、可能拖慢正在跑的 run），是刻意放棄的驗證步驟。
