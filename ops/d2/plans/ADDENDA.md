# D2′ 計畫檔附註（更正事實；不改預註冊本文的判準）

計畫檔一旦開跑就不再改（改了 sha 會變、續跑會被擋）。以下是 2026-11-25 獨立稽核之後的事實更正，**判準一字不動**。

## main_d2_qwen9b_1003.json、main_d2_gemma12b_1003.json、main_d2_gemma12b_1004.json
- `prereg.known_limits` 第 6 條寫「只有本機 1003（1004 離線）」：寫計畫時 1004 已經恢復，12B 有一半就跑在 1004（見 `prereg.models_and_strata`，那一段是對的）。
- 計畫 commit（d9d2c707b）到第一通模型呼叫只隔約 4 秒，當時沒有先推遠端、沒有外部時間戳；推上 `origin/auto/redo` 是開跑之後。之後的批次（sens2、留出、Haiku 以後的）執行器會先檢查 HEAD 已在遠端才開跑，並在 RUN.json 記 HEAD 與各腳本 sha。
- 12B@1003 那一半由等候腳本在 9B 結束後發射，載入的是當時最新的執行器（判準與提示和計畫 commit 時相同，已用程式比對舊教材的四種提示逐字不變；多記的只有 RUN.json 的 HEAD／腳本 sha 與存取紀錄的臂與週期）。

## main_d2_haiku.json
- 從 9B 計畫複製時，`prereg.common` 仍寫「agent＝pi＋掛 `vacant install --agents pi --mode observe`」：實際是 **Claude Code**（`claude -p`，claude-haiku-5-5）＋`vacant install --agents claude --mode observe` 真的寫出的掛鉤（`model` 與 `agentcfg` 欄是對的）。
- `prereg.cost_metric`（主要成本量＝美元）是**看過 Haiku 小量試（s57）之後**才定的；這一點結論檔要寫明。

## 開跑後改過的分析／評分程式（結論檔逐一列出）
| commit | 檔 | 改了什麼 | 會不會改變主批次數字 |
|---|---|---|---|
| a4ecc7749 | score_d2.py | manifest 沒有 `cycles` 時週期類型當 F | 不會（真實 manifest 都有） |
| 8a395e133 | audit_d2.py | 同上（週期數） | 不會 |
| 31bc3d13b | score_d2.py、analyze_d2.py | Claude 的輸入 token 含快取讀寫、加 `cost_usd`；`--cost-metric` | pi 的數字不變（沒有快取欄位） |
| b4d47b4d2、747f2ce33 | run_d2.py、source_server.py | 留出教材、b2／d2／c_every／d_diff、RUN.json 記 HEAD、存取紀錄帶臂與週期 | 已開跑的批次載入的是舊版；12B@1003 載入新版（見上） |
| daaafa7fe | audit_d2.py | 獨立稽核第 1–3 點的修正（歸因、出處、驗鏈） | 不改分數；改歸因表與出處表 |
| efacf883f | report_d2.py | 開跑後新增的報告產生器 | 只產生報告 |

## 2026-11-25 ~07:00 UTC 事前決定（在看 9B 主批次最終數字之前寫下並推上遠端）：LM Studio「Context size has been exceeded」

**事實**：1003 上 qwen3.5-9b 載入時 ctx 32768、parallel 4，這 32768 是所有同時請求共用的 KV。06:38 留出批次開跑後，1003 上同時有 9B 主批次 3 個＋留出 2 個 agent，總上下文超過，LM Studio 對部分請求回 500「Context size has been exceeded」。不是提示本身太長（s36 c 臂第 1 週期那一次的提示只有兩行交辦，連第一通呼叫都被拒）。06:38 之前的 37 組（s01–s37 的初稿與大部分臂）沒有這個錯誤。

受影響的執行（從 agent.log 掃出）：
- 9B 主批次：s38/c0、s50/c0、s36/c/cycle_1（0 次成功回應，執行器判成基礎設施失敗、停組）、s37/b/cycle_4、s38/b/cycle_3、s43/d/cycle_4、s49/b/cycle_3。
- 留出批次：s01/c0、s02/c0、s05/c0、s04/c/cycle_1（留出批次只看了這張清單，沒有看任何分數或逐條結果）。

