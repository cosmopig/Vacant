# vacant-dev＋1003／1004 複製批次（任務導向 94 題 → DABstep 79 題）— RUNLOG

預註冊：`decisions/prereg/PREREG_20261002_VACANTDEV_REPLICATION_V37.md`。時間 UTC。

| 時間 | 事件 |
|---|---|
| 09:53 | 人類：「把這些東西都丟去 vm 上測試，用 1003 1004 去跑，可以跑很久沒關係，儘速丟上去」；09:57「先以任務導向的那些」 |
| 09:54 | vacant-dev（Ubuntu 24.04、8 核、7 GB、磁碟剩 4 GB、load 0）；1003／1004 都載著 `gemma-4-12b-it-qat`（262k context）、`reasoning_effort: none` 時沒有 reasoning、延遲 1.2–1.5 秒。分身專用的 .102 不碰 |
| 09:58 | 舊實驗的 repo 副本都只有幾 MB，清不出空間 ⇒ 改成「格子打包進 chunk 後只留 DONE／meta／score／vacant_check」（`cleanup_packed.sh`）；DABstep 的 7 個資料檔在 79 題之間用硬連結（23 MB 一份） |
| 10:00 | `setup_vd.sh`：apt 補 pipx、python3-pandas（2.1.4）；wheel 在這台重建 ⇒ **sha256 `92ddc44d…` 與 Colab 那顆相同**、114／114；node v22.23.2、pi 0.87.1。第一次圍牆自我檢查失敗：bwrap 要蓋 `/content` 但這台沒有 ⇒ 建空的 `/content`，重跑通過（負控制 OK）。代理 upstreams `g1003`／`g1004` |
| 10:02 | 經代理打兩台：都沒有 reasoning。磁碟剩 3.0 GB |
| 10:03 | 預註冊凍結（本 commit） |
| 10:00:58 | **發射佇列**：`run_queue.sh`（t3L：`UP=auto AGENT_TIMEOUT=1800`、8 位置、不設時限；跑完且打包完 ⇒ d37L：`MAX_TURNS=15`）；`cleanup_packed.sh` 常駐 |
| 10:17 | 前 6 格（dabench）：rc 0、沒逾時、C 裝上且走到交件前檢查；代理 169 通全 200（g1003 77、g1004 92）；load 低、記憶體可用 6 GB、磁碟 2.7 GB |
| 10:18 | Mac 端 `sync_vd.sh`：每 20 分鐘 rsync `/srv/eval/archive` 到 `~/Vacant_colab_raw/vacantdev_replication_20261002/`、逐個驗 sha256；這次沒有 GPU 計費（人類自己的機器），不需要自動關機 |
| 11:53 | 64 格完成（第 1 次；A 32／C37 32）、逾時 A 9／C37 6、安裝失敗 0；每格牆鐘中位 304 秒。代理 2,050 通全 200（g1003 745、g1004 1,305）。**吞吐低**：最近 30 分鐘兩台各只約 33 生成 tok/s（單條中位 g1003 37、g1004 12 tok/s；g1004 延遲中位 45 秒，請求在 LM Studio 排隊）⇒ 約 0.57 格／分，兩批合計估 35–40 小時。不動 LM Studio 設定（人類的機器）。Mac 同步迴圈睡太久（Mac 休眠），重開後 12／12 chunk 驗過 |
| 12:52 | 人類：「1003 也可以用吧，或是你直接用 100.119.113.56:5500 吧」。查 5500：是 1003 上的 `lmsmon hub`（同 8765 那份 config）——`strategy: least-busy` **每一通請求**各自挑機器、`force_thinking: true`、`default_max_tokens: -1` ⇒ 同一段對話會在兩台之間跳（2.5 萬 token 的提示每次重算）、而且強制思考，**不適合**這個實驗，不用。1003 其實已在用（745 通）；慢的原因是 cksum 分配不均（1004 1,305 通、延遲中位 45 秒；1003 7 秒） |
| 12:56 | **偏離預註冊（分配規則）**：`cell.sh` 改成「每個單位開跑時分給進行中格數較少的那台（平手 g1003）」，同一單位的各組讀同一個決定檔（`/srv/eval/unit_up/`，鎖裡決定）⇒ 組間仍在同一台、台的差不進組別的差。原子替換（`mv`，跑到一半的格子不受影響），新 sha256 `b4868f69…`。正在跑的 8 格依舊規則補 `upstream` 檔供計數（第一次補錯欄位、立刻重補）；自我測試選到 g1003。分析時兩台分開列 |
| 18:27 | ⚠ **1003 的 LM Studio 沒有載入模型**（代理回 400「No models loaded」）。LM Studio 事件（8766 唯讀）顯示兩台的 gemma 從 10-02 23:54（+8）起一再被卸載／載入（間隔常是 5 秒），**不是本實驗做的**；1003 上另有 `/d/lock_queue`（10-03 06:58 +8 建立）。最後一筆：1004 在 20:20Z 被卸載 ⇒ 之後兩台都沒有模型 |
| 18:27–19:09 | ⚠ **新分配規則放大了故障**：分到 1003 的格子幾秒內失敗結束 ⇒ 1003 的「進行中」一直最少 ⇒ 新單位一直被分到 1003 ⇒ t3L 第 3 次幾乎全部、第 2 次 26 單位在 1003 上失敗。規則沒有健康檢查，是我的設計缺陷 |
| 19:09 | t3L 佇列走完（564 格）；d37L 開跑 |
| 19:13 | d37L 可行性規則觸發（最先 40 格的代理呼叫 39／54 非 200）⇒ 停止檔；19:31 ALL_DONE（d37L 只有 51 格，無效） |
| 10-03 04:3x | 診斷（Mac ssh 的 ControlPath 指到不存在的目錄，前幾次查詢都卡住；改 `-o ControlPath=none`）。同步：59 個 chunk 全部 sha256 驗過。t3L void 檢查（不讀分數）：**238／564 void**（A-s3 93、C37-s3 93、A-s2 26、C37-s2 26）；第 1 次 188 格完整 |
| 04:40 | 停住，等人類決定：兩台都要重新載入 gemma 才能補跑／續跑，而載卸是別的工作在做的 |
| 04:45 | 人類：「你去處理載卸，我等」（＝人類處理 1003／1004 的模型載入，好了通知）。在那之前**不發射**，只備好續跑：`cell.sh` 加健康檢查（LM Studio `/api/v0/models` 要有 gemma `state=loaded` 才分；兩台都不行就每 60 秒再看，寫 `unhealthy.log`）；`resume_queue.sh`：t3L 的 238 格 void（119 個單位、全部成對）移到 `void_try1/` 用同前綴補跑一次（預註冊）→ d37L 第一次的 51 格移到 `aborted_d37L_try1/`（不進分析）、從頭重跑；從 `packed_cells.txt` 拿掉這些名字、清 `unit_up/`、重開瘦身常駐。void 清單由本機用完整 chunk 算（`t3L_void_try1.txt`） |
| 04:5x | 人類：「你自己掛」。LM Studio REST `POST /api/v1/models/load {"model":"gemma-4-12b-it-qat","context_length":262144}`：1003 9.6 秒、1004 7.1 秒，兩台 `loaded`、262144。經代理打：都沒有 reasoning。vacant-dev 起 `~/keep_gemma.sh`（每 120 秒；哪台沒載著 gemma 就重新載入、記 `~/keep_gemma.log`；QUEUE_DONE 後結束） |
| 04:5x | **發射續跑** `resume_queue.sh`：238 格 void → `void_try1/`、51 格 d37L → `aborted_d37L_try1/`，從 packed 清單拿掉、`unit_up/` 清空、瘦身常駐重開；t3L 用同前綴補跑。4 分鐘後：最近 5 分鐘 g1004 80 通、g1003 31 通全 200，`unhealthy.log` 空、沒有重新載入。Mac 同步重開（加 `ControlPath=none`） |
| 05:2x | **根因調查**（人類：「調查出為什麼會自己掉嗎」）。**1003**（LM Studio 日誌＋Windows 事件，時間 +8）：02:24:58、02:27:05 `Resource-Exhaustion-Detector`「low virtual memory」，最大的是 `llama-server.exe` 約 **54 GB 虛擬記憶體**（實體 31.8 GB＋C 槽分頁檔，分頁檔最高用到 26 GB）；02:24:58 Intel 顯示驅動 igfxn 逾時重置；**02:27:11 `llama-server.exe` Application Error 1000（崩潰）** ⇒ 02:27:29 LM Studio 記 gemma「terminated」、之後「No models loaded」。日誌同時段有 llama.cpp 的 prompt cache 在系統記憶體裡「making room…removing oldest entry」，一筆 2–6.6 GB；4 個 slot、每條對話 1.6–4.4 萬 token、context 262k。1003 在 10-02 另有 5 次同樣的 terminated（本地 00:19、00:32、09:40、10:36、15:09，都在本批開跑之前），之前都有人／JIT 重新載入，這次沒有。**1004**：本地 04:20:12「Unloading model gemma-4-12b-it-qat due to TTL expiration」——d37L 被擋下後閒置約一小時、JIT 的 TTL 到期，正常行為。5 秒一次的 unloaded／loaded 事件沒有對應的 terminated，來源未確認 |
| 05:2x | 對策（已在跑）：`keep_gemma.sh` 每 120 秒自動重載；`cell.sh` 健康檢查不分給沒模型的機器；崩潰中斷的格子＝void，照規則補跑。**沒有改**人類機器上的 LM Studio 設定（prompt cache 上限、分頁檔、parallel），要不要改由人類決定 |
| 05:57 | t3L 補跑的可行性規則觸發：最先 40 格逾時 12（0.30，剛好碰門檻；補跑的單位偏難、偏長）；「非 200 40 通」是同名格子 10-02 的舊 400（ledger 依 tag 算），補跑期間實際非 200 是 0 ⇒ 驅動停開新單位，只補完第 2 次的 25 個單位（50 格），第 3 次的 186 格沒補 |
| 06:27 | d37L 從頭開跑（resume_queue.sh） |
| 06:5x | t3L 期中分析（**第 1、2 次**；第 2 次 dab_657 補跑仍 void ⇒ 兩組拿掉）：A 119 vs C37 124／188，每題平均差 +2.7 pp，C37 好 14 題、A 好 11 題，Wilcoxon（常態近似）p＝0.37 ⇒ **沒有量到差別**。A「說做完卻沒寫答案檔」**0 格**（Colab 任務導向 5／120）；A 沒交的全是撞時限。退回只有 2 格。結果 `results/report_t3L_s12.json` |
| 06:5x | **偏離**：第 3 次 186 格 void 排在 d37L 之後補跑（`after_queue_s3.sh`），那一輪啟動後停掉 feasibility（開跑檢查，不適合補跑）；`keep_gemma.sh` 改成 S3_DONE 才結束。（`pkill -f keep_gemma.sh` 又殺到自己的殼一次，分開重開） |
| 08:50 | d37L 224／711（每小時約 98 格）；逾時 0、安裝失敗 0；最近一小時 g1004 501、g1003 422 通全 200；`unhealthy.log` 空、沒有重新載入。磁碟 2.1 GB 且緩慢減少（`/srv/eval` 只有約 120 MB，打包後瘦身有效；`/home/user1` 18 GB 是舊資料）⇒ 刪掉自己的測試目錄 `/var/tmp/pr82t`、`journalctl --vacuum-size=100M`、`apt-get clean` ⇒ **3.0 GB** |
| 08:5x | **0.9.0 發布**（人類：「先推到 main 更新 pypi」「readme 等全部記得改」）：PR #85（merge redesign 分支＋版本 0.9.0＋CHANGELOG＋README 中英日零設定一節＋CLAUDE.md＋各批紀錄＋PR #82 的 bridge 檔）。CI 第一次只紅 1 個：分身的 `test_twin_vm_retention`（main 原版就壞）⇒ 人類：「把這個 ci 拿掉，數位分身不應該跟 vacant 有關」⇒ CI 不跑 `tests/test_*twin*.py`（檔案保留）⇒ 全綠（Ubuntu 3.12／3.13、macOS 3.12 測試、lint、型別、安全掃描、wheel 冒煙）⇒ 合進 main `09cc052f` |
| 08:55 | Release `v0.9.0` ⇒ publish.yml：build、掛 Release 成功；**PyPI job 被 `pypi` 環境擋**（只允許 `main` 分支，Release 的 ref 是 tag）⇒ 在 `main` 上 `workflow_dispatch`（同一個 commit `09cc052f`）⇒ **PyPI 0.9.0 上線**（wheel sha256 `ae560889…`）。PyPI 的 wheel 與 main 的 `vacant_network/` 逐檔相同 115／115 |
| 09:0x | 從 PyPI 的端到端（vacant-dev 新使用者，照 README 兩行、pi 設定在 `~/.pi/agent`、模型 1003）：`vacant install` 放 `extensions/vacant.ts`；pi 讀 data.csv 寫 answer.txt（7）；病歷 3 步、交件前檢查 1 次 allow、delivery.md 有。小缺口：`vacant --version` 不支援 |
| 14:13 | **d37L 跑完**（711 格，06:27–14:06 開跑；逾時 A 1／C37 2／C37R 1、安裝失敗 0、模型全程 200）；14:15 t3L 第 3 次補跑開始（feasibility 照計畫停掉） |
| 15:2x | d37L void 檢查（本機 123 個 chunk 全部 sha256 驗過，按 chunk 順序先刪同名格子再解壓；711 格全部是重跑那一批）：**1 格 void**——`d37L-C37-dabstep-66-s2`：agent 有交答案，但答案裡有單引號（"isn't"），題目自己的 `test.sh` 用 `xargs` 讀答案、遇到沒配對的單引號就在寫 reward 之前結束 ⇒ 沒分數。照預註冊補跑一次（同一台 g1004、15 回合；從 packed 清單拿掉、舊格子移到 `void_try1_d37L/`） |
| 15:4x | d37L void 補跑完成（有分數）⇒ 第一次讀分數、凍結分析：**A 122 vs C37 121／231，p＝0.84（主要，不顯著）**；C37R 146（p＝0.0051 對 A、0.00076 對 C37）。A「說做完沒寫檔」20 格（Colab 42）；C37 補到 2 但被 15 回合切斷的 59→74 ⇒ 淨 0。傷害 0（4 格候選逐格比對，退回前就錯）。結論 `decisions/conclusions/CONCLUSION_20261003_VACANTDEV_DABSTEP_V37.md` |
| 19:02 | t3L 第 3 次補跑完成（`s3 rerun done`）；期間 1003 崩潰 2 次（15:38、16:43），`keep_gemma.sh` 自動重載。佇列另外把 `dab_657-s2` 兩格又跑了一次（不在計畫內，不採用） |
| 10-04 | 147 個 chunk 驗過；單次讀取解壓（`tarfile`，先刪同名格子再解）；void 只剩 `dab_657-s2`（第一次補跑仍 void）⇒ 兩組拿掉。**最終分析（第 1–3 次）：A 187 vs C37 186／282，−0.4 pp、14 對 14、p＝0.87**；A「說做完沒寫檔」0；退回 4 格、傷害 0（`pg_go_counting-s1` 退回前就只過 5／11）。結論 `CONCLUSION_20261003_VACANTDEV_TASK3_V37.md`（取代期中版） |
