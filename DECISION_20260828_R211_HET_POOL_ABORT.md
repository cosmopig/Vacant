# DECISION 20260828 round211 — 異質池 run 中止（calibration 卡死）

## 背景

round210 啟動 `runs/g_het_r210_20260828`（PID 2119690），池子
`qwen/qwen3.6-35b-a3b` + `qwen/qwen3.8-27b`，並預先寫死 Gate H（能力異質
前提檢查）與 Gate T（吞吐量門檻，OFF 臂 ≥30 筆 gen 後推算 >12 小時就停）。
round211 開場發現 run 還活著，進入監看。

## 觀察到的事實（round211，2026-08-28 UTC 11:58-12:03）

`runs/g_het_r210_20260828/calls.jsonl` 在 kill 前的完整內容：

- `preflight`：3 筆。`qwen/qwen3.6-35b-a3b` 5174ms ok。`qwen/qwen3.8-27b`
  attempt1 120088ms **失敗**、attempt2（記錄成 `qwen_qwen3.8-27b`）73920ms ok
  ——**預檢當時就已經不穩，只是剛好第二次嘗試撞進去**。
- `calibration`：12 筆，**全部屬於同一題** `mbppplus_Mbpp/84`（12 題 calibration
  的第 1 題，跑了 39 分鐘還沒進第 2 題）：
  - `qwen/qwen3.6-35b-a3b` 3 個 agent，attempt=1 全部 ok=True，
    latency **345982 / 409715 / 454050 ms**（5.8–7.6 分鐘）。
  - `qwen/qwen3.8-27b` 3 個 agent（hasty-2/careful-2/plain-2），
    attempt=1,2,3 全部 ok=False，latency 全部落在 **600034–600109 ms**
    （逼近 `--request-timeout-s 600` 的天花板，`error: TimeoutError`）。
    `retries_max=4`，卡在 attempt 3/4。

**外插**：`qwen3.8-27b` 每個 agent 4 次 attempt 全失敗要燒 4×600s=2400s
（40分鐘），且 `calibrate_pool()` 用 `ThreadPoolExecutor` 對 6 個 agent
一次 `pool.map`，單題耗時取決於最慢的 agent ⇒ 單題 ≈40 分鐘。
12 題 ⇒ calibration 本身要燒 **~8 小時**，燒完之後 `calibration_ready()`
（`ops/gain/gain_run.py:613-623`）因為 `qwen3.8-27b` 的 `infra_void>0`
必定回傳 False，程式本身會 `raise SystemExit`（`gain_run.py:794-798`）
——**跑完 8 小時只會得到「calibration 沒過」，不會產出任何 arm 資料**。

## 決定：kill 掉，不等它自己 SystemExit

`kill -TERM 2119690` @ 12:03:09 UTC，行程立即結束（`ps -p` 查無此行程）。
確認 `ps -eo cmd | grep -c "^python3 ops/gain/gain_run\.py"` = 0，沒有殘留。

**為什麼在 Gate T 字面條件（OFF 臂 ≥30 筆 gen）達成之前就出手**：Gate T
的立法精神是「後端撐不住異質池就停，不要繼續燒」，寫的時候假設失敗會發生
在 OFF 臂。但這次失敗發生得更早——**calibration 階段本身結構性地不可能
成功**（`calibration_ready()` 是程式碼裡的既有硬性檢查，不是我發明的新判準），
繼續等只是把同一個「後端撐不住」的結論，用 8 小時去換一次程式自己會
喊出來的 SystemExit。round210 自己也把這個結果標成「很可能」發生。
這不是重新設計實驗，是提早執行 round210 已經寫好的 contingency
（見 round210 交棒最後一段：「如果 Gate T 觸發，pivot 方向……」）。

## 額外診斷（kill 之後，零實驗汙染，純粹排查故障點）

行程已死、無競爭負載下，直接 curl 8765 中轉：

```
qwen/qwen3.6-35b-a3b  solo: HTTP=200, 8.495s，回應正常（"OK"）
qwen/qwen3.8-27b      solo: 120s 逾時，0 bytes（curl: (28) Operation timed out）
```

`/v1/models` 仍然列出 `qwen/qwen3.8-27b`。

**結論：這不是「後端擠不下兩個模型」的併發問題，是 `qwen/qwen3.8-27b`
這個 model 本身目前在這個後端上是掛的／沒有真的在服務**（列在 `/v1/models`
≠ 載得動、答得出來——跟 round210 發現 `gemma-4-12b-it-qat` 的模式一樣，
只是這次連 400 錯誤都沒有，是純逾時）。`qwen3.6` 單獨測仍是健康基準
（8.5s，跟同質池那次的 ~10s/筆一致）。

## 對 R210 prereg 的影響

- Gate H、Gate T **都沒有被字面觸發**（沒有任何一筆 `role=gen`），
  round210 的 prereg 本身沒有錯，只是沒預見到 calibration 階段就會卡死。
- **`qwen/qwen3.8-27b` 目前不能用**，不只是「跟 qwen3.6 搭配時不能用」。
  下一輪如果還想追異質池，先對候選的第二個 model 做**單獨 solo curl 測試**
  （不進 runner），確認它在沒有任何併發負載下能在合理時間內回應，再進
  runner 的模型池預檢——**模型池預檢本身測過一次（120s 超時內成功一次）
  不夠**，round210 的預檢就是被這個「偶爾成功一次」騙過去的活生生案例
  （attempt2 that one 73920ms 剛好在 120s 預檢視窗內擠進去）。

## 沒做的事（照實寫）

- 沒有刪除 `runs/g_het_r210_20260828`（保留，`calls.jsonl` 這次診斷過程
  沒有再寫入，因為行程已死；診斷 curl 是獨立呼叫沒有寫進這個目錄）。
- 沒有修改 `gain_run.py`／`brain_cline.py`／`POOL` 任何一行。
- 沒有重新設計實驗方向或挑新的 pivot——那是下一輪（Opus）的判斷。
- 沒有對這台 relay 後端做任何設定變更（不在本 loop 權限內）。

## 推翻條件

若下一輪發現 `qwen/qwen3.8-27b` solo curl 測試變成能在 <30s 內回應
（表示只是暫時性狀態，例如對面機器剛好在重載模型），
則本輪「這個 model 目前壞掉」的結論要重新驗證，不能直接沿用。
