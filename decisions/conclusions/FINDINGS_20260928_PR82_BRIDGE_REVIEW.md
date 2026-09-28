# PR #82（Native Acceptance Bridge）審查（2026-09-28）

審查對象：`origin/review/c5-native-acceptance-v2-20260928` @ `8d2f2411`（`ops/eval/native_acceptance_bridge.py`、測試、README）。
方法：三個角度（語意、信任邊界、實驗設計）各一個審查，每一條再由另一個代理**實際跑**重現（workflow `review-pr82-bridge`，run `wf_6a9f7ee2-82d`）。
重現腳本：`ops/eval/evidence_20260928_pr82_review/{probe,repro}/`（跑法：`WT=<PR 的 worktree> PYTHONPATH=$WT PYTHONDONTWRITEBYTECODE=1 python <script>`；全部是合成的小題，沒有題庫內容）。
**我沒有改 PR、沒有在 PR 上留言**（那是人類的 PR）；這一份給人類與修 PR 的 agent。

## 一句話

核心路徑是對的（凍結交付物 → 驗收時重算套件雜湊、變了就 HOLD → 只從隔離區放行同一個雜湊；repair 模式的交件前檢查真的會跑釘住的套件、把失敗送回）。
但**有 3 條高嚴重度問題讓它現在還不能拿來做實驗**，另有 10 條中低嚴重度；實驗設計上，C5 的數字顯示 GATE 不可能提高正確交付、CONFORM 的上限大半是「撞時限重跑」，需要一個不用套件、預算相同的重跑對照組。

## 高嚴重度（都重現）

| # | 問題 | 重現 | 修法 |
|---|---|---|---|
| H1 | `judge` 讀的是 agent 可寫的 `/app/.vacant/contract.json`，從不對照 prepare 時簽的鎖：agent 改掉合約（換成自己的套件、改驗證器）⇒ 錯的解 `accept`、結束碼 0（release 才拒絕，但 CONFORM 已經停止重試） | `repro/r1_contract_tamper.py`、`probe/test_probe_bridge.py::test_judge_accepts_under_tampered_contract` | prepare 把鎖住的合約存到 receiver home；judge／release／status 只讀那一份；送出前 `approval.check_lock(flow._lock_for(task))`（`server.py` 已經這樣做），不合＝HOLD、另一個結束碼 |
| H2 | `--receiver-home` 沒有被檢查：省略、放在 `/app` 底下、或和 agent 同一個帳號 ⇒ agent 可以重簽鎖，錯的解被接受**並放行**；放在工作區底下又用萬用字元交付物時，receiver 的私鑰被凍進成品、一起發布 | `repro/r2_relock.py`、`repro/r9_keys.py` | 沒有 receiver home、或它在工作區底下 ⇒ 拒絕（除非明寫 `--insecure-same-account`，並記在輸出與合約）；交付物排除 `**/identity.key`、`**/intake/keys/**` |
| H3 | `release` 放行的是這個任務帳本裡**最新被接受**的成品，不是剛剛 judge 的那一個：同一個 task id／receiver home 跨種子或重跑，第二跑被拒、卻發布了第一跑的正確解 | `repro/r7_reuse.py`、`probe/test_probe_bridge.py::test_stale_accept_from_previous_run_is_released` | `release --artifact <judge 回的 sha>` 必填；prepare 加每一跑的 run id（合約雜湊每跑不同）或帳本已有事件就拒絕 |

## 中低嚴重度（都重現）

- **嘗試次數沒有被執行也沒有被記**：gate（最多 1 次）可以一直 `--attempt 1` 重判到過；CONFORM 可以超過上限；`status.attempts` 永遠 0（`repro/r11_attempts.py`）。⇒ judge 數帳本裡這份合約的 `candidate_frozen`，要求遞增、不超過上限、接受之後不再判，寫 `attempt_started`。
- **巢狀的測試檔被釘住卻不會跑**：prepare 用遞迴找 `test_*.py`、雜湊整棵樹，執行器只跑最上層；失敗的巢狀測試被跳過、錯的解被接受（`repro/r8_nested.py`）。⇒ prepare 用執行器同一個規則驗證，有子資料夾就拒絕。
- **套件格式錯、基礎設施錯被當成 FAIL**（pytest 風格的 `def test_*`、找不到 python3）：正確的解被拒、repair 還把回饋輪數用完（`probe/test_probe_infra.py`）。⇒ prepare 先檢查每個檔有 `check_*`／`main`；檔案層級的驅動錯誤＝UNKNOWN。
- **預設的套件在工作區裡**：agent 加一個自己的測試檔（常見行為）⇒ 每一次都 HOLD、CONFORM 一直重試進同一個 HOLD；背景行程換檔的競態 40 次裡 9 次讓錯的解通過（`repro/r3_toctou.py`、`probe/test_probe_freeze.py`）。⇒ prepare 把套件複製進 receiver home、釘那一份；驗證器先複製到暫存、驗雜湊、再跑同一份位元組。
- **放行的目的地在工作區裡**（`dir:.vacant/native-release`）：放行之後 agent 可以改檔、或用 symlink 讓 receiver 寫進自己的套件；`status` 讀帳本、看不出來（`repro/r4_destination.py`）。⇒ 目的地預設在 receiver home；評分讀隔離區的那一份（依 sha）。
- **`python_checks` 可以被候選解偽造**（在 bwrap 裡也可以：import 時直接寫出通過的紀錄與結束標記、`os._exit(0)`；`repro/r5_forge.py`）。合約裡的 `trust_boundary` 說法過頭。⇒ 提供行程外的 `command` 或資料式的 SuiteSpec 驗證器（`vacant_network/suitespec.py`：擬態攻擊不可表達），並改寫說法。
- **REPAIR 會安靜地變成 GATE**：README 建議套件放在另一個帳號底下，但交件前檢查是以 agent 的身分讀套件；讀不到＝UNKNOWN＝放行、不回饋（`repro/r6_unreadable.py`、`probe/test_probe_unreadable.py`）。⇒ repair 模式要求 agent 讀得到（寫不了）的套件，或另釘一份唯讀副本給交件前檢查用；預註冊一個操弄檢查（有多少格真的收到回饋）。
- agent 看得到的 `/app/tests_visible` 和 receiver 的副本從不比對（`repro/r12_diverge.py`）。

