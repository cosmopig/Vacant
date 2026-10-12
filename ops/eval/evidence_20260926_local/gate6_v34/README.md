# 閘門 6：零設定 v3.4（L-fake，不花錢，2026-09-26）

v3.4 wheel：commit `1685e664`，sha256 `81a761deefd72bfc1be192a38fd0a2f9582736a1b089b65f28211c65f69b595b`。Harbor＋pi 0.87.1＋回合上限 15、DABstep 第 5 題、假模型。

| 情境 | 評分 | 請求數 | 病歷最後幾筆 | 說明 |
|---|---|---|---|---|
| `capped/`（`scenario_capped.json`：第 13 回合後提醒、第 14 回合寫 NL、第 15 回合交答案） | 1 | 15 | `nudge, step, session_closed, ended` | 「在最後一回合說了做完 … 事後查的」＋ Budget reminders：`answer.txt: written at step 14 … Vacant checked no value in it` |
| `final/`（`scenario_final_on_cap.json`：第 12 回合寫檔、第 15 回合交答案） | 1 | 15 | `step, step, session_closed, ended` | 「在最後一回合說了做完 … 事後查的」 |

- 工作階段的結束（`session_closed`）記在事後檢查之前（v3.4 的順序）。
- 模擬使用者（乾淨 Ubuntu、只照 README 裝、pi 沒有上限）：`../simuser_v34/`——三個情境結果和 v3 相同；`correct` 的 4 通請求 A／C **逐位元組相同**，
  而且和 v3 那一輪的 4 通也逐位元組相同（`correct_bodies_sha256.txt`）。
