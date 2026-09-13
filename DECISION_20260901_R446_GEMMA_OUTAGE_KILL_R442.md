# DECISION 2026-09-01 round446: gemma-4-12b-it-qat 掛了，殺掉 g_r442_ononly_20260901

## 發現

`g_r442_ononly_20260901`（round442 啟動的 ON-only 診斷，n=60，測試
review-retries 2→6 是否解決 void_rate 暴衝）從 round442 一路跑到本輪，
round443/444/445 三輪都在同步進度，讀出 void_rate 從 91.7% 掉到 10%，
判讀為「review-retries 調寬有效」。

本輪重新檢查 `calls.jsonl` 發現：**`gemma-4-12b-it-qat` 在這個 run 開始
沒多久（約 08:52 起跑，第一筆 gemma 400 錯誤在 09:00:38 UTC）就開始對
每一通請求回 `HTTP 400 Bad Request`，訊息是 `Failed to load model
"gemma-4-12b-it-qat". Error: Operation canceled.`**——直接對後端
`http://100.119.113.56:8765/v1/chat/completions` 送 gemma 請求驗證，
同樣拿到這個 400。這不是這個 run 特有的雜訊，是後端層級的模型載入失敗，
從 round442 relaunch 後幾乎全程都在發生（`tail -200` 的 calls 裡
gemma 佔 81 筆、其中 55 筆是這個 400）。

同時間，人類原始交接檔（round445 之前）裡有一輪嘗試（未落地到
GAIN_STATE.md、疑似是失敗的 local 輪次留下的孤兒產物）留下
`runs/g_off_failure_rate_20260901` 與 `..._20260901b` 兩個目錄：
第一個因為輸出目錄已有殘留檔被 runner 擋門拒絕啟動；第二個嘗試用
`qwen + gemma` 兩個模型家族，**gemma 預檢直接失敗**（同一個 400），
於是那個嘗試改成只用 qwen 啟動了 `g_off_qwen_only_20260901`（OFF-only，
n=60），本輪接手時它已經在跑（etimes ≈ 5 分鐘，2/60 processed）。

## 這代表什麼

round442-445 對 void_rate 91.7%→10% 的「retries 調寬有效」判讀，**至少
部分被 gemma 整段掛掉汙染**：不是「重試次數夠了所以 review 成功」，
更可能是「gemma 那票審查者整段時間都在對 400 重試到力竭，但 6 個
agent 裡還有 qwen 那幾個撐住了 quorum，所以 void_rate 沒有真的暴衝
回 91.7%，可是每個 gemma call 都在 380s timeout × 最多 6 次重試上
燒掉大量 wall-clock」——這也同時解釋了 round444/445 記錄的「步調比
估計慢很多」（901s/題、592s/題）現象：不是模型變慢，是每題都在陪
gemma 撞牆。

**不完全推翻 round442-445 的方向**（void_rate 確實沒有暴衝回 91.7%），
但「review-retries 調寬解決了問題」這個因果判讀站不住——乾淨的驗證
需要在 gemma 正常的情況下重跑，或改用不含 gemma 的池子。

## 決定

1. **殺掉 `g_r442_ononly_20260901`**（`kill -TERM 2494564`，正常結束，
   `summary.json` 落盤有效：13/60 processed、8/13 meets_demand、
   2/13 infra_void）。理由：繼續跑只是繼續在壞掉的後端上燒時間，
   拿到的每一筆新資料都帶著同一個汙染，不值得再等它跑到 60。
   資料保留，不刪除。
2. **讓 `g_off_qwen_only_20260901`（OFF-only、純 qwen）繼續在背景跑**——
   這支完全不碰 gemma，不受這個後端問題影響，而且直接對應總綱最優先
   要答的問題（OFF 失敗率）。
3. **不重啟 ON 診斷**，等 gemma 後端確認恢復正常（下一輪或之後開場先
   `curl` 探一次 `gemma-4-12b-it-qat`）才考慮要不要用同一個 seed 重跑
   一次乾淨版本。

## 推翻條件

- 若下一輪 curl 探測 gemma 已恢復（回 200 而不是 400），且需要重新
  驗證 review-retries=6 的效果，可以用同一組 `--seed
  g-r212-route-20260828` 重跑一個新的 ON-only 診斷（不要覆用
  `g_r442_ononly_20260901` 這個目錄名，它已經是殺掉的舊 run）。
- 若 gemma 持續掛著超過數輪，應該考慮：這個實驗的模型池要不要整個
  改成 qwen-only（跟 `g_off_qwen_only` 對齊），這是要記錄的實驗條件
  改變，不能默默換掉不寫。

## 我沒做的事（誠實列出）

- 沒有能力修復後端（`100.119.113.56:8765` 是遠端算力中轉，不是這台
  機器管的）。只能繞開，不能修。
- 沒有回頭修正 round443/444/445 已經寫進 GAIN_STATE.md 的歷史敘述——
  那些是誠實記錄，本輪的新發現用新的一輪記錄補充/修正判讀，不竄改
  歷史輪次的文字。