**處理（主要分析）——照預註冊字面**：預註冊的基礎設施失敗＝「0 次成功回應＋連線錯誤」。500「Context size has been exceeded」不是連線錯誤，所以：
1. s36 c 臂第 1 週期那一次算「執行了、沒有改動」。續跑時用 `forced_noop.json` 讓執行器在 s36/c/cycle_1 不再叫 agent、直接把那一次的用量（0 次成功呼叫）記成這一週期的執行，報告維持週期開始時的樣子；c 臂從第 2 週期接著跑；s36 其餘還沒跑的臂照常跑。原始那一次的紀錄另存 `cells/s36/c.attempt_failed_ctx/`。
2. 其他受影響的執行（有成功回應、中途被拒）照常計分，不排除。

**敏感度分析（事前登記）**：(a) 去掉任何一次執行出現這個錯誤的組（9B 主批次：s36、s37、s38、s43、s49、s50；留出：s01、s02、s04、s05）重算全部判定；(b) s36 的 c 臂改成整臂重跑（另存，不取代主要分析）。結論檔兩種都報，判定以主要分析為準。

**修正**：9B 主批次結束後，先停留出批次（SIGTERM，正在跑的那一格丟掉、可續跑），把 1003 的 qwen 重新載成 ctx 65536，再續跑留出批次（同一個 root）、發射 sens2。之後 1003 上同時跑的 9B agent 不超過 4 個。

## 獨立稽核複查（11-25）的更正
- 上面「推上遠端是開跑之後」寫反了：本機 reflog 顯示 d9d2c707b 在 06:10:07 推上，早於第一個 agent 事件（reflog 仍不是外部時間戳）。
- 漏列：`cfdcae3bc`（06:12:57，凍結之後把零設定誤判修正 `trace/evidence.py` 提交進 repo；不在 wheel 裡、不影響任何實跑）；`54bcb1d81`（06:48:25 改 run_d2 刪目錄重試，在留出批次開跑後——留出批次載入的是舊版，續跑時載入新版並記在 RUN.json 的 resumes）。
- Haiku 主批次（06:46 開跑）載入的執行器版本與 9B 主批次（06:10）不同：多了 Claude 的接法與 b2／d2 等臂；pi 的提示與四臂邏輯相同（RUN.json 有各自的 runner_sha256）。
- 「12B@1003 由等候腳本在 9B 結束後發射」照舊有效；留出計畫的 known_limits 從 9B 計畫複製而來，裡面「1004 離線」「與 gemma 同機載入」兩句對留出批次不適用（留出批次在 1003、與 gemma 同機，但 1004 已恢復）。

## 2026-11-25 ~11:10 UTC 事前揭露（在看 r2heldout_b 任何結果之前寫下並推上遠端）：c_verify 的實際協定

**事實**：`ops/d2/run_d2.py` 第 524 行，「沒有出處的行（同一行文字）只交辦一次」的抑制條件寫成 `arm == "c"`。所以 **c_verify 臂（和 c_every 一樣）每個週期都會把沒有出處的行重新交辦**；再加上驗收步驟：改完後再跑一次來源檢查，交辦過的行仍不是 unchanged 就退回一次——沒有出處的行改完通常仍然沒有出處，所以也會被退回。
實際的 c_verify＝**c_every（沒出處的行每週期重交）＋用紀錄驗收修正（退回一次）**，不是計畫文字寫的「c＋驗收」。

資料（從 cycle.json 數）：
- 留出 v2（r2heldout_qwen9b_1004）：交辦行數 c 108、c_verify 181；c_verify 退回 100 行。c 的 5 個漏抓都是「沒出處、只交辦一次之後不再看」；c_verify 每週期重交，所以補回來了，也因此 token 是 c 的 2.9 倍。
- 9B 第二輪主批次（r2main_qwen9b_1003）：沒出處的行幾乎沒有（c 0、c_verify 2），交辦 198 對 200、退回 10 行，兩臂成本相近。

