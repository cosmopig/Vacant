# round460 決定：殺掉孤兒 OFF run `g_off_failure_rate_20260901c`，只留 scale2 ON

## 發現了什麼

本輪開場重複 run 檢查（錨行首）發現**兩個** `gain_run.py` 同時在跑：

1. `g_on_qwen_only_scale2_20260901`（PID 2513538，round456 啟動，
   round458/459 持續同步中，elapsed ~1h46m，7/60 rows）
2. `g_off_failure_rate_20260901c`（PID 2516646，elapsed ~33min，16/60 rows，
   **`GAIN_STATE.md` 完全沒有記錄這次啟動，是孤兒 run**）

時間軸重建：`g_off_failure_rate_20260901c` 於 22:56:26 啟動——晚於
round459 commit（e88eef8，22:53 前後）、早於本輪（round460）開場
（23:29）。中間有一輪執行過、啟動了這個 run，然後**沒有 commit、
沒有寫 GAIN_STATE.md 就結束了**。這跟 round446 記錄的模式完全一樣
（見 GAIN_STATE.md round446 段落「孤兒 run 是怎麼來的」）：本地輪次
（`local` 模型）失敗或未完整收尾時會留下這種痕跡。

`_c` 的命名延續今天早上（10:46-10:50）就存在、已經失敗放棄的
`g_off_failure_rate_20260901`（擋門拒絕重複計數）與
`g_off_failure_rate_20260901b`（gemma 預檢失敗）——換句話說，這個孤兒
輪次是在**重做已經在 round446-449 answered 過的問題**（OFF 失敗率），
且用的種子 `g-off-failure-rate-20260901` 跟 round449 定案的
`g-r212-route-20260828`／`g_off5_qwen_only` 系列不同，是另一批獨立
抽樣，不是接續。

## 為什麼殺掉 OFF 留 ON

1. **重複性**：OFF 失敗率這個問題本迴圈已經在 round449 確立
   19.3%（`g_off5_qwen_only_20260901`，n=60，落在可用窗口）。這個孤兒
   run 是同一個問題的第三次獨立測量，不是頻譜上還沒回答的新問題。
2. **違反協定**：兩個 run 同時打同一顆後端 GPU 會互相拖慢，而
   SPEC_GAIN §7 把延遲當實驗條件——這個孤兒 run 啟動時完全沒有做
   「開跑前確認沒有別的 gain_run 在跑」這一步（scale2 ON 當時已經跑
   了快一個半小時），違反總綱明文寫的規則。
3. **時序上不影響 round459 的結論**：round459 的 void 率分析
   （22:43-22:53）發生在孤兒 OFF run 啟動（22:56）**之前**，round459
   對 scale2 ON 66.7% void 率的判讀不受這個孤兒 run 汙染。但**往後
   如果不介入，scale2 ON 剩餘的呼叫會繼續跟這個孤兒 run 搶資源**，
   讓已經很慢的 scale2 ON（7/60，1h46m）更慢，且孤兒 run 自己的
   infra_void／timeout 讀數也會被這段共享期間的壅塞汙染，兩敗俱傷。
4. **機會成本**：scale2 ON 是 round456 正式決定、目標是把配對樣本
   推到 n≈70 做等預算檢定力分析（round456 的 equal-budget n=35 是
   noise，需要更大樣本）——這是本迴圈目前唯一還沒回答的「有成效」
   判準第 3 條。保護它比累加第三批重複的 OFF 資料更有價值。

## 做了什麼

```
kill -TERM 2516646   # 正常結束，非 -9
sleep 8
ps -p 2516646        → 行程已消失，正常退出
```

`runs/g_off_failure_rate_20260901c/`**不刪除**（鐵律：不要刪任何 run
目錄）。最終落盤：n=16，meets_demand=10，failure_rate=0.375（37.5%，
落在可用窗口內，跟 round449 的 19.3% 不同批次、不同種子，僅供參考，
**不拿來跟既有 OFF 基準合併**——樣本太小且是不同種子，混用不成立）。

## 推翻條件

若未來又出現孤兒 run，且此時 scale2 ON（或任何當時的主力 run）已經
停止／完成，則不適用本決定的邏輯——本決定只在「兩者同時存活且其中
一個是未經記錄的孤兒」這個情境下成立。若之後想重新測 OFF 失敗率
（例如想確認 19.3% 在不同種子下穩不穩），**用新的、有記錄的正式啟動**
（寫進 GAIN_STATE.md 再開），不要撿孤兒 run 的資料當正式測量。
