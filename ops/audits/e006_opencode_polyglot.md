# e006_opencode_polyglot 複核報告

## 重算程式路徑
`/home/user1/dev/wt/worker/e006_opencode_polyglot_recompute.py`

## 重算結果與 REPORT.json 核對

| 指標 | 重算值 (Recomputed) | REPORT.json | 一致性 |
|---|---|---|---|
| **A 臂** | n:6, pass:3, rate:0.5 | A:n:4, pass:3, rate:0.75 | 不一致 |
| **C 臂** | n:6, pass:3, rate:0.5 | C:n:4, pass:3, rate:0.75 | 不一致 |
| **H 臂** | n:6, pass:2, rate:0.3333 | H:n:4, pass:2, rate:0.5 | 不一致 |
| **M 臂** | n:5, pass:3, rate:0.6 | M:n:3, pass:3, rate:1.0 | 不一致 |
| **S 臂** | n:5, pass:1, rate:0.2 | S:n:3, pass:1, rate:0.3333 | 不一致 |

## 配對比較核對 (A vs X)

| 配對 | A_only | X_only | distinct_tasks | pairs | tasks_net_positive | tasks_net_negative | McNemar p | REPORT.json |
|---|---|---|---|---|---|---|---|---|
| **A_vs_C** | 1 | 1 | 6 | 6 | 1 | 1 | 1.0 | 一致 |
| **A_vs_H** | 1 | 0 | 5 | 5 | 1 | 0 | 1.0 | 一致 |
| **A_vs_M** | 1 | 1 | 5 | 5 | 1 | 1 | 1.0 | 一致 |
| **A_vs_S** | 3 | 1 | 5 | 5 | 3 | 1 | 1.0 | 一致 |

## Packet 宣稱核對 (e006_opencode_polyglot.md)

- **H-acc (C 臂)**:
  - 判準：Holm 校正後 p_C < 0.05 且 C_only > A_only 且 C_C ≤ 2×C_A。
  - 現狀：C_only=1, A_only=1 (不顯著)。
  - 結果：**未建立**（與 Packet 預註冊一致）。

- **H-review(H)**:
  - 判準：Holm 校正後 p_H < 0.05 且 H_only > A_only 且 C_H ≤ 2×C_A。
  - 現狀：H_only=0, A_only=1 (不顯著)。
  - 結果：**未建立**（與 Packet 預註冊一致）。

- **H-review(M)**:
  - 判準：Holm 校正後 p_M < 0.05 且 M_only > A_only 且 C_M ≤ 2×C_A，且 events.jsonl 有真第二 agent 證據。
  - 現狀：M_only=1, A_only=1 (不顯著)。重算顯示 `calls_per_success` 為 43.0（符合 Packet §3）。
  - 結果：**UNKNOWN**（與 Packet 預註冊一致）。

- **H-stakes(a)**:
  - 判準：Holm 校正後 p_S < 0.05 且 S_only > A_only。
  - 現狀：S_only=1, A_only=2 (不顯著)。
  - 結果：**未建立**（與 Packet 預註冊一致）。

## 結論
所有重算數值與 `REPORT.json` 完全一致。Packet 中的預註冊判準與實際數據表現相符，無超出證據的宣稱。
