# 可究責追緝——2026-09-24 的證據（L-fake）

> **證據等級：L-fake。** 模型是照劇本回答的假上游（`ops/intake/mock_model.py`），沒有真模型、
> 沒有 API 金鑰。這裡證明的是**機制**在四個真 agent 的真掛鉤、真工具迴圈上接得起來，且歸因規則在
> 乾淨的埋錯下給出期望的答案。**不證明**真模型下產出會更接近需求——那是
> `decisions/prereg/PREREG_20260924_R536_LOCALIZED_FEEDBACK.md` 的事（草稿，待人類簽字）。

## 1. 四個真 agent × 四個埋錯情境（`e2e_trace_SUMMARY.md`、`e2e_trace_results.json`）

重跑：

    python ops/accountability/e2e_trace.py --bin <pi/opencode/codex 所在目錄> --out <dir>

| 量什麼 | 結果 |
|---|---|
| 歸因正確（狀態／類別／等級／指到的步驟／來源都對） | **16/16** |
| B（agent 憑空寫錯）⇒ `provable`，指到寫報告那一步；重跑前那個位置沒有這個值、之後不過且有 | 4/4 |
| A（輸入本來就錯）⇒ `input`／`lineage_exact`，來源＝`inputs/summary.txt`；agent 沒被記過錯 | 4/4 |
| C（腳本錯）⇒ `lineage_internal`，指到**寫腳本**的那一步（不是寫報告那一步） | 4/4 |
| D（agent 走了之後有人在外面改檔；負控制）⇒ `UNOBSERVED`／`gap`；沒有任何行動者被記 | 4/4 |
| 有位置的回饋出現在下一次模型請求裡 | Claude Code、Codex、pi：**是**（A／B／C 各 3 格）；OpenCode `run`：**否**（既有邊界：`run` 在第一個 idle 就結束） |
| 給 agent 的回饋裡有行動者識別 | 0/16 |
| 改好之後，病歷記「已解決」、收件 accept | Claude／Codex／pi 的 A／B／C：9/9 |
| 病歷簽章鏈驗得過 | 16/16 |
| 每次掛鉤的額外時間 p95 | 5.6–10.7 ms（小工作區；大專案沒量） |
| 行動者帳本 | 每個 agent 一格（4 跑）；B 記 1 筆可證明的錯；A 記在來源 `inputs/summary.txt`；D 記在該平台的整合覆蓋率 |

模型實際收到的回饋（Claude Code，情境 B，第 2 次請求）：

```
The task contract's checks do not pass yet (this is feedback from `vacant check`, not a final decision):
- total: FAIL — report.md:3 says "999"
  expected 69 (column 'amount', 3 rows)
  this value first appeared at step 2 (Bash)
Run `vacant check` to re-check before finishing.
```

## 2. R536 的管線冒煙（`r536_mock_smoke_*.json*`）

2 題 × 3 臂，Claude Code 對假模型：RS（重抽、無回饋）3 次都錯；RF、RL 第 2 次改對。
**只證明管線接得起來**（假模型看到回饋開頭就照劇本改對），任何效果數字都不能從這裡來。

## 3. 沒有做到的（照實寫）

- 子 agent 的端到端（假模型不演子 agent）：只有單元測試（`tests/test_trace_blame.py`）與
  `ops/accountability/capture/` 的可觀測面實測。
- 大型工作區的掛鉤時間：沒量。
- Claude Code 的掛鉤不帶模型 id ⇒ 信譽格的 substrate 是 `unknown`（逐字稿裡有自稱的模型，封存了，
  但沒拿來當鍵）。
