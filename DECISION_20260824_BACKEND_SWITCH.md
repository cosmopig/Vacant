# DECISION 2026-08-24：後端從 Cline 換到本地 LM Studio

**寫在跑之前。** 這是實驗條件的改變，不是實作細節——照
`SPRINT_PROMPT.md` 的規矩，每一次改條件都要記下來並說明為什麼。

## 一、為什麼一定要換

`runs/g_off60_20260824` 那一輪 60 題**全部** infra_void，calls.jsonl 裡
60/60 是 `HTTPError: HTTP Error 403`。直接打端點驗證，回的是：

```
{"error":{"code":"ENTITLEMENT_ERROR",
          "message":"Error 403: the user is not subscribed to required model plan"}}
```

不是金鑰過期，是**訂閱沒了**（人類 2026-08-23 已說明額度用盡）。
再跑幾輪只會拿到更多 60/60 infra_void。

## 二、換成什麼

| | 原本 | 現在 |
|---|---|---|
| 端點 | `api.cline.bot` | `http://100.119.113.56:1234/v1/chat/completions`（win1003 的 LM Studio） |
| 模型家族 | glm-5.2／deepseek-v4-flash／kimi-k3（3 個） | qwen3.6-35b-a3b（**1 個**） |
| 每次呼叫成本 | 約 $0.0065 | $0 |
| 每題耗時 | 約 13s | 約 82s |

實測（`runs/g_local_smoke_20260824`，3 題 OFF）：量具兩個方向 3/3、
infra_void 0、`run_complete: true`、成本 $0。**路徑是通的。**

## 三、單一模型家族——放棄了什麼，換到了什麼

先試過兩個家族（qwen ＋ nemotron-3-nano-omni）。實測每題 120s，而且
**nano 那個反而更慢（195s vs 82s）**——那不是模型大小，是 LM Studio 在
兩個模型之間換載。GPU 24GB 只剩約 5GB（VMware 也在用），塞不下兩個。

所以本輪用單一家族。**代價要講清楚**：

- SPEC_GAIN §5.1 的共同盲區問題在 ON 臂會更嚴重——同一個模型評審自己家族的
  產出，Kim 2025 量到兩個模型都答錯時 60% 錯在同一個答案。
- 池子的異質性只剩 system prompt，沒有模型家族的差異。

**但這兩點對 OFF 臂都不成立**：OFF 沒有評審，也不做信譽路由。
所以「量 OFF 失敗率」這件事用單一家族是乾淨的，而且快 2.4 倍。
**家族數的決定留到要跑 ON 的時候再做，不在這裡預先決定。**

## 四、這不影響 SPEC_GAIN §6 的平台無關宣稱——反而是它需要的

§6 說宣稱平台無關要「兩個不同的後端各跑一次，結論同號」。
Cline 是第一個後端，本地 LM Studio 是第二個。**現在還不能宣稱任何東西**，
因為兩邊都還沒有完整的三臂結果；但端點身分已經逐呼叫落盤（`api` 欄位），
兩個後端的數字不會混在一起。

## 五、判準沿用不改

`DECISION_20260824_OFF_BASELINE.md` 第三節那張 f 判決表**原樣沿用**，
一個字不動。換後端不是改判準——判準是在看到任何數字之前訂的，
現在也還沒看到數字。
