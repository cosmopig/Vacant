# DECISION 2026-08-25（round 82）：探測 gemma-4-12b-it-qat 疑似干擾了正在跑的 g_off371——記錄事故＋修正規則

## 一、背景：為什麼本輪去查第二個模型

round77（`DECISION_20260825_ROUND77_BOUNDS_OVER_BACKFILL.md`）判定 ON vs OFF5
在 MBPP+ 全庫（378 題）上結構性答不出來（需要 n≈1096），並列出三條路
（A 擴大n只答OFF vs ON、B 換更弱的worker把效應量做大、C 接受現況停手），
明確不替 A/B/C 拍板。round78 選擇先做三條路共同前提：把 OFF 擴到全庫
n=371（PID 1833831，`runs/g_off371_20260825`），並寫死 P4 讀出規則：
**全庫失敗率 <25% ⇒ B（弱化 worker）成為必要**。本輪開場讀到的五個連續
觀測點（round79 14題21.43%、round80 19-22題18-21%、round81 25題16.00%、
本輪 39題20.51%）全部落在 <25% 那一格，方向非常一致。

round80 已經指出：現有 persona 池（hasty-1/2 等）**全部共用同一個底層模型**，
只是 prompt 風格不同，不是真的換了更弱的模型——這代表「換 worker」若要真的
拉大失敗率，可能需要**換模型**而不是換 persona 子集。本輪查詢 relay
（`GET http://100.119.113.56:8765/v1/models`）發現除了現用的
`qwen_qwen3.6-35b-a3b`，還有 `gemma-4-12b-it-qat`（12B，明顯小於
qwen3.6-35b-a3b）——這是 Route B「真的換一個更弱的模型」的候選。

## 二、本輪做的探測與其後果（照實寫，不是好看的部分）

用 `curl` 直接對同一個 relay endpoint 送了兩次單次呼叫測試 `gemma-4-12b-it-qat`
（間隔約 3 秒），兩次都得到：

```
{"error": {"message": "Failed to load model \"gemma-4-12b-it-qat\". Error: Operation canceled.", ...}}
```

**這個探測是在 `g_off371` 仍在跑的情況下做的**——沒有先想清楚「同一個 relay
只能載一個模型」這件事：curl 直打 relay 不是開第二支 `gain_run.py`，過去的
規則（「開跑前先 pgrep 確認沒有第二支 run」）只防了「兩支 runner 互相拖慢」，
沒有覆蓋「隨手一個 curl 探測也會跟正在跑的 job 搶同一顆 GPU 的模型槽」。

**時間戳對照（`runs/g_off371_20260825/calls.jsonl`、`notes.jsonl`）**：

```
04:07:05 UTC  本輪 date -u（探測前）
04:0x         curl 探測 gemma #1（"Operation canceled"）
04:0x+3s      curl 探測 gemma #2（同樣失敗）
——
notes.jsonl 記錄兩筆新的 infra_void（本輪讀 analyze_fullbank_off.py 前是
n_void=0/39，本輪讀之後變 n_void=2/39）：
  Mbpp/765  plain-2 重試4次仍失敗：第1次 EmptyResponse（163s後，推理耗盡，
            這筆時間點早於探測、與探測無關）；第2次 04:10:37 附近
            HTTPError 400 Bad Request
  Mbpp/593  hasty-1 重試1次 04:10:37 附近 HTTPError 400 Bad Request
```

第一筆失敗（EmptyResponse，推理 token 用完）是已知的獨立故障模式
（`brain_cline.py` 註解已記載），跟探測無關。**但兩筆 400 Bad Request
與探測的時間窗高度重疊（同在 04:08-04:11 這 3 分鐘內）**，合理懷疑
是本輪的 curl 探測讓 relay 嘗試切換/載入 gemma，干擾了同時段 qwen 那邊
正在處理的請求。**這是時間相關，不是機械證明**——relay 本身的行為
（LM Studio 節點路由、模型槽管理）不透明，無法從 client 端百分之百排除巧合。

## 三、後果評估：run 沒有作廢，但這是不該發生的干擾

```
void_ratio = 2/39 ≈ 4.88%，仍遠低於 SPEC_GAIN §7 的 10% 閘門
```

`g_off371` 本身**沒有被判定作廢**，探測之後 `pgrep` 確認行程仍活著、
`calls.jsonl` 在探測之後（04:12:11 起，careful-1 呼叫成功，93.9s）持續有新的
成功呼叫進來，run 仍在正常前進。**但這不代表探測是安全的**——這次只多花
2 格 infra_void，換一個時機更差的探測（例如節點正卡在關鍵重試視窗）可能
直接把某一格拖進 `>10%` 閘門，讓整條臂作廢，前面幾小時的量測全部作廢。

## 四、修正規則（新增，補在既有「先 pgrep 確認沒有第二支 gain_run.py」之上）

**任何 `gain_run.py` 在跑的時候，不准對同一個 relay endpoint 發任何額外的
model 呼叫——包括手動 curl 探測、smoke test、確認新模型可不可以用。**
連零成本的單次探測都不例外，因為 relay 對「同時服務兩個不同模型」的行為
沒有文件、實測上會回 `Operation canceled`，而失敗處理路徑（重試/backoff）
跟正在跑的 job 共用同一個節點，會互相污染彼此的延遲與成功率。要測新模型，
必須先確認 `pgrep -af "gain_run.py --out"` 是空的。

## 五、對 Route B 設計的影響——不是壞消息，只是還沒能驗證

`gemma-4-12b-it-qat` 是否真的可以在這個 relay 上用，**本輪沒有得到結論**
（"Operation canceled" 不能當成「這個模型不可用」的定論——過去
`DECISION_20260824_NEMOTRON_UNAVAILABLE.md` 就記錄過教訓：探測失敗訊息
本身不是永久狀態的證明，要在乾淨環境下重測才算數）。**下一輪要做的**：
等 `g_off371` 完全結束（`pgrep` 確認行程消失）之後，再單獨、乾淨地重測
`gemma-4-12b-it-qat` 一次，確認它能不能正常回應。若可以，才進入 Route B
的具體設計（n 要多大、pool 怎麼配、`--models` 怎麼寫）。

## 六、什麼條件下這份決定該被推翻

- 若下一輪在 `g_off371` 結束後乾淨重測 `gemma-4-12b-it-qat` 仍然
  "Operation canceled"（不是資源競爭而是模型本身裝不起來），那 Route B
  的「換模型」子選項作廢，退回「換 persona 池」或「換題庫」兩個選項。
- 若日後有更直接的證據（例如 relay 的 log）證明那兩筆 400 Bad Request
  跟本輪的探測完全無關（例如同一時段 relay 本來就在做別的維護），
  第二節的因果推斷要撤回，改記成「時間相近但無法證明因果，不排除巧合」。
