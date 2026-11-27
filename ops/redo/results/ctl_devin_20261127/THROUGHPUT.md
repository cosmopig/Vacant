# 吞吐量（Devin swe-2-flash-medium，經 `devin_sandbox_agent.py`，2026-11-27；`ops/redo/probe_throughput_devin.py`）
每個並行度 c 跑 2c 次真實嘗試（8 個不同題輪流、不評分）。**限流是帳號層級、時間窗式的**（錯誤文字：`Reached request rate limit. … Your limit will reset in N seconds`），
Devin CLI 遇到就直接以 `Error: Agent error: …` 結束（不自己重試）。

乾淨（0 錯誤）的測量，限流窗已重置之後（`throughput.jsonl`，探針錯誤偵測＝匯出沒有 final_metrics 或輸出含 `Error:`）：
| 並行度 | 嘗試 | 牆鐘 s | 完成／分 | 單次牆鐘中位數 s | 錯誤 |
|---|---|---|---|---|---|
| 4 | 8 | 248.5 | 1.93 | 45.4 | 0 |
| 8 | 16 | 342.9 | 2.80 | 39.6 | 0 |
| 12 | 24 | 64.5 | 22.33（不可用：17 個是限流後秒結束） | 31.8 | **17** |
| 16 | 32 | 212.1 | 9.05（不可用） | 27.9 | **25** |

**選 jobs＝8**：4→8 吞吐還在升（1.93→2.80；較早一次 8 是 3.65）、無限流；12 起就限流。
單次牆鐘中位數 40–45 秒（實際任務很小，單獨跑一次 16 秒）⇒ 服務端有排隊／節流，不是本機 CPU（容器 4 CPU 沒吃滿）。
**作廢保留（照實）**：
- `throughput_v1_c32_suspect.jsonl`：c=4/8/16 乾淨（探針當時的錯誤判準較弱：只看有沒有匯出；c=16 的 32 次都有完整 final_metrics，所以結論可用——16 在窗內未限流），
  c=32 的 64 次探針判成功但其實 32 次沒有 final_metrics；之後直接重現 32 並行＝全部 `rate limit`。
- `throughput_v2_c32_ratelimited.jsonl`、`throughput_v3_c20_c24_ratelimited.jsonl`、`throughput_v4_c12_c16_still_limited.jsonl`：限流中或限流窗尚未重置時測的，不能當吞吐。
**不確定性**：限流是滾動窗；c=16 在 v1 沒限流、在 v5 限流，差別在**之前累積的請求量**（v1 是第一次）。所以 8 是「連續跑也不限流」的保守選擇，不是量到的上限；
真正的上限（每分鐘請求數）沒量，也沒在文件裡找到。校準時任何限流錯誤都走 infra_void 重試規則（最多 4 次），並在報告列出次數。
