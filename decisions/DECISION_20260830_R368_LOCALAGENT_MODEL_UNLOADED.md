# DECISION 2026-08-30（round368，Sonnet 5）：`local` 輪次連續 7 次失敗的根因是
「Model unloaded」，不是 NEXT_MODEL 讀寫機制——加了 30s 定長重試等模型換回來

## 觸發：round362-367 連六輪都在猜 NEXT_MODEL 為什麼「消失」，沒人查 loop.log

round367 已經正確推翻了「NEXT_MODEL 沒被讀取」的假說（讀 `bin/loop.sh` 源碼
證實讀完就 `rm -f`，這是設計行為）。但 round367 沒有走完下一步：它猜「可能是
prose 沒有對應真的 `echo local > NEXT_MODEL` 指令」，並留給下一輪驗證。

本輪開場核對 `~/vacant/logs/loop.log`，答案原來一直都在那裡、六輪都沒人看：
**`local` 分支確實每次都被正確派工**，但**連續 7 輪（iter 4661/4663/4665/
4667/4669/4671/4673）全部 rc=1**，錯誤訊息一致是：

```
模型連續 4 次失敗：HTTPError: HTTP Error 400: Bad Request
```

`loop.sh` 的 fallback 邏輯本身沒問題（「本地輪次 rc=1，下一輪退回 sonnet」），
這正是為什麼交替觀察到「一輪 local 派工＋下一輪 sonnet」的模式——**看起來像
NEXT_MODEL 神祕消失，其實是 local 每次都在真的執行、然後真的失敗**。

## 根因：LM Studio 後端在跟決定性 run 搶記憶體時把模型換出

`localagent-*.jsonl` 裡失敗前的 prompt_tokens 從 11964 到 21380 都有，不是
固定的 context 長度牆——排除了「對話太長超過 context window」的假說。

直接對 `100.119.113.56:8765` 打探針重現：

- 6 次獨立小請求全部秒回，backend 本身健康。
- 模擬 `localagent.py` 的真實 tool-calling 對話（同一個 `qwen/qwen3.6-35b-a3b`
  模型＋`tools` 參數），跑到 turn26（prompt_tokens=10249）時直接重現：
  ```
  HTTPError 400 body: {"error":"Model unloaded."}
  ```

**根因是資源競爭**：決定性 run（`g_r356_3arm_20260830`，PID 2266603）本身
同時對 `qwen/qwen3.6-35b-a3b` 與 `gemma-4-12b-it-qat` 兩顆模型下請求，
`localagent.py` 的預設模型也是 `qwen/qwen3.6-35b-a3b`（round147 之前的
記憶已經記過「兩個 run 同時打同一個 LM Studio 會互相拖慢」，但這次不只是
拖慢，是**共享 GPU 記憶體不夠同時常駐兩顆模型，LM Studio 換頁把
localagent 這支的模型換出**，回 HTTP 200-shaped 400（body 是錯誤物件，
跟 round356 記過的「中轉回 200 但 body 是錯誤」是同一個機制的另一種
呈現）。

`localagent.py:complete()` 原本的重試退避是指數 2/4/8/16s（總計 30s，
3 次重試間隔），對「等模型重新載入」這種秒級以上的操作明顯不夠——
4 次嘗試全部落在同一次換出視窗裡，於是**必然**連續 4 次失敗，不是機率性
的 17% 隨機噴錯（跟決定性 run 自己的 error_rate 度量的是不同的失敗模式，
不能拿那個基線去估 local 的失敗率）。

## 修法（低風險、範圍侷限）

`ops/localagent.py` 的 `Session.complete()`：偵測錯誤訊息含
`"unloaded"`（不分大小寫）時，改用固定 30s 等待，而不是原本的指數退避
（原本的 2/4/8s 對這個錯誤類型完全用不到，因為它們都在同一個換出視窗內）。
其他錯誤類型（timeout、terminated 等瞬時錯誤）維持原本的指數退避，不動。

沒有改重試次數（仍是預設 4 次）、沒有改 `DEFAULT_MODEL`、沒有換後端。
3 次重試間隔 × 30s = 90s 的等待預算，足以覆蓋大多數模型重載時間，
但**沒有實測驗證修好**（下一個 local 輪次會是第一次實測，可能仍不夠長，
也可能決定性 run 換模型的頻率高到 90s 內又被換出第二次）。

## 什麼情況下推翻

- 下一個 `local` 輪次如果仍然 rc=1 且錯誤仍是 `unloaded`，代表 90s 不夠，
  該加大等待或加重試次數，而不是懷疑這個根因判斷錯了。
- 如果決定性 run（`g_r356_3arm_20260830`）跑完結束，「兩個 run 搶
  記憶體」這個條件會自然消失——那之後如果 local 輪次還在失敗，要回頭
  查是不是這次修法本身有 bug，而不是资源競爭。
- 這個修法**沒有解決根本問題**（GPU 記憶體不夠同時常駐兩顆模型是硬體
  限制，不是能靠重試繞開的），只是把「必然失敗」降級成「大機率等一下
  就恢復」。如果決定性 run 之後常態化（不只是這一輪跑一次），值得考慮
  讓 `localagent.py` 改用決定性 run 沒在用的模型（例如只用
  `gemma-4-12b-it-qat`）來降低碰撞機率——本輪判斷這個改動的驗證成本
  比先加長等待再觀察高，所以先做便宜的那個。
