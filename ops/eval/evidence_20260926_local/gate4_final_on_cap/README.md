# 閘門 4：最後一回合才交答案（零設定 v3.2，L-fake，不花錢，2026-09-26）

情境（`ops/eval/gate3/scenario_final_on_cap.json`）：Harbor＋pi 0.87.1＋回合上限 15、DABstep 第 5 題、假模型
（`ops/intake/mock_model.py`）照劇本：11 次查資料、第 12 回合寫 `/app/answer.txt`（NL）、再查 2 次、**第 15 回合交最終答案**（沒有工具呼叫）。
Harbor 的上限在自己的回合結束處理器裡中止，pi 因此不進交件前檢查——agent 說了做完，但 Vacant 的檢查沒跑到。

```
SCENARIO=ops/eval/gate3/scenario_final_on_cap.json GATE_NAME=gate4 \
ARMS="A=- v3=<凍結的 v3 wheel 0dcd5d68…> v32=<v3.2 wheel 0c953bc0…>" \
  ops/eval/gate3/run_gate3.sh <harbor> <jobs> <釘死的題目> - - 15
```

| 組 | 評分 | 請求數 | 交件說明的開頭 |
|---|---|---|---|
| A（沒裝） | 1 | 15 | — |
| v3（正式批次 C2 用的那一版） | 1 | 15 | 「Ended before the agent said it was done, after 15 of the stated 15 model turns; no delivery check ran.」——**錯的** |
| v3.2（commit `33634f62`，wheel sha256 `0c953bc0e9974c9e1dd66bb211815ba3c7578f43d4aae431c4c8764f9796e2a8`） | 1 | 15 | 「The agent said it was done on the last of the stated 15 model turns; … The check ran afterwards, for you only」＋完整的檢查結果 |

- 三跑共 45 通請求，假模型沒有收到任何 Vacant 的訊息（`mock.jsonl`：`fed_back` 全是 false）——補跑的檢查不送東西給模型。
- v3.2 的病歷（`v32/chain.ndjson`）最後一筆是 `ended`，`final_answer: true, checked: true`。
- 每一組的 `pi.txt`（pi 的事件流）、`vacant_check.json`、`delivery.{md,json}` 都在各自的資料夾。
