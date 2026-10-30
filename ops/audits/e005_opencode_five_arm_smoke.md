# e005_opencode_five_arm_smoke 複核結果

## 重算與評分對照

| 臂 | n | 通過 | 率 | 呼叫/成功 | token/成功 | 逾時 | REPORT.json 對照 |
|---|---|---|---|---|---|---|---|
| A | 1 | 1 | 1.0 | 0.0 | 0 | 0 | 一致 |
| C | 1 | 1 | 1.0 | 0.0 | 0 | 0 | 一致 |
| H | 1 | 1 | 1.0 | 0.0 | 0 | 0 | 一致 |
| M | 1 | 0 | 0.0 | None | None | 1 | 一致 |
| S | 1 | 1 | 1.0 | 0.0 | 0 | 0 | 一致 |

- **infra（不進分母）**：0 格；重新評分不一致：0 格。
- **重算程式路徑**：`~/dev/wt/worker/ops/audits/e005_opencode_five_arm_smoke_recompute.py`

## Packet 宣稱與數據對照

Packet (`/home/user1/dev/wt/worker/ops/vlab/packets/e005_opencode_five_arm_smoke.md`) 宣稱：
- **H/M/S 指引路徑**：`VLAB_APPEND_SYSTEM` → `/srv/vlab/arms/e002_{H,M,S}.md`（cell.py prepend 模式）。
  - *核對*：H 臂 `append_system: {"mode": "prepend"}`，M 臂同。一致。
- **C 臂掛載**：`install_rc=0`，且該格 `vacant_home.tgz` 存在、非空、含 `.vacant/intake/hooks/events.jsonl`。
  - *核對*：C 臂 `install_rc: 0`，`vacant_home.tgz` 為 79,333 B。一致。
- **M 臂第二 agent 證據**：M 格 `events.jsonl`/stderr 有啟動第二 agent 的證據（shell `opencode run`／`pi -p` 或 subagent 工具呼叫）。
  - *核對*：M 臂 `agent_rc: 124` (900s 逾時)，且 events/stderr 無明顯的第二 agent 啟動證據。Packet 標註此為 UNKNOWN，與數據一致。
- **A 臂純對照**：該格 HOME 不產生 `~/.vacant` 資料（無掛載）。
  - *核對*：A 臂無 `vacant_home.tgz`。一致。

## 結論
所有數值與 Packet 宣稱的邏輯均一致。