## 實驗設計（依 C5 的沒裝組 920 題）

C5 的沒裝組：748 對；89 可見過、隱藏沒過（其中 62 在 MBPP+）；41 可見沒過但有檔（30 撞時限）；42 沒檔（33 撞時限）⇒ 可見沒過的 83 題裡 63 題是撞時限。

| 臂 | 正確交付 | 交出錯的 | 說明 |
|---|---|---|---|
| NATIVE | 748 | 130（交出 878） | 基準 |
| GATE | 748（不可能變多） | 89（−41） | 扣下 83；結果用評分器就能從 NATIVE 算出來，**不必另外跑** |
| CONFORM | 上限 831（+83，+9.0 個百分點） | 至少 89 | 事後估：多一個工作階段 ≈ +38 對、+7 錯（拿 C361 當同一 83 題的第二次） |
| REPAIR | 上限 ≤ +20 | — | 只有走到交件前檢查的：11 可見沒過＋9 沒檔；pi 自己已經在 809／920 跑了 `sh run_tests.sh` |
| Evidence v3.7 | — | — | 最終重播第一次就退回的只有 29 跑 |

- **沒有套件的重跑規則**（「撞時限或沒檔就開新的工作階段」）已經涵蓋 83 題裡的 72 題：套件本身在正確交付上只多 11 題（1.2 個百分點），在「交出錯的」上多 41 題。
  ⇒ 要一個**預算相同的 RETRY-NOSUITE 對照**（同樣的最多幾個工作階段與每次時限；撞時限或沒交就重跑、留最後一次），確認性的比較是 CONFORM 對 RETRY-NOSUITE，主要指標 `released AND hidden_pass`，「交出錯的」當 Holm 共同主要。
- **巢狀設計**：CONFORM 的第 1 次就是 NATIVE 那一跑；REPAIR／Evidence 從第一次交件前檢查的快照分岔。不要拿巢狀的臂對 NATIVE 做 McNemar（一邊幾乎是 0）。
- **檢定力**：每題跑一次、920 題、不一致率約 11.7% ⇒ 80% 檢定力大約只看得到 +3.2 個百分點；REPAIR（≤ 2.2）與 Evidence 看不到。
- **評分要讀放行的成品**：C5 的評分器讀 `/app/solution.py`，GATE 的拒交還是會被算成交出。零成本的前置檢查：在 920 份歸檔的 NATIVE 工作區上跑 bridge judge，和評分器的 `visible_pass` 要一致。
- **裝了 Vacant 的臂和 bridge 共用工作區時**，合約會關掉零設定的 Evidence、擋掉寫測試資料夾——每一臂有沒有裝 Vacant 掛鉤要預註冊。

## 產品（CLAUDE.md 的零設定原則）

bridge 每一臂都要評測者給 task id、套件路徑、交付物、receiver 金鑰——**不是零設定**，回答的是機制的上限，不是「裝了就變好」。
最小的零設定版本（建議當一個候選臂：TESTS-AT-STOP）：自動找專案自己的測試入口（`run_tests.sh`、pytest 設定、`package.json` 的 test、`Makefile` 的 test）→
在 agent 動手之前的第一個簽章快照裡釘住 → 交件前在隔離沙箱裡跑（測試檔用快照裡的原版）→ 失敗就把輸出退回一次、失敗一律放行。
GATE（扣下結果）和互動使用的「失敗一律放行」衝突；CONFORM 只適合 headless 的 `vacant do`。在 C5 上這個版本比 v3.7 最多多 11 格；更大的槓桿是評測的時限，互動使用沒有。

## README 要改的說法

- 「`mode: evidence` 是 C5 沒量到 CONFORM 那種差別的主因」——沒有量過，寫成假設，並寫上面那張上限表。
- v3.7 的重播表與 `SCRIPT_RUNNER` 是審查前的 `122a424c`；最終版是 `7db9bacf`／`7c63a132`（第一次就退回：Colab 309→29、u274 36→20、S36-nocap 不變）。
- 寫明 bridge 不是零設定。