**處理**：
- r2heldout_b 已經用同一份程式在跑（11:00 起），**不中途改程式**；它的主要臂就是上面描述的實際協定。結論檔照實寫成「沒出處的行每週期重交＋驗收退回」，不寫成單純的「驗收」。
- 這件事是我在寫結論、回頭核對程式時發現的（11:05 左右），不是看了 r2heldout_b 的結果才發現（那時它剛開跑、還沒有任何週期跑完）。
- 第二輪 9B 主批次、Haiku、留出 v2 的 c_verify 數字，結論檔一律照這個實際協定解讀。

## r2heldoutb_d2_qwen9b_1003（附註）
- **c_verify 的實際機制**見本檔「2026-11-25 ~11:10 UTC 事前揭露」那一節（commit b79e6708c）：c_verify＝沒出處的行每週期都交辦＋驗收退回一次，不是單純的「c＋驗收」。這一節在批次開跑後約 4 分鐘寫下，當時還沒有任何週期跑完。結論把 c_verify 與 c 的差異歸因給「每週期重交」這個協定；第二輪沒有跑 c_every，兩個因素分不開。
- c_verify 升為主要臂是看過留出 v2 之後；d_diff 沒有跑（最強的便宜基準不在這一批裡）。

## 2026-11-25 最終稽核後的補記
- `ops/d2/run_d2.py` 在 r2heldout_b 運行中被改過：commit 151359c09（12:51），為邊界測試加了「只跑初稿、提示變體、初稿後記錄出處」，受計畫的 `write_variants`／`provenance_after_c0` 鍵控制，預設路徑不變。r2heldout_b 載入的是開跑時的舊版（它的 RUN.json 記的 runner_sha256 與現在的檔不同）。
- `ops/d2/run_d2.py` 的 `NO_PROXY` 原本寫死兩台 GPU 主機的內網位址；最終稽核後改成從環境變數 `D2_MODEL_HOSTS` 讀。在這之前開跑的每一批，RUN.json 記的 runner_sha256 都是寫死位址的舊版。
- `ops/d2/anchors/*.json` 的 `"root"` 原本是含系統帳號名的絕對家目錄路徑；同一個 commit 起改成只記 root 的名稱（`anchor_d2.py write` 同步改）。舊提交裡的版本留在 git 歷史中，沒有改寫歷史；`check` 不比對 `root` 欄，錨點的雜湊內容不受影響。
- 邊界測試的抓取寫法分類原本按「指令字串裡有沒有 python 字樣」分，把 `which wget python3` 這種偵測指令誤判成 python（s23、s27）；改成看真的抓了來源網址的指令（`ops/d2/bnd_coverage.py`）。更正後：python urllib 4 組 0/80、wget 6 組 120/120。

## r3haiku_d2（2026-11-25 17:21 UTC 附註，續跑前寫下並推上遠端）

- 17:19 開跑後，看到前 3 組 cCGR 第 1 週期的候選檢查都是 20/20 no_source，17:21 手動停批（SIGTERM）查原因；沒有改任何程式、計畫或教材。
- 原因（看紀錄得知）：Haiku 在有索引頁的教材上用一個 shell 迴圈抓全部頁面（`cd /tmp && for f in a.md b.html …; do echo "===== $f"; curl -s "http://<host>/$f"; done`），指令裡的網址是 `…/$f` 而不是字面網址，輸出太大被 Claude Code 存成檔再用 Read 讀進來。v3 的候選集合只從指令文字裡的字面網址取候選，這種寫法取不到——這是計畫 known_limits 寫過的「指令裡沒有字面網址時抓不到」。
- 處置：照預註冊（產品 v3 一行不改）在同一個 root 續跑；被停的 s02 cCGR 週期 4 由執行器的續跑規則重做。這一批預期覆蓋率不過，照實報。

## 第四輪 harness 修正（2026-11-25 19:20 UTC，第四輪任何模型呼叫之前寫下並推上遠端）

