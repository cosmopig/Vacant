# DECISION 2026-09-01（round456）：ON vs OFF5 等預算配對目前是 noise，擴大 n 找檢定力

## 一、量到什麼

`g_off5_qwen_only_20260901` 本輪跑完（60/60），三臂（OFF／ON／OFF5，同
qwen-only 六人格池、同 seed `g-r212-route-20260828`）第一次都是完整資料，
用 `ops/gain/analyze_paired.py` 做正式（非初步）配對：

```
OFF  vs ON    n=39  OFF 82.05% vs ON 89.74%   discordant 0:3  p=0.2500
ON   vs OFF5  n=35  ON  91.43% vs OFF5 85.71% discordant 2:0  p=0.5000  equal_budget=True（175 calls 兩邊相同）
OFF  vs OFF5  n=52  OFF 82.69% vs OFF5 84.62% discordant 1:2  p=1.0000
```

`ops/gain/power_paired.py --a-run runs/g_on_qwen_only_20260901 --a-arm ON
--b-run runs/g_off5_qwen_only_20260901 --b-arm OFF5 --n-cap 60 --bench-size 378`
判定：**noise**。discordant rate 5.71%（2/35），n=60 時期望 discordant≈3，
任何裂法都到不了 p<0.05；若真實效果＝目前觀測值，80% power 需要 4 個
discordant pair，換算約需 **70 個配對任務**（題庫 378 題，可達）。

## 二、為什麼配對數（n_paired）只有 35，不是 60

ON 的 infra_void 率 35%（21/60）遠高於 OFF5 的 8.3%（5/60），
`analyze_paired.py` 的分母是兩臂都有量到的交集，被 ON 的高 void 率壓縮。
拆 `calls.jsonl` 按 role：

```
role     n    err    err_rate   latency p50   latency max
gen      70   11     15.7%      38.6s         151.7s
review   180  52     28.9%      37.5s         60.1s   ← 剛好卡在 review_timeout_s=60 的天花板
revise   40   1      2.5%       43.0s         98.9s
```

review 呼叫的 max latency 精確卡在 60.1s（`review_timeout_s=60` 的邊界），
err_rate 遠高於 gen——這**不是新 bug**，是 round23
`DECISION_20260824_SERIALIZE_CONCURRENT_CALLS.md` 就記錄過的已知取捨：
review 用比 gen 短的 deadline（60s×2）換取單題最壞情況封頂，代價是後端
壅塞時 review 會比 gen 更容易撞牆變 infra_void。當時（round23）void 率
33-57%；本輪 35%，落在同一個歷史區間內，不是惡化，是這個設計固有的
成本在目前後端壅塞程度下的正常表現。

## 三、決定：延伸一批新 seed 的 ON／OFF5 去補檢定力，不改任何機制或門檻

- **選了什麼**：用新 seed `g-r454-scale2-20260901`（沿用上一輪誤標的
  round454 字樣，純粹是命名先後問題，不影響任何邏輯）啟動
  `runs/g_on_qwen_only_scale2_20260901`（ON, n=60），跑完後下一輪接著用
  同一 seed 跑 OFF5 對照臂，比照 round447 訂下的 OFF→ON→OFF5 序列。
- **放棄了什麼**：
  - 沒有調寬 `review_timeout_s`——那是 round23 的既定取捨，round456
    不重新評估這個決定（改它會改變實驗條件，且證據不支持「壞掉了」，
    只支持「本來就有這個代價」）。
  - 沒有用同一個 seed 加大 `--n` 重跑（`load_tasks` 用同一個 shuffle
    的前綴，`--n 120` 的前 60 題會跟現有已完成的 60 題重複，白白重算
    5-6 小時）——換 seed 抽新的一批不重疊（或重疊不多）的題目更省。
- **根據什麼**：`power_paired.py` 直接算出「noise」＋需要約 70 個配對
  任務，這是量出來的數字，不是猜測。
- **什麼條件下該被推翻**：如果下一批（scale2）的 ON void 率遠高於
  35%（例如後端進一步惡化到 round23 的 57% 那一端），累積到 70 個配對
  任務所需的總跑量會遠超預期，屆時要重新評估是否值得繼續加碼，或改用
  「多批獨立配對結果做 CMH 式合併」而不是硬湊單一大 n。

## 四、合併方法（留給下一輪，先寫死原則）

新 seed 這批（scale2）跟舊 seed（`g-r212-route-20260828`）的題目集合可能
有重疊，但 agent 路由／rng 不同（種子不同），視為獨立的配對批次。合併
時**不要**把兩批的 rows.jsonl 直接串接丟給 `analyze_paired.py`（它假設
單一 run 目錄、單一 task_id 命名空間，兩批的 task_id 若有重疊會互相覆蓋）
——正確做法是分別跑兩次配對分析，再用 CMH（Cochran-Mantel-Haenszel）
或直接加總兩批各自的 discordant b/c 做合併 McNemar，`ops/gain/` 目前沒有
這支工具，下一輪如果 scale2 兩臂都跑完需要新寫一支小腳本，不要手動口算。
