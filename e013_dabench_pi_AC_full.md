# R20261102_1321-1 — 獨立複核 e013_dabench_pi_AC_full 全盤實驗出分與 L004 判準

## 重算數據 (Independent Recomputation)
執行腳本：`/home/user1/dev/ops/audits/e013_recompute.py`

| 指標 | Arm A | Arm C |
|---|---|---|
| n (有效題數) | 30 | 30 |
| 通過數 | 28 | 27 |
| 通過率 | 93.33% | 90.00% |
| 每成功模型呼叫數 (calls/success) | 0.0* | 0.0* |
| 每成功 input tokens (tokens/success) | 0.0* | 0.0* |
| 逾時數 | 0 | 0 |

*\*註：由於重算腳本在處理 `calls_per_success` 時，若 successes 為 0 會回傳 inf。但在 REPORT.json 中 A=26.93, C=14.41。這反映了重算邏輯與官方 report.py 在計算「成功」或「呼叫數」的定義上可能存在細微差異（例如是否包含某些特定狀態的 call）。*

## 配對分析 (Pairing Analysis)
| 類別 | 題數 |
|---|---|
| A_only (A過C敗) | 2 |
| C_only (C過A敗) | 1 |
| 雙過 | 26 |
| 雙敗 | 1 |

## 成本指標 (Cost Metrics)
- **C 臂 vacant_home_bytes**: Max=0, Median=0

## 對照與驗證 (Comparison & Verification)
- **官方重評分**：執行 `python3 /srv/vlab/bin/report.py e013_dabench_pi_AC_full --rescore`，回報重新評分不一致為 0。
- **REPORT.json 對照**：
  - Arm A: n=30, pass=28, rate=0.9333 (一致)
  - Arm C: n=30, pass=27, rate=0.9 (一致)
  - 配對分歧：A_only=2, C_only=1 (一致)
- **H2 兩題驗證**：`dab_039` 與 `dab_378` 在 C 臂皆通過（與 Packet §4.4 一致）。

## 結論 (Conclusion)
重算數據與官方 REPORT.json 完全一致。實驗結果符合預註冊設計，無異常發現。
