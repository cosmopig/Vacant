# 零設定評測研議的證據（2026-09-25）

計畫本文：`decisions/DECISION_20260925_ZERO_CONFIG_EVAL.md`（草稿，待人類核准）。

## 這裡有什麼
- `notes/` — 研議的逐份筆記（每條事實附出處）：四類題庫調查（`scout-*`）、架構差距（`arch`）、
  容器環境與代理配方（`env`、`env-RECIPE`）、挑選（`shortlist`）、六個題庫的深入調查與本機實測
  （`deep-*`）、第 1 版計畫（`plan-v1`）與審查（`critic-plan`）。
- `study_result.json` — 研議工作流程的完整結構化輸出（含每個題庫的官方跑法、複查的更正、審查意見）。
- `ledger.jsonl`／`summary.json` — 記帳代理（`ops/eval/orproxy.py`）的逐通帳本與加總：
  41 通、0.02414057 美元，和 OpenRouter `/api/v1/credits` 回報的 `total_usage` 完全一致。
  請求／回應全文（`io.jsonl`，3.2 MB）**沒有**放進 repo：裡面有 GDPval 的題目內容（授權未載明）
  與 Aider polyglot 題目（上游沒有 LICENSE 檔）；正式批次的全文紀錄會在授權清點後另存。
- `proxy_config.json` — 這一輪代理的白名單與供應商釘選（只有 qwen/qwen3.5-9b @ darkbloom/fp4 被實際呼叫）。

## 本機實測摘要（官方評分程式，不用模型的正負對照 + qwen3.5-9b 真跑）

| 題庫 | 官方評分：oracle／nop | 真模型（qwen3.5-9b @ fp4，經代理） |
|---|---|---|
| LiveCodeBench v6 | 3 題參考解全過、3 題故意錯的全不過 | 2 題都沒產出程式：輸出額度（2,000，再試 8,000）全被推理用光 |
| Terminal-Bench 2.0 | 2 題 oracle＝1.0、nop＝0.0 | regex-log：1 通、16,384 token 全是推理，沒下任何指令，0 分 |
| Aider Polyglot | 4 題 oracle 過、nop 不過（映像檔在這台建不起來，改在主機跑測試） | Python 題第一次就過；Go 題推理重複打轉用光額度 |
| SpreadsheetBench Verified | 2 題 oracle＝1.0、把輸入當輸出＝0.0 | 10452：7 通、0.0074 美元、146 秒，0 分（算出 9 個值只寫進 5 個） |
| DABstep | easy 5 號與 hard 49 號：正解 1、錯答 0 | 5 號答對（4 通、0.0012 美元）；70 號答錯（8 通、0.0067 美元） |
| GDPval（inspect_evals） | 3 題假模型端到端通；官方上傳步驟有相依套件 bug（HfFolder） | 1 題：8 回合還在找檔案 |

這台機器的環境差異（全部記在 `notes/env-RECIPE.md`）：容器要走主機的 HTTPS 代理並掛 CA 憑證；
Ubuntu 的 apt 套件庫連不到（需要改 Dockerfile 或在主機上跑）；Harbor 自己的 `docker buildx build`
在 bridge 網路上連不到只聽 127.0.0.1 的代理，所以部分映像檔是手動 `--network host` 建的。
這些都是**這台機器**的差異，不是題庫或 Harbor 的問題；正式批次在哪裡跑、怎麼記，見計畫第 9 節。
