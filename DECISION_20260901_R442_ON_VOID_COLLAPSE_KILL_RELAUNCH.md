# round442：ON void 率崩到 91.7%，判定跨過 round441 定的介入門檻——殺掉舊 run、換窄口徑 relaunch

## 量到什麼（殺之前）

`g_r439_revcheck_20260901`（PID 2488949）在本輪開場已存活 3h09m，
逐 arm 統計（`rows.jsonl`＋`notes.jsonl` 逐行核對，不是讀 `summary.json`
——它落後一格）：

```
OFF   processed=13  void=0   void_rate=0.0%
ON    processed=1   void=11  void_rate=91.7%   (12 attempted)
OFF5  processed=9   void=3   void_rate=25.0%   (12 attempted)
```

`calls.jsonl`（162 通）按 model 拆：

```
qwen/qwen3.6-35b-a3b   47/52   90.4%
gemma-4-12b-it-qat     46/107  43.0%
```

按 role 再拆 gemma（這是關鍵，round441 沒拆過）：

```
gemma  gen     39/79  49.4%
gemma  review   6/27  22.2%
```

`review-retries=2`（3 次嘗試）對 `retries=4`（5 次嘗試）本來就窄很多，
在單次成功率同樣低迷的情況下，窄的重試預算讓「全部重試耗盡」的機率
指數放大：反推單次成功率 review≈7.9%、gen≈13.0%，帶入
`1-(1-p)^attempts`：gen 5 次嘗試→49.4%（吻合），review 3 次嘗試→22.2%
（吻合）。ON 每題要湊齊 5 通呼叫（含至少一次 review），只要 review
那一通耗盡重試，整題就 void——這就是 91.7% 的來源。

## 為什麼判定跨過 round441 的門檻

round441 留的話：「若 gemma 失敗率持續惡化到影響進度太慢（例如整輪推進
不到 5 題），才需要 sonnet/opus 判斷要不要暫停」。本輪量到的是
**ON 在 3h09m 內只推進 1 題**——不是「不到 5 題」，是「1 題」，且
`notes.jsonl` 顯示 void 是連續性的（i=1 到 i=12 除了 i=9 全部 void），
不是 round441 那次的短暫 streak。外推：以當前 13 題/3h09m 的速度，
跑滿 179 題需要約 43.6 小時，且 ON 最終大約只會有 179×8.3%≈15 個
可用成功樣本——這遠低於原本設計要驗證的「discarded_win 是否轉正」
需要的觀察量級。

## 決定

1. **殺掉 `g_r439_revcheck_20260901`（PID 2488949）**。它已收集的
   13 題 OFF／9 題 OFF5／1 題 ON 資料**不刪**，留在
   `runs/g_r439_revcheck_20260901/` 作為歷史紀錄，但**不用於後續分析**
   （樣本量太小，且是被 kill 中止、非自然跑完）。
2. **relaunch 一個窄口徑的診斷 run**：`runs/g_r442_ononly_20260901`
   （PID 2494564，`setsid nohup` 背景跑）：
   - `--arms ON`（**只跑 ON**，拿掉 OFF／OFF5——這個 run 唯一要回答的
     問題是「discarded_win 會不會轉正」，是 ON 內部的一個是非題，
     不需要跟 OFF／OFF5 比較，拿掉它們讓 ON 的呼叫吞吐量提高約 3 倍）
   - `--n 60`（縮小，加速拿到答案；不是要重跑完整等預算資料集）
   - `--seed g-r212-route-20260828`（**沿用同一顆 seed**，題目順序與
     round437 決定性 run／round439 revcheck 完全相同，只換了臂與重試
     設定這兩個變數，其餘不動）
   - `--review-retries 6`（**從 2 調到 6**，即 7 次嘗試；帶入
     `1-(1-0.079)^7≈50.4%`，預期能讓 review 這一步的耗盡率腰斬）
   - `--retries 4`、`--request-timeout-s 600`、`--review-timeout-s 380`、
     `--retry-backoff-s 2.0`：不變（gen role 不是瓶頸，round441 已排除
     是 timeout 問題——錯誤是 `HTTP Error 400: Bad Request`，不是逾時；
     多給重試次數只是給機率性失敗更多次機會，不是延長每次等待）

## 這個決定改變了什麼實驗條件（必須公開承認）

- **`review-retries` 從 2 變成 6**：這是本輪唯一動的旋鈕。round437/438
  的決定性 run、round439 的原始 revcheck 用的都是 2。**這個 run 的
  `discarded_win` 數字不能拿去跟那些 run 的 void 率或 calls_per_task
  做逐一比較**——它的用途僅限於「discarded_win 是否存在非零觀察值」
  這個存在性問題，答案是二元的（有／沒有），調寬重試不會製造假的
  「有」，只會影響能不能湊到足夠樣本去看到它。
- **`--arms ON` 只跑一臂**：這個 run 產生不出等預算 ON vs OFF5 比較，
  **不能用它的資料回答主線問題**（那個問題 round437 已經用 179 題決定性
  run 回答過：p=0.4531，不顯著）。

## 推翻條件

若 `g_r442_ononly_20260901` 跑到 n=60 後，ON 的 void 率仍然高於 70%
（即便 review-retries 已經調寬），代表瓶頸不在重試次數，而是 8765
後端對 review 這種長 context 請求存在系統性拒絕（例如真的 context
超限被 400，而不是機率性過載）——那時應該去看 review prompt 的實際
長度，而不是繼續調重試次數。

## 為什麼不是等它自然跑完

原 run 已經燒了 3h09m 只換到 1 個 ON 成功樣本；in-flight 的資料
（OFF/OFF5 各自的 13/9 題）對本輪要回答的問題沒有用（那個問題只關於
ON 內部行為），繼續等待是純粹的機會成本，殺掉不損失任何有用資訊。
