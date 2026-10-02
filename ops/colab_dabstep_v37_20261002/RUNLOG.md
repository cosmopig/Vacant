# DABstep 77 題 × 零設定 v3.7（Colab G4，2026-10-02）— RUNLOG

預註冊：`decisions/prereg/PREREG_20261002_COLAB_DABSTEP_V37.md`。時間一律 UTC。做法照 skill `colab-vacant-campaign`。沒有讀 `u274/raw/`。

| 時間 | 事件 |
|---|---|
| 02:40 | 人類：「測完整的3.7直接在環境內做pi + install vacant這樣的模擬；找一個題組真的完整跑過，題組必須是在過去有效的；同時做一份簡報」 |
| 02:45 | 選題組：DABstep 正式 77 題（15 回合）——「pi＋使用者安裝」下過去唯一量到顯著差別的題組（v3，p＝0.021）。效果來自 v3.6 起預設關的回合預算提醒 ⇒ 三組 A／C37／C37R |
| 02:50 | 帳號狀態：沒有運作中的 VM、餘額 91.43 CU。i1001 第三台 VM（00:57 發射）此時已不在，原因未確認（不是這個工作階段關的） |
| 03:00 | 題目：69 題 `harbor-datasets@e25eec6e`、10 題 Harbor adapter `--split dev`（`harbor@6cb9ff31`）重新產生；**79 題 `tests/` tree sha256 全部等於 FORMAL_MANIFEST**；7 個資料檔 sha256 全部等於 pin |
| 03:05 | `cell.sh` 加兩件事（其餘逐字同 C5）：Harbor `max-turns.ts` 逐字（`MAX_TURNS`）、C37R 的 `vacant install --budget-reminder`；新增 `stage_dabstep.py`、`dabstep_score.py`（題目 test.sh 逐字跑）、`analyze_dabstep.py` |
| 03:20 | `colab new -s d37 --gpu G4`；本機掛 07:45 一律 `colab stop` 的保險 |
| 03:25 | VM：vLLM 安裝與部署在背景；kernel 保活（`keepalive.py`，在 kernel 裡每 60 秒一點 CPU）——i1001 兩次被收回都在 kernel 閒置約 25–30 分鐘後 |
| 03:26 | 部署：wheel sha256 `92ddc44d…`（**與冒煙那次相同**）、114／114 檔；7 個資料檔放進 79 題、逐題核 sha256（`fill_dabdata.sh`）；python3 3.13.16、pandas 2.2.3；Linux 上產生的 `max-turns.ts` 第 2 行 `const maxTurns = 15;` |
| 03:27 | 計分器量具第一次：正解 0／79 過——**量具自己的錯**（`test.sh` 讀 `/app/answer.txt`，量具把答案放在暫存目錄）。`dabstep_score.py` 改成也把 `/app/answer.txt` 換成 `<app>/answer.txt`（格子裡 `<app>` 就是 `/app`，行為不變）。重量：**正解 79／79 過、不交 79／79 不過** |
| 03:28 | 冒煙（題 1 × A／C37／C37R，`MAX_TURNS=15`，不看分數、不進分析）：三組的每一通模型請求都帶「hard budget of 15 model turns」（15／7／6 通）；A 剛好 15 通後被 `ctx.abort()` 中止；C37、C37R 裝上、走到交件前檢查；C37R 的 install.json `budget_reminder: true`、C37 沒有這個欄位 |
| 03:35 | **預註冊凍結**（本 commit）：工具、計畫（`plan_d37.json`：79 題×3 組×最多 3 次、種子 20261002） |
