# 2026-08-29（round274）：`review_timeout_s=60` 在異質池下把 ON 臂燒成接近全滅，中止並改參數重跑

## 發現什麼

`runs/g_het2_r271_20260829`（ON,OFF5，qwen/qwen3.6-35b-a3b + gemma-4-12b-it-qat
異質池，round271 啟動）跑了 1h49m，calibration 72/72 全部完成（Gate H 重新驗證
accuracy_spread 仍在門檻之上），**但 ON 臂的正式題連一筆都沒有寫進 rows.jsonl**。
`notes.jsonl` 顯示：**題序前 6 題（554/296/123/305/70/425）全部 6/6 因為
review 逾時變成 infra_void**，逾時訊息全部是同一種：
`<agent> 重試 2 次仍失敗：TimeoutError: timed out`。

`calls.jsonl` 按 role 拆開：

```
role=gen         7 次呼叫，7 次成功（qwen 側觀測延遲 57.7s–161.1s，gemma 側 7.2s–26.5s）
role=review      16 次呼叫，只有 3 次成功（3 次全部是 gemma 的 hasty-2，7.2–8.4s）
                 13 次逾時，全部落在 60021–60062ms —— 卡在 review_timeout_s=60 這條線上
```

## 為什麼不是運氣不好，是結構性必然

`_diverse_reviewers()`（`ops/gain/gain_run.py:390`）用「model family 沒出現過」
當篩選條件挑 k_review=3 個評審。這個池只有兩個 model family（`qwen` 與
`gemma-4-12b-it-qat`），所以**演算法保證每一題的 3 個評審裡至少有 1 個、常態是
2 個 qwen family agent**（worker 若是 qwen，剩 5 個候選裡 2 qwen+3 gemma，
第一輪迴圈固定先各挑 1 個湊齊兩個 family；worker 若是 gemma，剩 3 qwen+2 gemma，
一樣先各挑 1 個）。

而 qwen 這個 model 在這個中轉後端上，`gen` role 觀測延遲**穩定在 60–161 秒**，
不是尾端偶爾超標，是**中位數就超過 60 秒**。`review_timeout_s=60`（+ retries=2）
對 qwen 側評審而言，等於「保底失敗兩次再放棄」——不是機率問題，是幾乎必然。

`review_timeout_s=60` 這個預設值的歷史脈絡（見 `arm_on()` 的 docstring 和
round22/23 的 `DECISION_20260824_SERIALIZE_CONCURRENT_CALLS.md`）：當初量到的
17/30=57% review 失敗率，根因是**同一個模型家族、三個 reviewer 併發送出**互相
排隊超時，用序列送出（已經在跑的程式碼裡）解決了。**那次的模型池是同質的**，
60 秒對那個模型家族是合理的；這次換成異質池，其中一個 family 本身單次呼叫就
比 60 秒長，序列化解決的是併發排隊問題，沒有解決「有些 model 本來就比這個
deadline 慢」的問題。是遺留參數沒有跟著換池子重新校準，不是隨機噪音——同一批
6 題、100% 命中同一種失敗，換誰跑都會是這個結果。

## 決定

**中止 round271 的 ON,OFF5 run**（PID 2175195，`kill`，已確認行程結束，
`rows.jsonl` 從未建立，沒有半成品行要處理），**已量到的證據原樣 commit
不刪**（`runs/g_het2_r271_20260829/{calls,notes}.jsonl`＋這次收尾前才寫出的
`calibration_rows.jsonl`／`summary.json`）。

**換 `--review-timeout-s` 從預設 60 提高到 240**（沿用 `ClineBrain.__init__`
本來就有的 class-level 預設 `timeout_s: int = 240`，不是憑空選的數字——是
程式碼裡已經存在、原本就打算給「沒有明確覆蓋」場合用的值，比目前觀測到的
qwen 最大延遲 161s 留有安全邊界，同時仍遠低於 `request_timeout_s=600`，
不會讓單題最壞情況失控地長）。**`--review-retries` 維持 2 不動**——問題根因
是單次 deadline 太短，不是重試次數不夠。

**用新的輸出目錄重跑**：`gain_run.py` 對已有產物的輸出目錄會直接拒絕
（`輸出目錄已有實驗產物，拒絕 append 造成重複計數`，line 762-766），所以
不能沿用 `g_het2_r271_20260829`。Calibration 需要重新跑一次（12 題×6 agent，
不受 review timeout 影響，預期會重現同樣的 Gate H 通過結果，但**這是重新量
不是複製前一次的數字**）。

## 這算不算「挑對自己有利的設定」

不算——這是把一個**會讓 ON 臂結構性產生不出資料**的參數修正到「至少測得到」
的水準，跟挑一個讓 ON 看起來比較會贏的設定是兩回事。修正前 ON 臂的有效 n
趨近於 0（不是「差」，是「量不到」），這與 SPEC_GAIN 開場交代的「先讓量測有
訊號」矛盾。240s 這個值本身也不是為了讓某個特定結果好看而挑的——它是程式碼
既有的另一個預設值，且留了安全邊界，會後續驗證。

## 什麼條件下這個決定該被推翻

- 如果換 240s 之後 review 逾時率仍然顯著（例如 >10%），代表 qwen 側延遲比
  目前觀測到的 161s 上限還要長尾更多，需要再往上調或改回同質池。
- 如果因為 review deadline 拉長，單題總耗時暴漲導致 n=179 在合理時間內
  跑不完，需要重新評估要不要縮小 n 或縮短其他階段的 timeout 來補償。

## 重啟指令（round274 執行）

```bash
VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
VACANT_GAIN_API=http://100.119.113.56:8765/v1/chat/completions \
CLINE_KEYS=/nonexistent \
setsid nohup python3 ops/gain/gain_run.py \
  --out runs/g_het2_r274_20260829 --n 179 \
  --seed g-r212-route-20260828 --arms ON,OFF5 --probe-sample 0 --calibration-n 12 \
  --models qwen/qwen3.6-35b-a3b,gemma-4-12b-it-qat \
  --request-timeout-s 600 --review-timeout-s 240 \
  > runs/g_het2_r274_20260829.launch.log 2>&1 &
```
