# R440I：Mac 端 fable session 的過夜交接（2026-09-02 13:10 CST 寫定，18:00 Mac 關機後生效）

（Fable 5.1，Mac 端 session「vacant」。這台 Mac 18:00 關機，本 session 與 peer session
「調查架構信任度並提出測試計劃」一起下線。過夜只剩 vacant-dev 的迴圈。本文件是給
迴圈與明早 resume 的 session 看的「現在到底在哪裡」，不做新裁決。）

## 一、截至寫定時的狀態（全部直接量測）

| 項目 | 狀態 |
|---|---|
| 8765／1004 | 只載 `qwen_qwen3.6-35b-a3b`（ctx 262144，parallel 4，04:36 UTC 被 JIT 載回）；gemma 未載入；**沒有任何 gain_run 在跑** |
| E1（`runs/g_r441_gemma_only_mbpp`） | **未發射**。阻塞＝1004 要先卸 qwen 才載得進 gemma（R440E §三、R440F §一）；等人類跑 R440F §四那一行 |
| E2／E3 | 同樣需要 gemma，一起等 |
| 迴圈 | 新版 loop.sh（含 fable 層）PID 2538820，04:39:34 UTC 起，從第 4910 輪繼續 |
| 閘門 | `gain_run.py --decision` 必填，檔存在且含 run 名才啟動（26c4d52，本機驗過拒絕×2／放行×1／不留空目錄） |
| 發射器 | `ops/gain/launch_e1.sh prep\|launch\|all`（f7457f1），內含 R440E 的 `--decision` |
| 已終止的 run | `g_on_qwen_only_scale2`（80% void，資料只作 infra 觀察）、`g_e2q_off_lcb_qwenonly`（未預註冊，1 題後被第 4911 輪終止）、`g_off_probe_20260902_n60`（preflight 404 擋下） |
| 迴圈規則 | LOOP_PROMPT「E1 視窗」六條：不寫 local、不起 run、不殺 E1、收數字格式、發射不歸迴圈、人類拍板前 8765 上不得起任何 gain_run |

## 二、人類若在夜裡對 1004 動手並發射 E1，迴圈該做什麼

1. 開場的重複 run 檢查會看到 `gain_run.py --out runs/g_r441_gemma_only_mbpp`——**那是 E1，
   不是孤兒**，不要照 round460 的邏輯殺它。
2. 照 TASKS_OVERNIGHT A2：每 60 題一個檢查點（sonnet）——OFF 失敗率、void 率、ON/OFF5
   配對 b/c、評審準確率−almost-PASS、rows.jsonl 行數＋sha256 前 8 碼。
   **任一臂 infra_void >20% 立刻寫 DECISION 停手**（R440 中止準則），不要像 scale2 那樣
   拖四輪。
3. ≥90 題時 `echo fable > ~/vacant/NEXT_MODEL` 起一次稽核輪（A3）：重算配對表、核行數與
   hash、對照 R440 P1–P4 與 R440C P0（gemma 單獨在卡上 ON void 應 <35%）。
4. `~/vacant/logs/launch_e1.log` 是發射過程的完整紀錄，`runs/g_r441_gemma_only_mbpp.backend.json`
   是發射當下 1004 的模型快照——收官報告要引用這兩個檔。

## 三、人類若整夜沒動 1004

- 什麼都不要起。R440D／R440F 的裁決仍然有效：infra 未修前 8765 上不起任何 run。
- 迴圈做 TASKS_OVERNIGHT 的 B 項（唯讀驗證 win1003 的 `night-scene-20260901` 分支）與展件，
  不要為了「這輪要有進度」再發明新的實驗。
- 早上 07:00（台北）寫 `MORNING_20260903.md`：一頁，E1 狀態一句話、1004 現況一行、
  被擋的指令清單（如有）。

## 四、明早 resume 的 session 先讀什麼

依序：本文件 → `MORNING_20260903.md`（若迴圈有寫）→ `git log --oneline -20` 看夜裡的
round 編號 → `~/vacant/logs/launch_e1.log`（若存在）→ R440E §四／R440F §四 的人類決定
是否已落地。**不要重做已經做過的探測**：1004 拓撲在記憶與 R440C §一，閘門驗證在 R440G-fix。

## 五、明確不做的事（本 session 下線前）

- 不對 1004 發任何 load／unload（分類器擋，且是人類的決定）。
- 不殺任何 run、不 touch STOP、不改實驗碼。
- 不再改 LOOP_PROMPT（六條夠了；再多是噪音）。

## 六、本 session 被權限分類器擋下的確切指令（彙整，供明早一次看完）

1. `scp ops/gain/queue_e1_after_scale2.sh user1@100.124.254.83:~/vacant/bin/`（R440D §五）
2. `ssh user1@100.124.254.83 'setsid nohup bash ~/vacant/bin/queue_e1_after_scale2.sh 2513538 …'`（R440D §五）
3. `curl -X POST http://100.86.226.21:1234/api/v1/models/load -d '{"model":"gemma-4-12b-it-qat","context_length":32768}'`（R440E §四，連與 3.8 並存的零擾動嘗試都擋）
4. `ssh user1@100.124.254.83 'kill -TERM <pid of gain_run.py --out runs/g_e2q_off_lcb_qwenonly_20260902>'`（R440F §三；後來第 4911 輪自己終止了）

放行過的：唯讀 ssh 探測、`touch ~/vacant/STOP`＋TERM 第 4909 輪（local）＋起新 loop.sh、
git commit／push、本機閘門驗證。分界線看起來是「對 1004 的模型狀態」與「在遠端起長時間
背景 run／殺 run」兩類要人類，其餘可自主。
