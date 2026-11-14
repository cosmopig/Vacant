# T01 — 發射前檢查＋冒煙 2 對（S0）

**前提**：無。**規模**：0 行產品碼；約 4–10 通 pi 執行。**讀**：`ops/redo/MISSION.md`。

## 步驟
1. `python3 ops/redo/redo.py selftest` → 最後一行必須是 `VERDICT: REDO_SELFTEST_OK（26/26）`。
2. `python3 ops/redo/redo.py preflight --plan ops/redo/plans/smoke2_pi_gemma12b.json`
   - `FAIL 找不到題庫`：找到本機 polyglot_py 題庫（每題一個目錄，裡面有 `workspace/`；
     過去在 `~/dev/ops/ref/bm_tasks/polyglot_py`），之後每個指令加 `--bank <路徑>`。**不要改計畫檔的題目清單。**
   - `FAIL provider … 不在 models.json`：看 `~/.pi/agent/models.json` 裡 gemma-4-12b-it-qat 的 provider 叫什麼，
     把**三份**計畫檔（`smoke2_…`、`screen16_…`、`redo1_…`）的 `providers[0].provider` 改成同一個名字，commit。
     要用第二台機器就在這時候加第二個 provider（含 `jobs`）；可以加 `health_url`
     （那台的 `http://<ip>:1234/v1/models`）與 `health_contains`（模型名）。三份計畫的這一段必須相同
     （`tests/test_redo_harness.py` 會擋）。
   - `FAIL 負控制失敗`：停，回報人類（題庫的起點就會通過測試，這個題庫不能用）。
3. preflight 是 `PREFLIGHT_OK` 之後發射冒煙（約 20–60 分鐘，跑在這一輪之外）：
   ```bash
   ROOT=~/dev/ops/redo_runs/smoke2; mkdir -p "$ROOT"
   setsid nohup python3 ops/redo/redo.py run --plan ops/redo/plans/smoke2_pi_gemma12b.json --root "$ROOT" >> "$ROOT/nohup.log" 2>&1 < /dev/null &
   ```
4. 跑完後 `python3 ops/redo/redo.py report --root ~/dev/ops/redo_runs/smoke2`。

## 驗收（全部要成立）
- 2 對都完成、`infra_void 對=0`。
- 每一格 `attempts[*].usage.calls` ≥ 1（pi 真的有呼叫模型）。看 `$ROOT/cells/*/r1/*/cell.json`。
- 報告裡沒有「⚠ 有嘗試以模型錯誤結束」那一行；有的話把原文貼在票尾，**不要自己改 infra 規則**。

## 禁止
- 不看、不引用這 2 對過不過。
- 不改 `ops/redo/redo.py`。selftest 沒過＝環境問題（python 版本等），回報，不要改到它過。

## 票尾（做完填這三行，再把票移到 done）
- commit：
- 驗收指令的實際輸出（逐字貼最後一行）：
- 沒做完的：
