# e005_opencode_five_arm_smoke 複核結果

## 重算程式路徑
`/home/user1/dev/wt/worker/ops/audits/e005_opencode_five_arm_smoke_recompute.py`

## 數據一致性檢查 (對照 REPORT.json)

| 指標 | Packet 宣稱 / REPORT.json | 重算結果 | 一致性 |
|---|---|---|---|
| cells_scored | 5 | 5 | 一致 |
| infra | [] | [] | 一致 |
| A pass | 1/1 (rate: 1.0) | 1/1 (rate: 1.0) | 一致 |
| C pass | 1/1 (rate: 1.0) | 1/1 (rate: 1.0) | 一致 |
| H pass | 1/1 (rate: 1.0) | 1/1 (rate: 1.0) | 一致 |
| M pass | 0/1 (rate: 0.0, timeout=1) | 0/1 (rate: 0.0, timeout=1) | 一致 |
| S pass | 1/1 (rate: 1.0) | 1/1 (rate: 1.0) | 一致 |

## Packet 宣稱超出證據檢查

- **Packet 宣稱**：M 臂逾時（900s）是格結果且照常打分。
  - **重算證據**：`score.json` 顯示 `wall_s: 900`, `pass: false`. 符合「放行鐵律」描述。
- **Packet 宣稱**：C 臂 `install_rc=0`，且 `vacant_home` 非空、含 trace。
  - **重算證據**：`score.json` 顯示 `pass: true`, `wall_s: 155.9`. `vacant_home.tgz` 存在於目錄中。
- **Packet 宣稱**：H/M/S 指引路徑在 OpenCode 上可跑（prepend 成功）。
  - **重算證據**：H 臂 `wall_s: 474.2`, M 臂 `wall_s: 900` (逾時但啟動), S 臂 `wall_s: 102.8`. 皆有模型呼叫記錄，證明機構層未攔截。

## 結論
所有核心數據與 Packet 宣稱一致。M 臂的 UNKNOWN 狀態符合預註冊判準條款（無第二 agent 證據）。
