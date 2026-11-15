# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（2026-11-14 人類改向；這條分支＝redo 線）
- **唯一的任務在 `ops/redo/MISSION.md`，每一輪先讀它。** 問題只有一個：原生 pi＋本機 gemma-4-12b，
  同樣 1800 秒，「工作區自己的測試沒過就開全新行程重來（最多 3 次）」是不是比「一次跑到底」交出更多通過的成果。
- 量具＝`ops/redo/redo.py`（已驗：selftest 26/26；真的 pi 0.87.1 對假模型端點跑通兩臂、端點死掉記成 infra_void）。
  **不要改它的判定邏輯。**
- 票＝`ops/redo/tickets/T04…T07`，照編號一次一張。**T01／T02 done（GO）、T03 已發射在跑**（票尾在 `~/dev/ops/tickets/redo/done/`）：
  redo1（34 題×5 次＝170 對，root `~/dev/ops/redo_runs/redo1`）2026-11-14 17:23 發射（preflight PREFLIGHT_OK、計畫 f95f90d86b77 已 commit、runner PID 111807）。
  **下一輪起：每輪最多一次 `status`、貼進「進度」、結束**；runner 死就同一行重啟（PATH 含 `~/.local/bin`）、不因結果刪格；
  跑完（state ∈ {EFFECTIVE, UNRESOLVED, CONTRADICTS}）：查 `harness_changed_mid_run`=false → REPORT 複製進 `ops/redo/results/redo1_REPORT.{md,json}` 並 commit → 做 T04。
- screen16（S1）：EFFECTIVE 16/16 對 A=2/16 R3=9/16 b=0 c=7 p=0.015625、R3 驗收放行卻錯＝0 ⇒ **GO**（計畫檔 `prereg.go_rule`）。
  這 16 題是看過結果挑的（`prereg.role`：「篩選，不是證據」）：**這批數字只是 GO/NO-GO 閘門，不可當成效果引用**；結果在 `ops/redo/results/screen16_REPORT.{md,json}`。
- ⚠ 同批 8 次嘗試（A 2、R3 6）以 `Model reloaded.` 結束（100.86.226.21 伺服器端錯誤、會話被終止，12:02–16:15 分散），
  照預註冊規則計為嘗試（regex 不含 "reloaded"）、未改規則；「要不要歸 void」已照 MISSION §七記一行在 `ops/redo/IDEAS.md`（不做）；
  8 格中 6 格沒過、2 格後續嘗試通過。
  GO 判定對這 8 格不敏感（這 8 題 R3 全過；重跑只可能增大 c、b 恒 0）。端點 17:09 實測正常。詳見票尾。
  redo1 若再出現：報告會列出、照同規則處理；**不要改 infra 規則、不要因為結果刪格**。
- 尚無可引用數字：可引用的句子只有 **redo1** 計畫檔的 `prereg.states` 那幾句（smoke2／screen16 計畫沒有 `states` 欄位，兩批數字不可引用）。

## 這一輪怎麼做
1. 有長跑在跑：`python3 ops/redo/redo.py status --root <root>` 一次，把那一行貼在下面「進度」，結束這一輪。
2. 沒有長跑：做編號最小、前提已滿足的那張票。
3. 沒有票可做：結束這一輪。空輪比亂做好。

## 不准做（MISSION §四）
- 結案量具、複核腳本、替量具／簿記寫守門測試、只改簿記的輪次、重新驗收以前驗收過的東西。
- reqloop／G 系列／L008（凍結，不是這條分支的事）。freeze_check／ci_tip_check 的紅燈屬於那條線：不修、不追。
- 一批跑到一半改 `redo.py` 或計畫檔；因為結果刪格；讀題庫的 hidden／scorer。

## 紅線
- 凍結／受控解凍：repair.py 2795 行／blob 5147f8c3…、run_eval.py 1298 行／blob b6d2f37f…（仍凍結）；extract.py 1295 行／blob b502741b…、checks.py 2907 行／blob d401a8ae…（受控解凍、只加法、預設＝舊行為）；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。
- 不 push main；無 reset/rebase；.github/workflows/ 只讀；鐵律 1–6 照舊。
- 口徑：redo 的數字是 harness 裡的機制，不是「裝了 Vacant」的數字；可以說的句子只有計畫檔 `prereg.states` 那幾句。

## 進度（每輪覆寫這一段，一行）
- 2026-11-15 09:01（1780 輪）status：redo1 `INCOMPLETE 44/170 對 A=26/44 R3=29/44 b=3 c=6 infra_void 對=1`（還在跑，runner PID 111807 alive；08:43 的 43/170 之後 18 分新增 1 對）；screen16 `EFFECTIVE 16/16`（GO 閘門，不可引用）；smoke2 `UNRESOLVED 2/2`（不可引用）；下一輪照舊只做 status
