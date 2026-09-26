# 閘門 5：零設定 v3.3 的給人說明（L-fake，不花錢，2026-09-26）

Harbor＋pi 0.87.1＋回合上限 15、DABstep 第 5 題、假模型（`ops/intake/mock_model.py`）。v3.3 wheel：commit `a2b4b0ee`，
sha256 `5ed17c6c7c28d03d73960562ac2620c71b92ea514bc0c475409597efb9c44ae1`；v3＝正式批次 C2 用的凍結 wheel（`0dcd5d68…`）。

| 情境 | 組 | 評分 | 請求數 | 說明 |
|---|---|---|---|---|
| `scenario_capped.json`（一直查、第 13 回合後提醒、第 14 回合寫 NL、第 15 回合交答案） | v3 | 1 | 15 | 「Ended before the agent said it was done … /app/answer.txt: exists; its content was not checked.」 |
| 同上 | v3.3 | 1 | 15 | 「The agent said it was done on the last of the stated 15 model turns …」＋完整檢查＋**Budget reminders** 一節：`answer.txt: written at step 14, after the budget reminder sent after turn 13 … Vacant checked no value in it against the record.` |
| `scenario_final_on_cap.json`（第 12 回合寫檔、第 15 回合交答案，沒有提醒） | v3.3 | 1 | 15 | 和 v3.2 相同（閘門 4） |

- 提醒情境兩組的請求數相同（各 15），假模型都在第 14、15 回合的請求裡看到同一段提醒（`mock_capped.jsonl`：`fed_back` 4＝2×2）——
  **v3.3 只改給人的說明，模型收到的東西不變**。
- 各組資料夾：`pi.txt`、`vacant_check.json`、`delivery.{md,json}`、`chain.ndjson`。
- 同一段說明在正式批次 C2 的真實病歷上離線重跑過（複本；`../research_12b/scripts/replay_ended.py`）：第 1464 題（提醒之後寫了「Not Applicable」）
  的說明寫明「提醒之後寫的、沒有值被對照過」、第 2697 題（兩次提醒都沒寫）寫「兩次提醒之後什麼都沒寫、檔不存在」。
