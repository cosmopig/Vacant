# R210-HET 預先登錄：異質 agent 池能不能讓 ON 有東西可路由

寫於 2026-08-28 UTC 11:38，**在任何模型呼叫之前**。判準寫在量測之前，
量完不准改。

## 背景

`DECISION_20260828_R146S_ENDPOINT_VERDICT.md` 的終點裁決：等預算下
ON（82.42%）沒有贏 OFF5（83.57%），McNemar p=0.5572。該檔自列的
推翻條件 #2 是最值得先查的：

> `pool` 清單 6 個 agent 全部是同一個模型 `qwen/qwen3.6-35b-a3b`
> （差異只在 system prompt）⇒ 能力同質、只有指令風格異質。如果信譽
> 路由的價值來自路由到「能力更強」的 agent，而池子裡沒有能力差異可
> 路由，那麼「ON 沒贏」有可能是實驗設計的產物。

本輪要做的就是把那個「沒有東西可路由」的前提拿掉，重跑一次。

## 池子怎麼選——選擇規則寫在看到結果之前

**規則：用 8765 中轉當下服務的「全部」非 embedding 模型，不挑。**
理由：挑模型＝挑實驗條件，挑到讓 ON 好看的組合，結論一文不值
（人類 2026-08-24 明文警告）。「relay 上有什麼就用什麼」是一條不看
結果就能執行的規則。

`GET /v1/models`（2026-08-28 11:21 UTC）回四個：

```
qwen_qwen3.6-35b-a3b
qwen/qwen3.8-27b
gemma-4-12b-it-qat
text-embedding-nomic-embed-text-v1.5   ← embedding，不適用
```

三個候選都試了。**`gemma-4-12b-it-qat` 實測不可用**——runner 的模型池
預檢（零容忍）擋下來，直接 curl 拿到 body：

```
HTTP=400
"Failed to load model \"gemma-4-12b-it-qat\". Error: Model loading was
 stopped due to insufficient system resources. Under the current settings,
 this model requires approximately 44.87 GB of memory..."
```

這是**後端硬體限制**，不是我挑掉它的：relay 那台機器載不動。要用它得
改對面機器的 LM Studio guardrail 設定（不在本 loop 權限內，屬於「需要
人類」的那類）。**照實記：唯一一個真正不同家族的模型拿不到。**

⇒ 實際可用的異質池只剩兩個 model：
`qwen/qwen3.6-35b-a3b`（35B MoE，A3B active）與 `qwen/qwen3.8-27b`（27B）。
`--models` 是 round-robin 分配（`models[i % len(models)]`，決定性）：

| agent | model |
|---|---|
| careful-1 | qwen/qwen3.6-35b-a3b |
| careful-2 | qwen/qwen3.8-27b |
| plain-1 | qwen/qwen3.6-35b-a3b |
| plain-2 | qwen/qwen3.8-27b |
| hasty-1 | qwen/qwen3.6-35b-a3b |
| hasty-2 | qwen/qwen3.8-27b |

**這個池子帶進來的是「能力異質」，不是「家族異質」。** `_model_family()`
是 `model.split("/")[0]`，兩個都回 `"qwen"` ⇒ ON 的 `_diverse_reviewers`
與 `_independent_reviser` 看到的仍然是單一家族，行為跟同質池那次一樣。
**本輪不改 `_model_family`，也不改 POOL 以外的任何機制**——只換池子成分，
機制原封不動，否則「換了池子」與「換了機制」兩個變因會纏在一起。

## Gate H：前提檢查（先寫，後量）

異質性是這個實驗的**前提**，不是結論，所以要量不能假設。

- 量法一（獨立樣本）：`--calibration-n 12`，12 題與主實驗**不相交**
  （`offset=len(tasks)`），6 個 agent 各跑 ⇒ 每個 model 36 次嘗試。
  結果明文「never fed into routing」。
- 量法二（主樣本、檢定力較大）：**arm 順序刻意排成 `OFF,ON,OFF5`**，
  OFF 每題只 1 次呼叫、359 題約 1 小時就跑完，每個 agent 約 60 題
  ⇒ 每個 model 約 180 次。這是 Gate H 的**主要**依據。

**門檻（現在寫死）：**

- `|acc(qwen3.6-35b-a3b) − acc(qwen3.8-27b)| ≥ 10 個百分點`
  ⇒ 池子確實有能力差可路由，**讓 run 跑到終點**。
- `< 10 個百分點`
  ⇒ 前提不成立，**停掉這個 run**（不要跑完 2.5 天再說），照實寫
  「這個後端目前給不出能力異質的池子（gemma 載不動），推翻條件 #2
  在這個後端上量不了」，然後改做不需要異質性的方向。

10pp 的根據：OFF 臂每個 model 約 180 次嘗試，p≈0.8 時 95% CI 半寬約
±6pp，兩個獨立比例的差要穩定看得出來大約需要 10pp。低於這個數，
「路由到能力更強的 agent」這件事在池子裡根本沒有可觀察的對象。
（這是判斷，不是量測——它是用 CI 半寬推出來的門檻選擇。）

⚠ Gate H 的量法二用的是主實驗同一批題目，**不是獨立樣本**；它是前提
檢查不是結果，但報告時必須同時報量法一（12 題獨立）的數字。

## 主問題與終點規則（沿用 R146-S 的反 optional-stopping 紀律）

