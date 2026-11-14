# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（2026-11-14 人類改向；這條分支＝redo 線）
- **唯一的任務在 `ops/redo/MISSION.md`，每一輪先讀它。** 問題只有一個：原生 pi＋本機 gemma-4-12b，
  同樣 1800 秒，「工作區自己的測試沒過就開全新行程重來（最多 3 次）」是不是比「一次跑到底」交出更多通過的成果。
- 量具＝`ops/redo/redo.py`（已驗：selftest 26/26；真的 pi 0.87.1 對假模型端點跑通兩臂、端點死掉記成 infra_void）。
  **不要改它的判定邏輯。**
- 票＝`ops/redo/tickets/T01…T07`，照編號一次一張。**T01 done**（冒煙 2 對驗收成立，票尾在 `~/dev/ops/tickets/redo/done/`）；
  **T02 進行中**：篩選 16 題×1 次（S1），root `~/dev/ops/redo_runs/screen16`。13:33:46 原 runner 被外部中斷（與人類重啟迴圈同時），
  人類 13:38 重啟（第一次 PATH 缺 `pi` 卡住）；13:39:49 模型掉一次已恢復；現 8/16 對、在跑 pg_pig_latin A。runner 再死：照 MISSION §5 重啟，
  PATH 要含 `~/.local/bin`（`pi` 在那裡）。每輪最多一次 `status`；看到 16/16 的那輪做票步驟 4（report、複製結果、commit、票尾、移到 done）才完 T02。
- 尚無可引用數字：冒煙只是 S0 的 harness 驗收（UNRESOLVED 不是結果）；可引用的句子只有 **redo1** 計畫檔的 `prereg.states` 那幾句（smoke2／screen16 計畫沒有 `states` 欄位，兩批數字不可引用）。

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
- 2026-11-14 14:22（1719 輪）status：screen16_pi_gemma12b: INCOMPLETE  9/16 對  A=1/9  R3=4/9  b=0 c=3  infra_void 對=0；smoke2: UNRESOLVED 2/2 對（S0 驗收，數字不可引用）