- **沒有出處的行交辦時給索引頁**（計畫旗標 `nosrc_index`）：第三輪 Haiku 那批，網址抽取在 `/$f` 前停下、留下只剩主機名的「候選」，runner 有候選就拿它當來源寫給 agent。第四輪起，來源檢查狀態是 no_source 的行一律寫「沒有出處，網站是 <索引頁>」，不用候選字串。只對有這個旗標的計畫生效（之前的批次照它們當時的程式重現）。
- **真實版頁面變動偵測 `d_diff_real`**：執行器每週期經來源伺服器實際抓一次每張頁面（User-Agent `d2-notifier`，稽核的 served() 排除它），和上一週期抓到的比；每次抓取的雜訊會讓它每週期都觸發。理想版 `d_diff`（用教材檔算，不受雜訊影響）保留當上限。
- **網路出口代理**（計畫旗標 `egress`）：每組一個 `vacant trace egress`（產品），agent 的 http_proxy 指向它、它的上游是來源伺服器；Vacant 自己的重讀照舊直連來源伺服器（不進出口紀錄）。模型主機在 NO_PROXY 裡，不經過代理——冒煙的出口紀錄 79 筆全是 `*.d2-sources.example`。這個代理在實驗裡由 runner 啟動；產品裡「安裝後自動對 agent 生效」還沒做（要改各 agent 的環境設定）。
- 稽核：候選臂（cC*、cV）的漏抓分出「沒交辦：值還在比對到的位置（看值）／候選片段沒變（看片段）」；「有沒有重讀」另外收來源伺服器的存取紀錄（變數拼網址的抓取在指令文字裡看不到）。

## 第五輪（2026-11-25 23:00 UTC，第五輪任何新批次的模型呼叫之前寫下並推上遠端）

- **r5seen4 作廢**：22:39Z 開跑、22:45Z 手動停批（SIGTERM）；只完成 2 組初稿與 s01 的一部分。它跑的是 v5（555cd0568），其中守衛的 `--keep-labels` 建立在錯的診斷上（獨立稽核 11-25 查到越界守衛的 `_line_key` 撞鍵 bug，「agent 把欄位名一起改掉」是錯的歸因）。這一批的資料不用、不分析。由 r5seen4b（同一份教材 heldout-v4 種子 20261171、產品 v5.1）取代。
- **產品 v5.1**（7d574c3d3）：守衛改用改前那一行到「: 」為止的整段標籤對行；撤回 keep_labels 行為。主 checkout（~/dev/Vacant）因 22:48Z 一次下錯的 `git stash pop` 套上一份無關的舊 stash、5 個 reqloop 檔衝突、無法提交，還原動作被權限機制擋下、等擁有者決定（~/dev/ops/STASH_CONFLICT_20261126.md）；v5.1 與第五輪計畫從新的 worktree（~/dev/wt/d2r5，分支 d2/r5-guardfix）提交、推上 auto/redo，runner 也從那裡執行。
- 真實教材抓取因維基百科 429 限流，目標從 30 組縮成 20 組（照慢速、每秒最多一個請求、不加併發）。

## r5real 9B 兩批重開（2026-11-26 00:50 UTC，新 root 的任何模型呼叫之前寫下並推上遠端）

- 00:38Z 開跑的 r5real_d2_qwen9b_1003／1004（root r5real_1003、r5real_1004）跑了約 8 分鐘就看到大量「Context size has been exceeded.」：1004 有 24 次 agent 執行、1003 有 2 次；1004 的 s14 因此成為 InfraError。原因是基礎設施設定：兩台的 qwen3.5-9b 載入在 ctx 65536、parallel 4（共用 KV），真實維基百科頁面一頁 50–70 KB，agent 讀兩三頁就超過；被截斷的執行會讓「整份重查」這種讀全部頁面的臂吃虧，結果會偏向主要臂。
- 處置：00:47Z 停掉這兩批（SIGTERM）；兩台都改成 ctx 131072、parallel 2 重新載入（`lms load qwen/qwen3.5-9b -c 131072 --parallel 2`，估計 13.3 GiB，和同機的 gemma 一起放得下）；**兩個舊 root 作廢、不分析**；同一份計畫（7da900d6b，未改一字）以新 root r5real_1003b、r5real_1004b 重新從頭跑（jobs 仍是 2）。這是在看任何結果之前做的。
- Haiku 那批（Claude Code，200k context）不受影響，照常跑。
- 兩批描述性對照（r5h3b、r5seen4b，合成教材頁面小）在 ctx 65536 下跑完，各自的超出次數見結論。
