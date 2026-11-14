# T04 — 寫結論（照 state，逐字用計畫檔的句子）

**前提**：T03 done。**規模**：一個檔，≤ 80 行。0 次模型呼叫。

## 步驟
寫 `decisions/conclusions/CONCLUSION_<日期>_REDO1.md`，內容只有：
1. `REPORT.md` 全文（原樣貼）。
2. 這個 state 可以說的那一句：從 `ops/redo/plans/redo1_pi_gemma12b_polyglot34.json` 的 `prereg.states.<state>` **逐字**抄。
3. `prereg.known_limits` 四條（逐字）。
4. 多做了幾次模型呼叫：兩臂的 `mean_model_calls`、`mean_attempts`、`mean_agent_wall_s`（從 `per_arm` 抄）。
5. infra_void 的對與處理紀錄（從 T03 票尾抄）。

然後：
- EFFECTIVE ⇒ 開 T05、T06（T07 排後面）。
- UNRESOLVED／CONTRADICTS ⇒ 回報人類，這條線停。**不開新實驗。**

## 驗收
- `python3 ops/check_repo_links.py | grep REDO1` 沒有輸出（新結論檔沒有死連結；這支檢查在這條分支上本來就有
  與 redo 無關的既有紅項，**不要去修它們**）。
- 結論檔裡每一個數字都在 `ops/redo/results/redo1_REPORT.json` 找得到。

## 禁止
- 不寫計畫檔沒有的更強說法；不把這個數字寫進 README／CLAUDE.md（那要等 T05 的產品量測＋人類看過）。

## 票尾（做完填這三行，再把票移到 done）
- commit：
- 驗收指令的實際輸出（逐字貼最後一行）：
- 沒做完的：
