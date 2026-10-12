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
| 03:30 | **發射 `d37`**：`MAX_TURNS=15 launch_batch.sh d37 plan_d37.json 45 2026-10-02T06:29:54Z PREREG_20261002_COLAB_DABSTEP_V37`；VM 上 plan／cell.sh／dabstep_score.py 的 sha256 與凍結 commit `384fa838` 相同 |
| 03:31 | 本機常駐：`sync_from_colab.sh d37`（每 10 分鐘拉 chunk、驗 sha256，到 `~/Vacant_colab_raw/dabstep_v37_20261002/`）、`cu_guard.sh d37 45`（餘額 < 45 放停止檔）、`autostop_d37.sh`（DRIVER_DONE ⇒ 打包 → 下載 → sha256 → `colab stop`）、07:45 一律停機的保險。監看只看 rc、牆鐘、逾時、安裝，不看分數 |
| 03:30–05:42 | 711／711 格完成（05:42:13 DRIVER_DONE）；逾時 A 11、C37 3、C37R 14；安裝失敗 0；監看沒讀分數 |
| 05:52 | 本機同步 `SYNC_ALL_DONE`：14 個 chunk 全部拉回、sha256 逐個驗過 |
| 05:45–07:33 | ⚠ **GPU 空轉約 1 小時 52 分（約 16.6 CU）**：`autostop_d37.sh` 用 `vmrun.sh`（`colab console`）查 DRIVER_DONE，05:45 起 console 一直回空白 ⇒ 永遠看不到完成；同步走檔案介面早已完成，卻沒接到停機。等待通知的背景指令兩次到 2 小時上限被停，07:33 人工查才發現 |
| 07:33 | 改走 `colab download` 確認 DRIVER_DONE 與 progress.jsonl（711 行）；補下載發射紀錄、driver／feasibility log、代理帳本與摘要（代理全文在 chunk 裡）；**07:34 `colab stop`**；本機常駐全部停掉 |
| 07:35 | void 檢查（`analyze_dabstep.py --void-only`，不讀分數）：**0 格**；plan sha256 與凍結版相同 ⇒ 不補跑 |
| 07:36 | **第一次讀分數**，跑凍結的分析：C37 − A p＝0.0028（主要）、C37R − A p＝3.1e-5、C37R − C37 p＝0.011。結論：`decisions/conclusions/CONCLUSION_20261002_COLAB_DABSTEP_V37.md` |
| 07:45 | 事後拆解（描述）：A 有 42 格「說做完卻沒寫答案檔」、C37 0 格（`missing_output` 退回 38 格）；Vacant 把對的改成錯 0 次（唯一可疑的 C37R 61-s2 退回前的答案本來就錯）；和 09-26 本機批次比，有 Vacant 那組幾乎相同、差在 A 變差 |

**修法（下一批照做）**：收尾判斷只走檔案介面——`colab download /srv/eval/DRIVER_DONE` 成功、且同步回報 `SYNC_ALL_DONE` ⇒ 立刻 `colab stop`；console 只當備援。等待通知的背景指令有 2 小時上限，不能當成唯一的監測。