- 主問題：**能力異質池之下，等預算的 ON 打不打得贏 OFF5？**
  比較＝同一個 run 內 ON vs OFF5（條件一致、equal_budget=True），
  `analyze_paired.py` McNemar 精確雙尾，α=0.05。
- 次問題（免費附帶）：異質池的 OFF 失敗率還在不在 20–60% 窗口內
  （判準 1 在新條件下是否仍成立）。
- **終點＝ON 與 OFF5 兩臂各自處理完 359/359 題**（valid + infra_void）。
  在終點之前**不做裁決**，每輪只記進度。中途看到 p 值好看就收＝
  optional stopping，明文禁止。
- 唯一允許的中途動作是 Gate H（前提檢查）觸發的停止，而 Gate H 的
  門檻已經在上面寫死，不看主問題的 p 值。

## 實驗條件（與 R146-S 那次的異同，逐條列）

| 項目 | R146-S run | 本 run |
|---|---|---|
| 題庫 | MBPP+ 371（EvalPlus，sha 釘死） | 同左的前 359 題（seed 相同 ⇒ 題序相同） |
| seed | `g-smoke-20260820` | **相同** |
| n | 371 | 359（另 12 題給 calibration，兩者不相交） |
| 池子 | 6 agent／1 model（同質） | 6 agent／2 model（**這是唯一刻意改動的變因**） |
| request-timeout-s | 600 | 600 |
| review-timeout-s | 250 | 250 |
| audit-rate | 0.2（預設） | 0.2（預設） |
| K review | 3 | 3 |
| 機制程式碼 | — | **零改動** |

seed 與題序相同 ⇒ 本 run 的 359 題是上一個 run 371 題的前 359 題，
可以做跨 run 的題目配對比較（同質 ON vs 異質 ON），但那個比較**條件不
一致**（池子不同就是差異本身），只能當探索性觀察，不能當主結論。

## 什麼情況下這份預先登錄該被推翻

1. 若 Gate H 過了但兩個 qwen 其實在**不同題目上互補**（平均相近但覆蓋
   不同），那「平均能力差」就不是路由價值的正確操作化——本 run 答不了
   那個版本的問題，要另外設計。
2. 若 relay 之後載得動 gemma（或掛上別家族模型），這個「只有兩個 qwen」
   的池子就該被真正跨家族的池子取代重跑。
3. model 與 persona 沒有完全交叉（6 agent／2 model 下，qwen3.6 拿到
   careful-1/plain-1/hasty-1，qwen3.8 拿到 careful-2/plain-2/hasty-2）
   ——persona 編號與 model 綁死。若結果對 model 敏感，無法完全排除是
   persona 編號的效果。要拆開需要改 `--models` 的分配方式（本輪不改）。

---

## Gate T：吞吐量門檻（追加於 2026-08-28 UTC 11:34）

**寫作時點要照實說：** 這條是在 run 啟動之後、看到**預檢**延遲之後才補的，
但**在任何 arm 資料產生之前**（當下 `calls.jsonl` 只有 3 筆，全是 `preflight`，
零筆 `gen`）。它是對「跑不跑得完」的可行性設限，不碰主問題的判準。

觸發我補這條的觀察（`calls.jsonl` 前 3 筆，原始數字）：

```
qwen/qwen3.6-35b-a3b  attempt=1 ok=True   latency_ms=5174     （回 4 字）
qwen/qwen3.8-27b      attempt=1 ok=False  latency_ms=120088   TimeoutError
qwen/qwen3.8-27b      attempt=2 ok=True   latency_ms=73920    （回 2 字）
```

`qwen3.8-27b` 第一次直接吃滿 120s 預檢逾時、第二次 74s 才回兩個字。
對照 `qwen3.6-35b-a3b` 的 5.2s，這**可能**是冷載入一次性成本，也**可能**是
relay 那台機器同時放不下兩個模型、每次換 model 就要重載（gemma 需要
44.87GB 載不動，已證明它的記憶體是吃緊的）。若是後者，ON 臂每題會在
worker／3 個 reviewer／reviser 之間反覆換 model，換一次付一次重載。
**這是「哪一種」的問題，現在還不知道，要用 arm 資料判。**

**門檻（現在寫死）：** 等 OFF 臂累積 **≥30 筆 `role="gen"`** 之後：

- 以 OFF 臂的實際逐題節奏推算跑完 359 題所需時間。
  **若推算 > 12 小時**（即平均每題 > 120 秒；同質池的基準是每題約 10 秒）
  ⇒ 換 model 的成本已經吃掉可行性（ON+OFF5 的呼叫數約是 OFF 的 10 倍
  ⇒ 會變成 5 天以上），**停掉這個 run**，照實記「這個後端撐不住能力異質
  的池子」，並改用單一模型的方向。
- ≤ 12 小時 ⇒ 繼續，照 R146-S 紀律跑到終點。

同時要分 model 報 `latency_ms` 中位數（`calls.jsonl` 有逐筆 `latency_ms`
與 `model`），因為**延遲本身就是實驗條件**（SPEC_GAIN §7）：如果兩個
model 的延遲差一個數量級，ON 的路由就同時在路由「正確率」與「速度」，
那是另一個要單獨報的事實，不是可以混在一起的東西。

**Gate T 與 Gate H 互相獨立**：Gate T 只看跑不跑得完，Gate H 只看池子有沒有
能力差，兩者都不看主問題（ON vs OFF5）的 p 值。
