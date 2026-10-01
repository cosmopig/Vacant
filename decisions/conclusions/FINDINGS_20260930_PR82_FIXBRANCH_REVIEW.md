# PR #82 修正分支審查（2026-09-30）

審查對象：`fix/native-acceptance-bridge-audit-20260928` @ `6c2405de`——人類對 PR #82 的 native acceptance bridge 的修正；PR #82 之後以這條分支為底。
差異範圍：`git diff fb32c622..6c2405de`（10 個 commit：`ops/eval/native_acceptance_bridge.py` 489 行、`tests/test_native_acceptance_bridge.py` 225 行、`decisions/reviews/C5_NATIVE_ACCEPTANCE_20260928/*` 文件與 JSON、`ops/eval/replay_r534_gate_scores.py`、`ops/eval/evidence_20260928_pi_plugin/reproduce_same_account_bypass.py`）。它建立在 `vacant_network/intake/*`、`vrun/{acceptance,sandbox}.py`、`adapters/hookpolicy.py` 之上，那些檔案這次沒有被改（`git diff fb32c622..6c2405de -- vacant_network` 為空），只讀。
方法：七個維度（邏輯、安全、收件口、實驗設計、文件、測試、簡化）＋完整性批判者各自審查 → 去重 → 每一條由另一個代理**實際跑**重現並做設計意圖檢查（文件有沒有寫、是不是刻意）→ 全部由代理完成。重現腳本**不入庫**（每條的重現與輸出摘要寫在該條「證據」）。前一份（修正前）審查：`FINDINGS_20260928_PR82_BRIDGE_REVIEW.md`。**審查本身沒有改分支、沒有在 PR 上留言**；依這份審查做的修正見文末「處置」。

注意（資料來源與缺口，引用前先讀）：交給我整理這份文件的確認清單在 F06 中途被截斷，各維度覆蓋筆記也只收到前四個。所以：
- **F01–F06** 是驗證代理的原判（嚴重度是設計意圖檢查之後的，多數從中下修到低）。
- **F07–F21 與 W1–W5（標 †）** 是我依各驗證代理留在 scratchpad 的重現腳本**重新跑過**（全部在 `6c2405de` 上），並**由我重新判斷嚴重度**——不是代理原判；要和代理原判對時以 † 為準重審。W1–W5 是我從測試／批判者／簡化維度的 scratch 補驗的，沒有對應的代理編號。
- 清單裡 `DROPPED` 是空的：沒有任何一條被驗證代理退件。

## 一句話

**在非對抗前提下，上一輪三條高嚴重度（H1 契約、H2 receiver home、H3 放行舊成品）的核心都修對了，這次沒有找到會讓錯的解被放行的新路徑**（唯一仍成立的是已文件化的 `python_checks` 偽造與同帳號）；剩下的是三塊：評測端自己的失誤會燒掉唯一的嘗試、且同一類失誤被記成四種不同狀態（F02／F03／F05／F07／F11）、REPAIR 臂的處理組會靜默失效而收件端看不出來（F18）、13 條測試只守得住 38 個邊界變異體中的 14 個（W1）——這三塊要在跑真批次前處理。

| 嚴重度 | 條數 | id |
|---|---:|---|
| 高 | 0 | — |
| 中 | 2 | F18†、W1† |
| 低 | 24 | F01–F17、F19–F21、W2–W5† |

同根分組（一處修好幾條）：

| 根因 | 條 | 一處修法 |
|---|---|---|
| 評測端的失敗也消耗嘗試、標籤不一致 | F02 F03 F05 F07 F11 | 嘗試次數只在有裁決時才算；infra 一律 `infra_void`＋不計次＋同一個結束碼；judge 以收件端合約為準，工作區副本只當觀察 |
| 邊界的假保證（帳號／沙箱／路徑） | F01 F08 F17 F19 F20 | 分開帳號佈局下拒絕不隔離檔案的沙箱後端；後端與帳號探針的結果簽進 decision |
| prepare 的預檢與失敗清理 | F04 F10 F12 F13 F14 | prepare 先驗證再落地、失敗全部回收；跑一次套件做預檢 |
| 狀態與可觀測性 | F09 F15 F17 F18 | `status` 回報真實讀到的東西；處理組有沒有送達要有紀錄 |
| 證據與文件 | F06 F16 F21 W1 W4 | 補測試、改數字、改標籤 |

## 中嚴重度

**F18† 中 — REPAIR 臂靜默退化成 GATE，收件端的帳本與 `status` 完全看不出來**（`native_acceptance_bridge.py:267` 只在 prepare 時查套件可讀；`adapters/hookpolicy.py:833-841,857-910` `decide_stop` 遇到例外或讀不到都放行）
- 情境（四種，皆放行、沒有回饋）：(a) 評測端 root 用 umask 077：prepare 在工作區寫出 `.vacant`（0700 root）與 `contract.json`（0600 root），agent 帳號的 Stop 掛鉤讀不到，`PermissionError` 只記在 agent 自己的 `errors.jsonl`；(b) agent 的 `VACANT_HOME` 不可寫（例如 `HOME=/nonexistent`）：`_bump_round` 的建目錄例外被吞（同帳號案例實測為 `NotADirectoryError`）；(c) prepare 之後套件對 agent 變成不可讀：UNKNOWN → `allow`＋`not_agent_fixable`；(d) 工作區契約被刪或壞掉：`allow`。四種情況收件端帳本只有 `ledger_genesis／task_opened／contract_locked`，`status` 沒有任何掛鉤欄位，judge 之後那一格就是一個普通的 reject。
- 證據：同帳號 `vf18_same`（刪契約／壞契約／不可寫 home／三輪用完）、分開 uid（私有 mount ns，agent＝nobody、receiver＝root）`vf18_xuid`（X-ctl 有回饋；(c)(b2) 無）、批判者 `repro_secure_layout` R1（umask 077 無回饋，umask 022 對照組有回饋）。我全部重跑，結果相同。上一輪 M9 的修法（prepare 時查 `_readable_by_agent`）只擋 (c) 的一種前置情形。
- 意圖：fail-open 是掛鉤的刻意設計（失敗一律放行），但 bridge 把它當成 REPAIR 臂的處理機制，卻沒有任何處理組送達的量測。
- 修：`prepare` 最後一步以 agent 帳號跑一次 canary（對暫存的必失敗候選跑 `decide_stop`，確認拿得到回饋）並把結果簽進契約 notes；掛鉤把「送出回饋／放行原因」寫到 receiver 讀得到的路徑，`status` 回報 `feedback_rounds_delivered`；預註冊 REPAIR 的操弄檢查（真的收到回饋的格數）；prepare 之後再檢查工作區契約對 agent uid 可讀。

**W1† 中 — 測試只守得住邊界變異體的 14／38**（`tests/test_native_acceptance_bridge.py` 全檔；`:34-39` `_prepare` 寫死 `insecure_same_account=True`）
- 情境：這個修正的目的就是守住信任邊界，BRIDGE_AUDIT 把「13 條 bridge 單元及端到端回歸」當成機制正確的依據；但 13 條測試只殺掉 38 個手工變異體中的 14 個，**24 個存活（63%）**。其中 16 個落在邊界本身：release 的漂移檢查（M02）、鎖檢查（M03）、工作區比對（M04）、`_task` 內 boundary 重查（M05／M19）、目的地必須在 receiver home 內（M06）、只准 `dir:`（M07）、release 只放最新接受的（M08）、金鑰排除出交付物（M15）、`unknown_policy=hold` 改 reject（M16）、套件唯讀 chmod（M17）、可讀與父目錄檢查（M20／M21）、套件 symlink 檢查（M22）、receiver 不在工作區內（M33）、release 不採工作區目的地（M36）。其餘 8 個是冗餘或低價值守衛（flock M18、非 repair 的 `feedback_rounds` M24、重複守衛 M28／M30、雜湊重驗 M29、task id 長度 M35、`conflict_policy` M37、timeout M38）。所有成功路徑的測試都用 `insecure_same_account=True`：分開帳號才會走到的 `_boundary` uid 判斷、父目錄、可讀檢查沒有任何測試走過成功路徑。
- 證據：我重跑 38 個變異體（逐一替換一行、跑那 13 條）：killed 14、survived 24，與測試維度代理的逐條結果相同；代理補寫的 T3–T18（scratch、未提交）殺掉 24 個存活者中的 13 個，仍存活 11 個（M05 M08 M18 M19 M20 M21 M24 M28 M29 M35 M37）。
- 修：把 T3–T18 收進 repo（release 漂移、鎖被改、工作區不符、目的地越界、金鑰排除、unknown→hold、套件唯讀、symlink）；加一個要第二個 uid 才跑、沒有就 `skip` 的分開帳號測試（`setpriv`）；剩下 11 個逐個判等價與否。

## 低嚴重度

**F01 低 — `judge` 預設 `--sandbox auto`，沒有可用的 bwrap 時悄悄退到 `none`；分開帳號佈局下候選碼就以 receiver 的 uid 執行**（`native_acceptance_bridge.py:331,436`；`vrun/sandbox.py` HONEST_BOUND）
- 情境：依文件的分開帳號佈局（agent uid 擁有 /app、receiver home 0700、契約簽 `insecure_same_account:false`）跑預設 judge，主機或容器沒有可用的 bwrap／unshare ⇒ `none`。`python_checks` 以評測端 uid 匯入 agent 寫的 `solution.py`，能讀 receiver 的 owner 金鑰與隱藏測試（路徑可從工作區契約查到）、改寫帳本、寫 `<rh>/released`，或把祕密複製進工作區留給下一個 CONFORM 工作階段。`_boundary` 只查工作區的 owner uid，沒有任何東西拒絕不隔離的後端。
- 證據（兩個獨立重現）：bwrap 從 PATH 拿掉、預設 auto：agent 之後讀到 `.leak.json`＝`{euid:0, owner_key_readable:true, hidden_test_text:'…HIDDEN-MARKER-7f3a'}`，`<rh>/released/FORGED_BY_CANDIDATE` 被寫，outcome accept。同腳本明給 `--sandbox bwrap`：沒有洩漏，bwrap 缺失時 hold（rc 41，「量不到不是通過」）⇒ fail-closed 預設可行。judge 外層 JSON 的 `results[].evidence.sandbox` 有記後端，**簽章的 decision／ledger 沒有**（grep 帳本零個 sandbox／backend）。
- 意圖檢查：已文件化的非對抗工具——合約 `trust_boundary` 註記、`_python_checks` docstring「防意外，不防惡意」、HONEST_BOUND 說 `none`「不是沙箱」、README §8、PUBLIC_BENCH 明寫不可當敵對 agent 邊界——且需要敵意 agent＋沒有 bwrap 的主機；計畫中的 agent 不敵意 ⇒ 低。仍然真實的是：`_boundary` 與 BRIDGE_AUDIT 把「不同 OS 帳號」說成足夠，卻沒說 `auto→none` 時它不成立（BRIDGE_AUDIT `:63-66` 自己的環境就退到 `none`）。
- 修：契約 `insecure_same_account=false` 時，judge 在 `attempt_started` 前拒絕不隔離檔案的後端（預設改 `bwrap`，`none` 與解析成 `none` 的 `auto` 都拒）；解析後的後端與 honest_bound 簽進 decision；gate／conform 不寫工作區契約（洩漏 receiver 路徑）；改寫 `_boundary` 與 BRIDGE_AUDIT 措辭。

**F02 低 — 嘗試先被消耗、評測端的失敗才發生：judge 被殺、`--sandbox` 打錯、OSError、驅動啟不動都燒掉唯一的嘗試，且分別被記成 open／held／void／rejected**（`:357` `attempt_started` 在任何可能失敗的事之前；`:350-353` 期望次數＝`attempt_started` 的個數；`:436` `--sandbox` 沒有 choices）
- 情境：(a) judge 被 SIGKILL（逾時／OOM／容器殺）：帳本停在 `candidate_frozen`、state `open`、attempts 1，沒有 decision 也沒有 `infra_void`，之後任何 `--attempt` 都 `attempt must be 2 within 1..1`；沙箱子行程變孤兒、`/tmp/vacant-verify-*` 留著。(b) `--sandbox bwrapp` → UNKNOWN「sandbox unavailable」→ hold／exit 41，gate／repair 的唯一嘗試用掉，CONFORM 被告知要整個重開一個完整工作階段。(c) `flow` 內 OSError → `void:true`／exit 43，仍計一次。(d) 驅動啟不動（`python3` 找不到，見 F05）→ FAIL＝reject。已完成的 judge 也不能重跑取回裁決（要靠 `status`）；CONFORM 每個 void／hold 悄悄少一次，`status.attempts`(3) ≠ 實際工作階段數(2)。
- 證據：`vf_F02` a–e（killed→`open`、typo→`held`、ENOSPC 注入→`void`、驅動 rc=127→`rejected`、conform attempts=3 時 void 後以 attempt 3 通過）；我另外重跑 M1b／M1c（模擬 verify 失敗與 `RuntimeError`）：重試都 `attempt must be 2 within 1..1`。
- 意圖檢查：hold／void 本身是刻意的（`unknown_policy=hold`；README §7 把 reject／HOLD／infra void 分開記）；損失不安靜（`open` 仍在分母）且只往不利於 bridge 臂的方向偏；「約 9 格／1 pp」的估計沒有量過。缺的是 judge 內重試與文件（BRIDGE_AUDIT 的「嘗試受上限約束」沒寫「被殺、打錯 `--sandbox` 也算一次」）。
- 修：`--sandbox` 加 choices，並在 `attempt_started` 前探測 `make_sandbox`；`attempt_started` 延到凍結成功後，或讓 `judge --attempt N` 在 N 沒有 decision 之前可重複；驗證環境的 UNKNOWN、例外、被殺一律寫 `infra_void`、不計次、同一個結束碼；`status` 另列 `judge_calls` 與 `sessions_run`；文件寫明「judge 被殺 ⇒ 整格重跑」。

**F03 低 — 工作區契約漂移被記成 `infra_void` 並燒掉嘗試，但 judge 回報 `hold`／`void:false`／exit 41；`git clean -fd` 就能觸發**（`:359-363`；`:54` `EXIT`；`tests/test_native_acceptance_bridge.py:146-157` 斷言 `attempts==1`）
- 情境：agent 或清理步驟刪掉／改掉 `.vacant/contract.json`（同 uid 的 `git clean -fd`、`mv .vacant`、`find … -delete`，`hookpolicy.decide_pre_tool` 都放行；`rm -rf .vacant` 才會被擋）。judge 寫了 `attempt_started` 才發現漂移，記 `infra_void(stage=contract_drift)`，卻回 `hold`、`void:false`、exit 41；ledger／status 說 `state=void`、`decisions=0`——取決於分析看結束碼還是帳本，那格落在不同桶；agent 造成的漂移被標成基礎設施失敗（慣例上可被排除的標籤）。gate／repair 下次 judge `attempt must be 2 within 1..1`，即使契約已還原；release 拒絕。漂移的回傳缺 `run_id`／`attempt`／`contract_sha256`。分開帳號佈局下 agent 擁有 /app，仍可 `mv .vacant`（批判者 R3：hold、`state void`、attempts 1）。
- 證據：`vf_F03` 的 `git clean -fd`（連 `solution.py`、`tests_visible/` 一起移除）、counterfactual（關掉漂移檢查：accept、attempt 1、contract_sha256 在、`status accepted`）；我重跑 `run_h1` c／d：刪契約→hold，還原後→accept。
- 意圖檢查：hold 是刻意且有文件（BRIDGE_AUDIT「工作區副本不同時 judge HOLD」；測試 `test_tampered_workspace_contract_holds_before_acceptance` 刻意斷言）；沒有安全影響（決定本來就只看收件端合約）；`git clean -fd` 也會刪掉未追蹤的 `solution.py`，只有「已追蹤的 stub」才會真的丟掉正確解；「依 arm 選擇性排除」弱——帳本把 void 與未決留在分母（`ledger.py`），而且偏差只不利於 Vacant 臂。真正的缺陷是標籤與結束碼不一致、少欄位。
- 修：judge 一律以收件端合約為準、把漂移當觀察寫進 decision 的 notes、**不消耗嘗試**；若要硬停，用專用事件，讓帳本、JSON、結束碼三者一致（`void:true`／43 才對應 `infra_void`），並補欄位；`decide_pre_tool` 補擋 `git clean`／`git stash -u`／`mv .vacant`／`find … -delete`，或 prepare 時把 `.vacant` 加進 `.git/info/exclude`。

**F04 低 — prepare 放行 `run_suite` 永遠跑不過的套件（資料檔、輔助子目錄、`main()` 結尾 `sys.exit`、帶參數的 `check_*`）；正確解被 reject，repair 下 agent 被送回去修一個修不了的失敗**（`:116-126` `_suite_files`；`vrun/acceptance.py` `run_suite` 只送最上層 `*.py`，而 `contract.path_sha256` 釘整棵樹）
- 情境與證據：`run_m2`／`rep.py`（正確解、sandbox none／bwrap）：套件旁的 `cases.json`、`data/cases.json`、輔助套件 `support/__init__.py`、`main()` 以 `sys.exit(0)` 結束、`unittest.main()`、`check_eq(a,b)`、cwd 相對路徑資料檔 → prepare OK、judge reject（FileNotFoundError／ModuleNotFoundError／SystemExit／TypeError）；對照：純 `check_*`、同層 `_support.py`、`deliverable='*.py'` 都 accept。prepare 從未真正跑過一次套件。repair 下 `decide_stop` 連三輪送回同一個錯誤。我重跑資料檔與巢狀資料檔兩種：reject（FileNotFoundError）。
- 意圖檢查：套件格式是有文件的（`ops/gain/r530/TASK_FORMAT.md` §四-五：最上層 `test_*.py`、無參數 `check_*()`／`main()`、輔助只有同層非 `test_` 檔），bridge 沒宣稱擴大格式；失敗是 fail-closed 且訊息具名；repo 內 170 個 `tests_visible` 目錄（r530／r534／r535）沒有一個含子目錄、非 `.py` 檔、帶參數 `check_*`、`sys.exit`、`unittest.main`，所以計畫中的批次不受影響——且第一次冒煙就會暴露。agent 端「看到通過」只在 L1／L2／L5／L10 成立（repo 自己的 `run_tests.sh` 下 L9 也會在 agent 端失敗）。反方向也有落差：文件承認的 `_support.py` 在 `run_tests.sh` 下 `ModuleNotFoundError`，在 judge 卻通過。
- 修：`_suite_files`／`_snapshot_suite` 拒絕 `run_suite` 不會送的東西（非最上層 `*.py`、資料檔、子目錄，只放過空的 `__pycache__`），或讓 `run_suite` 送整個釘住的目錄；加一個可選 `--reference <dir>` 預檢（沿用 `suitegauge.probe_instrument`）要求 PASS，並以空候選預檢，只准以斷言類錯誤失敗；拒絕帶參數的頂層 `check_*`。

**F05 低 — 驗證器基礎設施失敗（沙箱寫死的 PATH 找不到 `python3`、只在 user-site 的依賴、記憶體上限）被判 FAIL，正確解得到簽章的 reject，repair 下得到誤導的退回**（`vacant_network/intake/verifiers.py:567-571`；這份差異沒碰它）
- 情境：`python_checks` 只把 `empty_reason` 映成 UNKNOWN，驅動 `driver_error`／`incomplete`（rc 127／126）一律落到 `return "FAIL"`。沙箱 PATH 寫死 `/usr/local/sbin:…:/bin`、丟掉 `PYTHONPATH`、hermetic 設 `PYTHONNOUSERSITE=1`；task 映像的 `python3` 或依賴在別處（venv／pyenv／conda／`pip --user`）⇒ 正確解 reject（耗掉唯一嘗試、`state rejected`），repair 的 `decide_stop` 回「驅動啟不動（rc=127）」給 agent。
- 證據：`vf_F05` NS-S1（私有 mount ns 把 `python3` 從 PATH 拿掉，沒有 patch）：`reject … driver_error … rc=127 … python3: command not found`；`flow.check`＋`decide_stop(repair)`＝`continue` 帶同一段文字；S2（依賴只在 `~/.local`）ImportError；S3 600 MiB 配置 MemoryError。我自己重跑 `run_m3` M4 也得 `reject FAIL … rc=127`。
- 意圖檢查：核心成立且**不是**刻意的（`verifiers.py` 檔頭 FAIL＝成品的問題、UNKNOWN＝驗證器壞了；上一輪審查已點名，修正分支只做了格式那一半，`BRIDGE_AUDIT` 沒提，`test_probe_infra.py` 仍斷言 `reject`）。但沒有安全影響（FAIL 與 UNKNOWN 都 fail-closed）、失敗大聲且系統性（首格冒煙就看到）、計畫中的任務只用標準庫；記憶體上限（512 MiB）與 hermetic user-site 是刻意（`sandbox.py`）。建議的「模組層 ImportError→UNKNOWN」會把模型幻想的 import 變成 hold、去掉可行動的回饋，**不要採**。
- 修：只做窄的那一半——所有非通過記錄都是檔案層級 `driver_error` 且 rc ∈ {126,127,97} ⇒ UNKNOWN；prepare 加 `python3 -c pass` 的沙箱內預檢。

**F06 低 — R534 重算文件說 940 格封存和 C5 是不同批次；它們是同一份封存（920 格正式 c5＋20 格未預註冊的校準），表格把兩者混加**（`BRIDGE_AUDIT_FIX_R534_REPLAY.md:46-58,63-66`）
- 情境：L58「R534 與先前 C5 的 920 題統計是不同批次，不能混加」不成立。43 個分包是同一批：chunk 1–4＝`calib1`（吞吐校準，Colab RUNLOG 宣告「不是預註冊批次、不看分數」，用凍結前的舊評分器），chunk 6–42＝正式 c5。表格每臂 940 格、hidden 762／773、wrong-release 90／88、refused 45／41、配對 711／116／62／51 全是混加；C5 README 的基準是 748／758。讀者會把 940 當額外證據、用 762／773 當 C5 基準、混用兩版評分器。L63-64 說 `ops/gain/r534/templates/` 保留題庫樣板，但那個目錄**恰好**是 20 題校準集，920 題正式批次一題都不在，所以「用樣板做 bridge 對 visible_pass 的零成本一致性檢查」只涵蓋約 2% 的格。
- 證據：我重跑 `replay_r534_gate_scores.py`（MANIFEST 全部 sha256 吻合）得文件表格；再以 cell 名稱前綴切開：c5／A 920 格 hidden 748、visible 837、有檔 878、有檔卻錯 130、放行錯 89、拒 41；c5／C361 920、758、846、886、128、88、40；c5 配對 699／113／59／49，精確 McNemar p＝0.3866（＝C5 README）；calib1／A 20 格 hidden 14、C361 15；合併 p＝0.347。40 個 calib 格的 `score.json` 沒有 `suite_timeout_s`／`timed_out`／`n_visible_files`，1,764 個 c5 格有。templates 20 題＝calib 20 題（我核對 id 相同），其 id 在 c5 的 LCB 格出現 35 次但 `test_visible.py` 的雜湊不同。
- 修：L58 改寫成「43 個分包是同一份封存：1–4 校準、6–42 正式」；表格只給 c5（748／758、878／886、89／88、41／40、配對 699／113／59／49），calib1 另列並註明舊評分器；`replay_r534_gate_scores.py` 加 `--campaign` 或分批次輸出；樣板那一句限縮到 20 題校準集。

**F07† 低 — CONFORM 依賴 `/app/.vacant/contract.json` 在工作階段之間存活；每個工作階段換一個全新 /app 時，第 2…N 次嘗試全部變成漂移 hold 並燒光次數**（`:31-33` docstring「外層要啟動全新的完整工作階段」；`:359-363`；`:255-256`）
- 情境：「fresh full native session」最自然的做法是從映像重開一個乾淨的 /app（只有 `tests_visible`、`goal.md`）。attempt 1 reject 之後重置工作區：再 prepare 被拒（`contract already exists`），而 attempts 2–5 對**正確**候選全部 `hold`／41，`status`＝`void`、attempts 5、void 4、decisions 1；第 6 次 `attempt must be 6 within 1..5`。CONFORM 臂實質上退化成「只有第一次」，而每一格都大聲 hold。文件沒有說 `.vacant` 必須保留。另：docstring `:21-29`、README `:148-160` 的 receiver home 用 `$TASK`，BRIDGE_AUDIT `:26,29,33` 用 `$RUN`；四臂設計共用 `$TASK` 時第二臂 `contract already exists`（大聲、fail-closed）。
- 證據（我重跑）：`vf_F07` E1（重置後 attempts 2–5 全 hold）、E1b（把 receiver 的 `contract.json` 複製回 `/app/.vacant` 之後 attempt 2 accept——未寫入文件的變通）、E2（保留 /app 時正常）、E3（三種模式下 agent 可見的檔案與契約欄位）、E4（`$TASK` 衝突；`<home>-suite` 殘留時也拒）。
- 修：根因同 F03——judge 不依賴工作區副本；或提供 `bridge restore-contract`／`judge` 自動從收件端還原再比對；文件明寫「每個 session 要保留或還原 `.vacant`」，統一用 `$RUN`。

**F08† 低 — receiver home 路徑含工作區內的 symlink 時，prepare 通過，之後 agent 可把它改指到自己的偽造 home**（`:249` prepare 時 `receiver_home.resolve()`；`:81,309,312` 之後每個指令都重新解析同一個字串）
- 情境：評測端傳入 `--receiver-home $W/rlink/vacant`（`rlink`→評測端擁有的 0755 目錄），prepare 以真實路徑通過 `_boundary`。agent（uid 1002）之後把 `rlink` 重指到自己擁有的目錄、在裡面 prepare 一個偽造的 home（自己的套件）；judge／release 用同一個字串 ⇒ 錯的解 accept、released、`readback_ok:true`，發布在 agent 擁有的目錄。祖先目錄由評測端擁有（0755／0700）時 agent 搬不動（`T3`→`T3.evaluator_orig` Permission denied），沒有這個洞。
- 證據（我重跑，私有 bed，agent＝uid 1002、評測端＝root）：ancestor 755／700 皆安全；symlink 變體 accept＋released。
- 意圖檢查：需要評測端把路徑穿過 agent 可控的 symlink，文件沒有任何地方這樣建議（邏輯維度也判為牽強）⇒ 低。
- 修：prepare 把解析後的 receiver home 寫進簽章契約 notes，`_task` 要求 `receiver_home.resolve()` 等於記錄值；非 insecure 時拒絕任一路徑成分是 symlink（`realpath != abspath`）。

**F09† 低 — `release` 的結束碼和正規的 `vacant release` 不一致：infra_void 與「發到一半」都回 44（拒絕）**（`:479`；`:54-55` `EXIT` 沒有 `release_unconfirmed`）
- 情境：正規 `cmd_release` 把 void 映成 43、`release_unconfirmed` 映成 45。bridge 一律 44：目的地父目錄是檔案（`flow` 記 `infra_void`，`status` 變 `void`、重試於預設目的地成功）、或發布到一半 ENOSPC（目的地留下 `solution.py` 內容 `partial`、`effect:"unknown"`、`state release_unconfirmed`）都被當成乾淨的拒絕。若評分讀目的地路徑而不看結束碼，半成品會被算成放行。
- 證據（我重跑）：`vf_F09` S1–S4（S2 錯 sha 與 S4 漂移＝44 正確；S1 void、S3 部分發布＝44，canonical 映射會是 43／45）。
- 修：重用 `intake.cli.EXIT` 的映射；README 列出結束碼表；評分只認 exit 0 且 `readback_ok`。

**F10† 低 — prepare 不是原子的：中途失敗留下殘餘，同一個 receiver home 或同一個工作區都不能重試；非 root 評測端還清不掉唯讀的套件副本**（`:261-285`：mkdir home → 父目錄檢查 → `_snapshot_suite`（0555／0444）→ 可讀檢查 → `build_contract`／目的地檢查 → 寫兩份契約 → `flow.lock`）
- 情境：`:266` 之後失敗（可讀檢查、`--destination` 越界、`--attempts 11`）留下 `<rh>-suite`，同一個 home 重試＝`receiver suite already exists`；`:280` 之後失敗（`flow.lock` 例外）留下 `rh/contract.json` 與 `/app/.vacant/contract.json`，任何新的 receiver home＋同一工作區＝`contract already exists`。評測端若不是 root，`rm -rf` 唯讀的 `-suite` 失敗（要先 `chmod -R u+w`）；`finally: shutil.rmtree(temp)` 在非 root 的模擬重新命名失敗下也失敗，留下 `*.tmp-*`。全部 fail-closed 且訊息具名，但每次失敗都要人工清。
- 證據（我重跑）：`vf_F10` t1（`--attempts 11`、`--destination` 越界後同 home 重試）、t3（`rh/intake` 是檔案：殘餘 `app/.vacant`、`rh/contract.json`，修好原因後同 home／新 home 皆拒）、t3b（模擬 ENOSPC）、t2／t4（私有 mount ns，評測端＝nobody，`rm -rf` 失敗）。
- 修：prepare 先做所有驗證（attempts、目的地、可讀、父目錄）再落地；整個函式包 try，失敗時 `chmod -R u+w` 後回收 `<rh>-suite` 與兩份契約；文件寫「失敗 ⇒ 換新 receiver home 與乾淨工作區」。

**F11† 低 — 工作區契約是惡意或損壞的 JSON（深度巢狀）時，`_workspace_contract_drift` 拋 `RecursionError`：judge／status／release 都崩潰（rc 1，帶 traceback），且 judge 已寫了 `attempt_started`**（`:324-327` 只接 `OSError`／`ContractError`；呼叫端 `:359,382,399`；`:483` `main` 只接 `OSError`／`ValueError`／`ContractError`）
- 情境：agent（工作區是不受信輸入）把 `.vacant/contract.json` 換成 20 萬個 `[`：judge rc 1、`RecursionError`、帳本 `…attempt_started`（無 decision、無 void）；`status`、`release` 也 rc 1；重試 `attempt must be 2 within 1..1`。結束碼 1 不在 `EXIT` 表裡。對照組（`{`、空檔、`[]`、`null` 等）都正確回 drift。同類：帳本被截短 ⇒ 所有指令 `LedgerError` traceback（設計：「inspect or move」）；收件端契約缺 `notes` 時 `status` `KeyError`（非 bridge 產生的契約，不實際）。
- 證據（我重跑）：`vf_F11` c_variants（200000 層陣列、10 萬層物件、5000 層平衡陣列皆 RecursionError；900 層通過）、b_hostile／b2_control（分開 uid）、a_ledger、d_keyerror。
- 修：drift 檢查用 `except Exception`（任何無法解析＝漂移）；`main` 對未預期例外回固定結束碼（建議 43）並寫 `infra_void`；與 F02 一起讓嘗試不因此消耗。

**F12† 低 — bridge 用 `raw["claims"] = [...]` 蓋掉 scaffold 的兩條安全底線（`deliverable_present`、`no_secrets_shipped`）**（`:206-215`；scaffold 見 `vacant_network/intake/contract.py:753-775`）
- 情境：套件不碰交付物時，沒有 `solution.py` 也 accept 並 release 一個空成品（`n_files:0`，目的地只有 `.vacant-release.json`）；交付物用萬用字元時，`.env`、`id_rsa` 也被接受並發布到目的地。真實的套件會 `import solution`（對照 B：reject），預設交付物是 `solution.py`，所以只在退化套件或萬用字元交付物時成立。
- 證據（我重跑）：`vf_F12` A（無 solution.py、套件不碰它 → accept、release `{released:True}`）、B reject、C（0 位元組 solution.py）reject；`ctrl.py`：把 scaffold 兩條 claims 接在 `python_checks` 前面 → 空成品 reject（`deliverable_present` FAIL）、祕密 reject（`no_secrets_shipped` FAIL）。
- 修：保留 scaffold claims，在後面加 `python_checks`。

**F13† 低 — `--destination` 的說明文字與行為相反；`--replace` 永遠報錯**（`:428-429`；`:111-112`；`:251-252`）
- 情境：help 寫「evaluator-owned dir: path outside workspace」，程式要求目的地在 receiver home **之內**（`release destination must be inside receiver home`，越界與相對路徑都拒）；`--replace` 被接受卻立刻 `a run cannot be replaced`。而且目的地檢查發生在套件已快照之後（F10 的殘餘）。README／docstring 沒寫 `--destination`。
- 證據（我重跑）：`vf_F13` A（依 help 的評測端輸出目錄 → rc 2，`rh`、`rh-suite` 殘留）、B、C／C2（`--replace`）、D（`rh/out` 通過）、E。
- 修：改 help 與 docstring；移除或實作 `--replace`；目的地驗證放進 prepare 的前段。

**F14† 低 — `notes.agent_visible_suite_sha256` 在 `--suite` 給定時其實是 receiver 副本的雜湊；agent 看到的 `/app/tests_visible` 和 receiver 的副本從不比對**（`:277`；上一輪 M10 仍開著）
- 情境：README §5 的建議佈局（receiver 另有一份 `tests_visible`、`--suite` 指向它）正好是分歧情形：欄位＝釘住的 receiver 副本雜湊（`5ed6b0173a3d`），agent 的真實 `/app/tests_visible` 是 `4394a5944cfb`；欄位名暗示有量到 agent 看到的東西，輸出與 notes 沒有任何 diverge／mismatch 標記。預設（沒給 `--suite`）與兩份相同時欄位才正確。
- 證據（我重跑）：`vf_F14` A／B／C（`note==agent_real` 為 False／True／True）；`run_m3` M10 結果相同。
- 修：記兩個欄位——`agent_visible_suite_sha256`（真的雜湊 `/app/tests_visible`）與 `pinned_suite_sha256`——不同時 `prepare` 輸出 `suite_diverges:true`；預註冊分歧是設計還是事故。

**F15† 低 — `status.destination_live` 讀的是帳本記下的 release 讀回，不是現在的目的地**（`:394-400`；`vacant_network/intake/flow.py:423-435` `status` → `state_of`）
- 情境：放行後目的地的 `solution.py` 被改寫或刪除，`status` 仍回 `state=released`、`destination_live.readback_ok=True`、accepted sha。再 release 一次才會得到 `already_published`、`readback_ok:false`、`content at destination differs`／`missing at destination`，`state` 變 `release_unconfirmed`。
- 證據（我重跑）：`vf_F15` 覆寫與刪除兩種；欄位裡沒有 live／checked_at 之類的欄。
- 影響：評分若讀發布路徑（而不是 `status`）不受影響；目的地在 receiver home 內，分開帳號下 agent 碰不到 ⇒ 低。
- 修：`status` 重新讀回並回報現況（或把欄位更名為 `destination_at_release`）。

**F16† 低 — 同帳號繞過重現腳本把結果寫死，沒有負控制，還把 `VACANT_HOME` 塞進攻擊者環境**（`ops/eval/evidence_20260928_pi_plugin/reproduce_same_account_bypass.py:44,55,69-70`）
- 情境：最後一行印出寫死的 `'incorrect_add_2_3':0`，並非量到的；改成回傳 99 的解，輸出仍是 0；腳本內沒有「攻擊前 judge 必須 reject」的負控制；`attack.py` 靠 `os.environ["VACANT_HOME"]` 找 receiver，而評測端從沒把它交給 agent（agent 要從工作區契約自己找路徑——可行，因為契約洩漏 receiver 與套件路徑，但那是另一個前提）。
- 證據（我重跑）：原腳本輸出 `pre_tool:allow、judge:accept、released:True、readback_ok:True、incorrect_add_2_3:0`；改成 `return 99` 的 `mut.py` 輸出仍是 `incorrect_add_2_3:0`；control（未攻擊的錯誤解）judge＝reject、`add(2,3)=0`；工作區契約洩漏 `receiver-suite`、`released`、`bridge_workspace` 路徑。
- 修：實際執行已發布的 `solution.py` 算 `incorrect_add_2_3`；腳本內先 judge 一次要求 reject；從工作區契約推導 receiver 路徑，不注入環境變數。

**F17† 低 — 同一個候選在 `sandbox=none` accept、在 bwrap／auto reject；後端不在簽章的 decision 裡；repair 掛鉤與 judge 可能用不同後端**（`:331,364`；`adapters/hook.py:399` `flow.check` 用預設 `sandbox=auto`）
- 情境：候選用絕對路徑讀工作區裡不在交付物內的檔案（`/app/input.txt`）：`none` 下讀得到＝accept；bwrap 下 `FileNotFoundError`＝reject。簽章的 decision 的 compact results 只有 `authority／detail／id／required／status／verifier／version`，沒有後端；judge 外層 JSON 有。評測環境的後端不同（作者環境退到 `none`，別處是 bwrap）⇒ 跨環境不可比；repair 的回饋與權威 judge 可能判相反。
- 證據（我重跑）：`vf_F17`（none accept／bwrap reject／auto reject；decision 與 `decision_doc` 欄位不含後端；`flow.check` 預設 reject、`judge(none)` accept）。
- 修：把後端簽進 decision；契約 notes 記 `verifier_sandbox`，掛鉤與 judge 共用；與 F01 一起處理。

**F19† 低 — 「是否同帳號」只看工作區 owner uid 與評測端 euid 是否相等，簽進契約的 `insecure_same_account:false` 並不代表量到過**（`:99`）
- 情境：工作區 owner 是別的 uid（65534），但 agent 實際以評測端 uid（0）執行：prepare 不加 `--insecure-same-account` 就過，契約簽 `insecure_same_account:false`；agent 之後改套件、去掉 pin、重簽鎖、改寫工作區契約，judge accept、released，發布 `def add(a,b): return 0`。反向（root 擁有工作區、agent 真的以 65534 跑，agent 讀不到 0700 的 receiver home）被 prepare **誤拒**。
- 證據（我重跑，需 `PYTHONPATH=<checkout>`）：`vf_F19` 案例 A／B 與對照（工作區 uid＝euid 時拒絕）。
- 意圖檢查：`_boundary` 註解把「工作區 owner 當作預設 agent 身分」；沒有文件說這是保證。標籤卻是簽進契約的。
- 修：要求 `--agent-uid`（非 insecure 時必填）並簽進契約；prepare 以那個 uid 做探針（嘗試讀 receiver home 失敗才算分開）並記錄；把簽進契約的欄位改名為「未驗證的聲明」直到有探針。

**F20† 低 — 掛鉤的 pre-tool 保護只涵蓋 agent 自己的 `VACANT_HOME`、工作區契約與釘住的套件，不含分開的 receiver home；最近的契約會遮住 bridge 契約**（`adapters/hookpolicy.py:121` `_protected`、`:762` `decide_pre_tool`；`adapters/hook.py:366`、`intake/contract.py:346` `find`；bridge `:196-198` 沒設 `effects.protect_paths`）
- 情境：(a) agent 的 `VACANT_HOME` 與 receiver home 分開（文件佈局）時，對 `<rh>/contract.json`、`trust.json`、ledger 的寫入與 `cat` 金鑰全部 `allow`；`protect_paths=[receiver_home]` 能擋寫但擋不了讀金鑰。同 uid 下這等於 R10（已知、文件有寫），分開帳號下由 OS 權限擋。(b) Stop 掛鉤從 `cwd` 往上找最近的契約：`sub/vacant.contract.json` 遮住 `/app/.vacant/contract.json`，repair 回饋評估的是另一份契約；bridge 的漂移檢查只看 `/app/.vacant/contract.json`，對這個盲。
- 證據（我重跑）：`vf_F20` a_pretool（三種設定下的 allow／deny 矩陣）、b_nearest（`sub` 底下 `deliverable_present`、`status workspace_contract_matches_receiver: True`）。
- 意圖檢查：pre-tool 是字串層級的軟護欄；同 uid 繞過已有文件與重現；(b) 只在 agent 把 session cwd 放進子目錄時成立。
- 修：bridge 在契約的 `effects.protect_paths` 加入 receiver home 與 `-suite`；Stop 掛鉤對 bridge 契約用 `bridge_workspace` 而不是 `find(cwd)`。

**F21† 低 — 測試名稱與斷言相反，真正的漂移路徑沒有測**（`tests/test_native_acceptance_bridge.py:111-120`）
- 情境：`test_suite_drift_after_prepare_becomes_hold_not_pass` 實際改的是 agent 的 `/app/tests_visible` 副本，並斷言 `reject`／`FAIL`（套件改放 receiver 後這是對的，名稱沒跟上）；釘住的 receiver 套件被改 ⇒ `UNKNOWN … changed since it was pinned`→hold 這條路徑沒有任何測試（M29 存活）。同時：repair 的 Stop 掛鉤在釘住套件漂移後悄悄 allow（UNKNOWN 不可行動）。
- 證據（我重跑）：`vf_F21` A／B／C 與 `hook_and_gaps` #1。
- 修：改名為 `agent_copy_edit_does_not_change_receiver_suite`，另補 receiver 套件漂移→hold 的測試。

## 補驗項目（W 系列，無代理編號，我從 scratch 補驗）

**W2† 低 — 驗證子行程繼承評測端的 stdin**（`vrun/sandbox.py` 沒有 stdin 處理；`native_acceptance_bridge.py:364` `flow.submit`）：候選碼（或它匯入的東西）讀 stdin 會吃掉評測端 pipe 的內容——`printf 'TASK_B\nTASK_C\n' | judge`（候選 `sys.stdin.read()`）後評測端剩餘 stdin 為空（`none` 與 bwrap 皆然，我重跑）；`while read task; do judge …; done` 型的批次迴圈會吃掉後面的 task；stdin 是開著不關的 pipe 時，讀 stdin 的候選會逾時 reject。修：`main()` 開頭把 fd 0 導向 `/dev/null`（不要改 vrun 舊行為）。

**W3† 低 — 以腳本執行時 `vacant_network` 從哪裡匯入取決於環境，且契約／決定不記程式版本**（`:49-52`；docstring `:20-29` 的指令沒有 `PYTHONPATH`）：`python ops/eval/native_acceptance_bridge.py …` 只把 `ops/eval` 放進 `sys.path`；沒裝時 `ModuleNotFoundError`，有 editable install 時**悄悄**匯入另一份 checkout（我實測：從修正分支跑這支腳本，解析到 `/home/user/Vacant/vacant_network`）。決定記了 `python_checks` 的版本，沒記整份程式的 commit。修：腳本以 `__file__` 推出 repo 根並放到 `sys.path` 最前，或斷言匯入位置；契約 notes 記 `vacant_network` 的 commit／樹雜湊。

**W4† 低 — 雙臂冒煙文件標 mode `repair`，其實沒有載入 Pi 掛鉤**（`PI_*_PAIR_SMOKE_20260928.md:9`）：文件寫「Mode `repair`，一輪回饋預定於拒絕時」，這次用的是外部 `prepare→judge→release` 工具，沒有 Pi 擴充（這點只在 `PI_PLUGIN_PUBLIC_BENCH_20260928.md:5` 自揭）；結果 JSON 沒有任何 hook／feedback／mode 欄位（grep 零個）。文件也寫了「沒有任何任務走到 repair、不能量測機制」，所以數字誠實，標籤誤導。修：冒煙文件內把 mode 改成 gate 等價、註明「未載入 Pi 掛鉤」。

**W5† 低 — 死碼與重複守衛（簡化維度）**：`_task_id` 結尾的 `re.fullmatch` 分支 30 萬筆模糊測試從未觸發（前面已正規化）；`prepare` 的 `root is not None` 永遠為真（`_receiver_root` 不回 None）；attempts 範圍與 id 規則 `C.parse` 已檢查一次。不影響行為，W1 裡 M28／M30／M35 這幾個存活變異體多半落在這類冗餘守衛上。

## 我先前 13 條的現況

13＝H1–H3＋10 條中低（把原文「套件格式錯／基礎設施錯」與「預設套件在工作區」各拆成兩條：M3／M4、M5／M6）。

| # | 先前的問題 | 現況 | 依據 |
|---|---|---|---|
| H1 | judge 讀 agent 可寫的合約、從不對照鎖 | **已修** | judge／release／status 只讀 `<rh>/contract.json`，`_task` 驗 `check_lock`，工作區副本差一個位元組就 hold；換驗證器／刪契約→hold(41)、release 拒絕、還原後 accept（`run_h1` a–f，我重跑）。副作用：F03／F07／F11 |
| H2 | `--receiver-home` 沒檢查，agent 可重簽鎖並放行 | **部分** | 必填；在工作區內、包住工作區、symlink 進工作區、同帳號都拒；`--insecure-same-account` 要明寫且簽進契約；金鑰從交付物排除（`run_h2`）。殘餘：同帳號繞過仍成立（已文件化、有重現腳本；`run_h2` H2b 仍 accept＋released）、uid 啟發式 F19、symlink 路徑 F08、契約洩漏 receiver 路徑 F01／F16、掛鉤不護 receiver home F20 |
| H3 | release 放行的是帳本裡最新接受的，不是剛 judge 的 | **已修** | `--artifact` 必填且須等於最新 decision；每 run 新 receiver home＋`bridge_run_id`；prepare 拒覆蓋；`run_h3` a–c（跨 run 的 sha 被拒、釋出後再改工作區不影響發布）。但沒有測試守住（W1：M08） |
| M1 | 嘗試次數沒被執行也沒被記 | **已修（有新缺陷）** | 遞增、有上限、接受後不再判、flock 序列化（`run_m1`）。新缺陷：失敗也計次——F02／F03／F11 |
| M2 | 巢狀測試被釘住卻不跑 | **已修（有殘餘）** | 巢狀 `test_*.py` 在 prepare 拒絕；資料檔、輔助套件仍會過 prepare 卻不被送去跑：F04 |
| M3 | 套件格式錯被當 FAIL | **已修** | prepare 拒絕沒有頂層 `check_*`／`main` 的檔（pytest 風格、純斷言、`__main__` 型皆拒）；殘餘 F04 |
| M4 | 基礎設施錯被當 FAIL | **未修** | 找不到 `python3` → reject(FAIL)；`verifiers.py` 沒動；`test_probe_infra.py` 仍斷言 reject：F05 |
| M5 | 預設套件在工作區，agent 加測試檔 ⇒ 每次 HOLD | **已修** | 套件複製到 `<rh>-suite`、釘那一份；agent 加／改／清空 `/app/tests_visible` 不影響（`run_m2` M5：accept；agent 掏空自己的副本＋錯的解：reject） |
| M6 | 換檔競態讓錯的解通過（40 次 9 次） | **已修（預設佈局）** | 翻動 `/app/tests_visible` 時 10 次 judge 錯的解 10 次 reject；同 uid 改 receiver 副本→hold（偵測、不是預防）；分開帳號由 uid 擋 |
| M7 | 放行目的地在工作區 | **已修** | 目的地必須在 receiver home 內，`dir:.vacant/native-release` 與越界都拒；symlink 轉向被正規化；殘餘 F15 |
| M8 | `python_checks` 可被候選偽造 | **未修（措辭已改）** | `trust_boundary` 改成「不是對抗性驗證器」；偽造在 bwrap 下仍 accept＋released（`run_m3` M8，`backend=bwrap`）；沒有行程外 verifier／SuiteSpec；已文件化 |
| M9 | REPAIR 靜默變成 GATE | **部分** | prepare 時查套件可讀；執行期的其他靜默 fail-open 仍在、沒有操弄檢查：F18 |
| M10 | agent 看得到的套件與 receiver 副本從不比對 | **未修** | 新增的欄位名不副實：F14 |

文件與實驗設計的五條：

| # | 先前的問題 | 現況 | 依據 |
|---|---|---|---|
| R1 | README 把「`mode: evidence` 是主因」寫成事實，沒有上限表 | **未修** | README `:14-15` 仍寫成原因；BRIDGE_AUDIT `:60` 補了「GATE 的事後上限」，沒有 CONFORM／REPAIR 的上限 |
| R2 | v3.7 重播表與審查基準是審查前版本 | **未修** | README `:9` 基準仍是 `122a424c`、`:98-101` 寫 v3.7 continue 32／allow 1,295；同分支已提交的最終證據 `ops/eval/evidence_20260928_v37/replay/v37_c5_all.jsonl` 重算＝30／1,297（v3.6.1 472／855 相符，我重算） |
| R3 | 寫明 bridge 不是零設定 | **部分** | `PI_PLUGIN_PUBLIC_BENCH_20260928.md:22,25` 寫了；C5 README 與 BRIDGE_AUDIT 沒有 |
| R4 | 預算相同的 RETRY-NOSUITE 對照 | **部分** | BRIDGE_AUDIT `:72` 列為待做；README §7 四臂表（`:194-199`）沒有 |
| R5 | 檢定力、巢狀臂、不要拿巢狀臂對 NATIVE 做 McNemar | **未處理** | 兩份文件都沒提（文件層級，不擋批次）；主要指標 `released AND hidden_pass` 已寫（BRIDGE_AUDIT `:73`、README `:204`） |

## 查了什麼、沒有問題

- **核心路徑對**：receiver root 全部走 `<rh>/intake`（`HOME`／`VACANT_HOME` 指到空目錄時什麼都沒被建立）；`flow.lock／open_task／submit／release／status` 都拿收件端合約（含 pin）；鎖簽在 pin 之後的 sha 上；工作區副本與收件端副本逐位元相同。
- **嘗試次數（正常使用）**：遞增、有上限；CONFORM 必須給 `--attempt`；接受後重判被拒；並行的 judge 被 `bridge.lock` 序列化；帳本寫入原子。
- **釘住與放行**：改 `<rh>-suite` ⇒ hold（`input 'visible_suite' changed since it was pinned`）；agent 改 `/app/tests_visible` 不影響裁決；release 發布的就是 judge 凍結的位元組（放行後再改 `/app` 不影響，我重跑 H3b）；錯誤或縮寫的 sha 拒絕（44）；重複 release 冪等（`already_published`，帳本多一個 `released` 事件、`status.released` 列兩次——微瑕）；讀回成功；目的地越界與相對 `dir:` 一律拒。
- **模式接線**：`stop_check` 只在 repair 為真、非 repair 的 `max_feedback_rounds` 為 0、`submit_on_end` 恆為 false、預設次數 conform 5／其餘 1；掛鉤端 `flow.check` 對工作區契約的 FAIL／PASS 與 judge 一致（後端相同時，見 F17）。
- **分開帳號佈局端到端**（bwrap）：工作區 owner 為 nobody、`<rh>` 0700、`<rh>-suite` 0555，prepare／judge／release／status 通過，nobody 身分的 `flow.check` 讀得到釘住的套件並得到真實的 FAIL；`_readable_by_agent` 正確拒絕父目錄不可穿越；bwrap 下候選看不到 receiver 路徑與隱藏測試；agent uid 讀不到 owner 金鑰、寫不了 receiver home、搬不動祖先為評測端擁有的目錄。
- **套件相容性**：R534 `templates` 20／20 可 prepare，放入 placeholder 候選全部 reject（我重跑）；封存裡 1,631 個 visible-test `.pyc` 都引用 `check_*` 名稱，格式限制與 C5 套件相容；1,799 份封存解沒有一份匯入 numpy／pandas／scipy 等，單一交付檔與 512 MiB 上限對 C5 不構成問題；1,880 格裡 agent 改過 `tests_visible` 只有 1 格、沒有刪除原檔，agent 造成的契約漂移應該很少（約 ≤0.2%）。
- **掛鉤**：repair Stop 掛鉤走真的入口（`python -m vacant_network.adapters.hook claude Stop`）：失敗給 `block` 與失敗的斷言文字，修好後放行，3 輪後停；gate／conform 的契約 `stop_check=false` 不跑檢查；四個 agent 的 Stop 掛鉤時限 600 秒，大於預設套件時限 60 秒。
- **數字重算**：`replay_r534_gate_scores.py` 只讀 `score.json` 並用 `extractfile`（無路徑穿越），重現文件表格全部數字（見 F06 的拆分）；C5 README 的 748／758、+1.087 pp、p＝0.38657、缺檔 42／34 重算相符；冒煙文件的總計（216.09／250.06 秒、token 101,975／6,815 對 106,285／7,076）與 DABStep 七題數字重算相符。
- **安全面**：提交的文件與 JSON 沒有金鑰或 token；凍結成品不跟 symlink、跳過特殊檔；套件快照拒絕 symlink 與巢狀測試；pytest 風格與語法錯誤的套件在 prepare 就拒絕。
- **其他**：13 條 bridge 測試全綠（我重跑）；結束碼 0／40／41／43／44／2 如程式所寫，且不與 `vrun/gateshim` 的 20–26 衝突。

## 被撤回／沒列入的

驗證代理沒有退掉任何一條（`DROPPED＝[]`）；設計意圖檢查把多條下修到低。以下是各維度**明說不列**或我檢視後不列的，附理由：

| 項目 | 理由 |
|---|---|
| `python_checks` 被候選偽造（bwrap 下也成立） | 已文件化：`trust_boundary` 註記、docstring「防意外不防惡意」、README §8；只列在 M8 的現況 |
| 同 uid 繞過（改套件、重簽鎖、放行錯誤解） | `--insecure-same-account` 明示且簽進契約，重現腳本已入庫；分開帳號由 OS 擋。品質問題見 F16、覆蓋缺口見 F20 |
| `release --destination dir:<rh>/intake/keys/owner` 被接受 | 目的地由評測端提供，agent 碰不到 |
| `pinned_input` 雜湊與 `run_suite` 讀取之間的 TOCTOU | 只有套件目錄可被攻擊者寫（同 uid／`sandbox=none`）時成立，已文件化為非對抗 |
| `_readable_by_agent` 在 insecure 模式略過 | 刻意 |
| 種子清單「找不到 `python3` 被判 FAIL」 | 邏輯維度重現不了（剝 PATH 後仍 accept，因為沙箱把 PATH 寫死）；之後由 F05 真的拿掉 `python3` 重現，**保留為 F05** |
| 種子清單 PUBLIC_BENCH 的三點（首批 R534／DABStep 數字沒有原始資料、oracle 可被 agent 取用且有 8 次上限、`wrong release 0/7` 近乎由構造得出） | 文件首段與正文已自揭（原始 JSON 在回滾中遺失；oracle 是 agent 可取用的；「nearly makes zero wrong releases true by construction」）；結論用語已限縮（「tiny, partly selected」、不宣稱增益）。引用時不可當證據，但不是文件的錯誤 |
| 種子清單中屬於 `vacant loop`、possess pi 擴充、wave-2 harness、互動 TUI 指標的條目 | 不在 `fb32c622..6c2405de` 範圍內，這份沒有審 |
| `vacant check` 提示不在 PATH | 掛鉤刻意用 `sys.executable -m`，既有行為 |
| 簡化維度的結果 | 沒有進到我收到的資料；只有我補驗的 W5，其餘未列 |

## 建議處置順序

1. **F18**：prepare 的 agent 帳號 canary＋處理組送達紀錄；預註冊 REPAIR 的操弄檢查。（REPAIR 臂的前置條件）
2. **失敗不燒次數那一組（F02／F03／F05／F07／F11，順便 W2）**：judge 以收件端合約為準、infra 一律 `infra_void`＋不計次＋同一個結束碼、`--sandbox` 先驗證、驗證器基礎設施失敗 ⇒ UNKNOWN。
3. **F01／F17／F19／F08**：分開帳號佈局下拒絕不隔離的後端，後端與帳號探針結果簽進 decision。
4. **W1**：把 T3–T18 收進 repo，補需要第二個 uid 的分開帳號測試。
5. 文件：R1／R2／F06／F13／W4，並寫明 CONFORM 每個 session 要保留或還原 `.vacant`。
6. 其餘低項順手修；冒煙時請每臂回報 reject／hold／void 各幾格，以及 REPAIR 真的收到回饋的格數。

## 處置（2026-10-01）

**沒有 commit、沒有 push。** 這一節是程式修正與文件階段都做完之後的總表，每條一行。程式修正階段自己的紀錄
（逐條做了什麼、測試、變異檢查）原樣保留在後面的「程式修正階段的紀錄」；兩邊不一致時以這張總表為準
（那份紀錄的「沒有做」清單是**程式階段結束時**的狀態，F15／F16／W4／R1–R5 是文件階段補上的）。

### 做法，以及一份被丟掉的嘗試

- 之前有一份**範圍過大的修正嘗試**：bridge 長到 2,375 行、動到 `vacant_network/` 的核心檔，**沒有收斂**。那一份已**整份丟棄**，不在這個工作樹、不進 repo，
  只當參考留在評審 session 的暫存區；借用的只有幾句文件措辭與重現腳本的做法。它新增的子系統
  （例如讀 agent 掛鉤日誌的 `repair_feedback`、工作區 shadow-contract 掃描、`--expect-contract-sha256`、`--agent-uid`、`void_kind`）**一個都沒有再引入**。
- 現在的版本從人類的 `6c2405de` 重新開始，範圍寫死：`vacant_network/` 零改動（`git diff -- vacant_network` 為空）；bridge 489→794 行（上限 850；第二輪只加 docstring／契約註記的文字）；
  人類的設計全部保留（收件端合約 `<receiver_home>/contract.json`＋鎖檢查、flock 序列化、每個 run 一個新的 receiver home、`release --artifact`、既有結束碼）。
  可改的檔案只有 `ops/eval/native_acceptance_bridge.py`、`tests/test_native_acceptance_bridge.py`、`ops/eval/replay_r534_gate_scores.py`＋`tests/test_replay_r534_gate_scores.py`、
  `decisions/reviews/C5_NATIVE_ACCEPTANCE_20260928/*`、`ops/eval/evidence_20260928_pi_plugin/reproduce_same_account_bypass.py` 與本節。
  **清單以外的問題一律不修、只記錄**（見下面「後續項」）。

### 逐條處置

狀態：**已修**＝程式或證據腳本改了、有測試或重跑佐證；**已文件化**＝程式沒改，風險與做法寫進文件（README／BRIDGE_AUDIT／相關 md）；**延後**＝這次沒做，寫明原因。
一條可以同時有兩個狀態（例如「已修（一半）＋延後」）。

| 條 | 嚴重度 | 處置 | 改了什麼／為什麼延後 |
|---|---|---|---|
| F01 | 低 | 已修（一半）＋延後 | 沒有 `--insecure-same-account` 時，prepare 與 judge 都預檢並要求 bwrap，`none`／`unshare` 與解析成它們的 `auto` 都拒；後端記進契約 notes、`attempt_started`、judge 輸出。延後：把後端簽進 decision（要動核心 `flow._record_decision`）、gate／conform 不寫工作區契約（會改人類設計）。文件寫明 bwrap 不替 root 評測端降權（README §8）。 |
| F02 | 低 | 已修 | 用掉的嘗試＝裁決數，`--attempt` 必須是已有裁決＋1；`--sandbox` 加 choices；`attempt_started` 之前先做沙箱預檢，失敗＝`infra_void`＋exit 43＋不計次；例外與被殺的 judge 不計次；同編號 3 次失敗上限（exit 43）。 |
| F03 | 低 | 已修 | 工作區契約漂移只做位元組比對、只回報（`workspace_contract_matches_receiver`），不 HOLD、不 void、不拒絕、不耗次；舊測試依新語意改寫。 |
| F04 | 低 | 已修（一半）＋延後 | prepare 拒絕子目錄（`__pycache__` 除外）、非 `.py` 檔、symlink、帶必要參數的頂層 `check_*`。延後：`--reference` 預檢（用參考解實跑一次套件）。 |
| F05 | 低 | 已修（以預檢）＋延後 | `python3` 在驗證沙箱跑不起來＝preflight 失敗＝void／43、不計次。延後：`verifiers.py` 的 rc 126／127／97→UNKNOWN（核心，沒動）；預檢之後才出現的 rc=127（競態）仍是 FAIL。 |
| F06 | 低 | 已修 | `replay_r534_gate_scores.py` 預設分批次輸出（`--campaign`、`--merged`）＋5 條測試；BRIDGE_AUDIT 改成 c5 only、calib1 單列、940 合併表保留但重新標示「不要引用」、樣板句限縮到 20 題校準集；C5 README §2 補註。對真封存重算：c5 748／758、有檔 878／886、放行錯 89／88、擋 41／40、配對 699／113／59／49、p＝0.3866；calib1 14／15；合併 762／773（p＝0.347）與原表逐格相同。 |
| F07 | 低 | 已修（效果） | judge 不再依賴工作區契約，每個 session 換全新 /app 不再讓第 2…N 次變 hold；文件統一 `$TASK`（`--task-id`）與 `$RUN`（每個 run 一個新的 receiver home 與乾淨的工作區）。 |
| F08 | 低 | 已修 | prepare／judge／release／status 拒絕絕對路徑上任何一段是 symlink 的 receiver home。 |
| F09 | 低 | 已修 | release 結束碼與 `vacant release` 同表（0／43／44／45），測試釘 `EXIT == intake.cli.EXIT`；評分只認 exit 0 且 `readback_ok`（README §5.4）。 |
| F10 | 低 | 已修 | 所有驗證先於建立任何東西；之後失敗先 `chmod -R u+w` 再回收這次建立的父目錄、home、唯讀套件副本與兩份契約，並重新丟出例外；呼叫者原有的檔案不動。 |
| F11 | 低 | 已修 | 工作區契約不再被解析（位元組比對），20 萬層巢狀不崩；`main()` 對其他未預期例外一行 stderr＋exit 2，沒有 traceback。 |
| F12 | 低 | 已修 | 保留 scaffold 的 `deliverable_present`、`no_secrets_shipped`，`visible_acceptance` 以 append 加在後面。 |
| F13 | 低 | 已修 | `--destination` 的 help 與 docstring 改成實際規則（receiver home 內的 `dir:`）；移除 `--replace`。 |
| F14 | 低 | 已修＋已文件化 | 新 `--agent-suite`；notes 與輸出記真實雜湊 `agent_visible_suite_sha256`、`pinned_suite_sha256`、`agent_visible_suite_matches_pinned`，judge／status 重算；README §5.2 要求預註冊「分歧是設計還是事故」。 |
| F15 | 低 | 已文件化 | 程式沒改（`status` 仍回帳本裡 release 當下的讀回）；README §5.5 與 BRIDGE_AUDIT 寫明評分器**必須對已發布的檔案自己算 sha256**，不能讀 `status.destination_live`。 |
| F16 | 低 | 已修 | 重現腳本改寫：實際執行已發布的 `solution.py` 算 `incorrect_add_2_3`（改成回傳 99 的變異體會印 99）；腳本內負控制（同一份錯解不攻擊 → 必須 reject；把套件改寬鬆的變異體會讓這個斷言失敗）；receiver 路徑從工作區契約推導，不再把 `VACANT_HOME` 塞給攻擊者。在新 bridge 上重跑，仍示範已文件化的同帳號繞過。PUBLIC_BENCH 同步更正。 |
| F17 | 低 | 已修（一半）＋延後 | 解析後的後端寫進契約 notes／`attempt_started`／judge 輸出，並傳給 `flow.submit`（驗證與預檢同一個後端）。延後：簽進 decision、repair 掛鉤（`flow.check` 預設 `auto`）與 judge 共用後端（要動核心或掛鉤）。 |
| F18 | **中** | 已文件化＋延後 | 程式沒改：要做得靠 canary 或讀 agent 的掛鉤紀錄，兩者都在範圍外。README §6 寫明掛鉤失敗一律放行、處理組可能靜默退化成 GATE，並要求 REPAIR 臂預註冊操弄檢查（真的收到回饋的格數）。**這是跑 REPAIR 臂之前最大的未處理項。** |
| F19 | 低 | 已文件化＋延後 | 程式只多記 `evaluator_euid`；README §8 寫明那是工作區 owner uid 的啟發式、要讓 agent 以工作區 owner 的 uid 執行並記錄實際 uid。延後：`--agent-uid` 探針。 |
| F20 | 低 | 已修（一半）＋延後 | 契約 `effects.protect_paths`＝receiver home＋`-suite`（原生寫入工具被拒，shell 的**直接**寫法〔`>`、`tee`／`cp`／`mv`／`rm`／`sed -i`、帶 `open(` 的 `python -c`〕也被字串層級檢查拒；間接寫法與所有讀取不擋——2026-10-01 第二輪更正，原文寫「讀取與 shell 不擋」，不實）。延後 (b)：Stop 掛鉤取最近契約（要改掛鉤）。 |
| F21 | 低 | 已修 | 誤名的測試改為 `test_agent_copy_edit_does_not_change_receiver_suite`；新增「receiver 套件被改 ⇒ UNKNOWN ⇒ hold」。 |
| W1 | **中** | 已修 | bridge 測試 13→91 條；81 個一行變異體殺掉 80 個，存活的 1 個是訊息措辭（U10）、不是守衛；兩條 bwrap 測試的條件不同：分開 uid 端到端那條要 root＋`setpriv`＋可用的 bwrap，沒有就 skip；「bwrap 下候選碼看不到 receiver 檔案」那條**只要可用的 bwrap**（不需要 root、不需要 `setpriv`；2026-10-01 第二輪更正，原文把兩條都寫成要 root）。 |
| W2 | 低 | 已修 | judge 執行期間 fd 0 導向 `/dev/null`，結束後還原。 |
| W3 | 低 | 已修（一半）＋延後 | 腳本把 repo 根放到 `sys.path[0]` 才匯入 `vacant_network`；延後：契約 notes 記 `vacant_network` 的版本。 |
| W4 | 低 | 已文件化 | 雙臂冒煙文件開頭加更正（沒有載入 Pi 掛鉤＝gate 等價；結果 JSON 沒有 hook／mode 欄位）；PUBLIC_BENCH 同步；README §7 要求每格記錄掛鉤與 mode。 |
| W5 | 低 | 延後 | `prepare` 的 `root is not None` 死分支隨重寫消失；`_task_id` 結尾的 `re.fullmatch` 與重複的 attempts 範圍檢查還在（不影響行為）。 |
| R1 | 文件 | 已文件化 | C5 README「一句話結論」改成「還沒檢驗過的假說」並附 2026-10-01 更正；新增 §2.1 上限表（NATIVE 748 對／130 錯〔交出 878〕、GATE 748 不可能變多／89〔−41〕、CONFORM 上限 831〔+83、+9.0 pts〕至少 89 錯、63／83 可見沒過是撞時限、事後多一個工作階段 ≈ +38 對 +7 錯、REPAIR 上限 ≤ +20＝11 可見沒過＋9 沒檔）。這些數字我對歸檔重算過，相符；**出處有兩種**（2026-10-01 第二輪更正，原文寫成都來自 `score.json`）：748／837／878／130／89／41 與「83＝有檔 41＋沒檔 42」是重播腳本印得出來的（`score.json`＋有沒有 `solution.py`）；「63 撞時限＝30＋33、沒撞 20＝11＋9」讀每格 `meta.json` 的 `timeout`（**agent 工作階段上限** 1800 秒，不是可見套件的 60 秒時限），「+38 對 +7 錯」讀 C361 臂同一批 83 題的 `score.json`——這兩組腳本沒有印、也沒有收進 repo。 |
| R2 | 文件 | 已文件化 | C5 README §3 加更正：最終 v3.7 是 `7db9bacf`／`7c63a132`，重算 continue 30／allow 1,297（審查前 `122a424c` 是 32／1,295）；v3.6.1 的 472／855 相符；第一次檢查退回的跑數 Colab 309→29、u274 36→20、S36-nocap 12→12；基準 commit 一行加註。 |
| R3 | 文件 | 已文件化 | C5 README §5.1「這座橋不是零設定」。 |
| R4 | 文件 | 已文件化 | C5 README §7 四臂表加 RETRY-NOSUITE（預算相同：同樣的最多 session 數與每次時限、撞時限或沒檔就重跑、留最後一次）；確認性比較 CONFORM 對 RETRY-NOSUITE，主要指標 `released AND hidden_pass`，wrong release 是 Holm 共同主要；BRIDGE_AUDIT 同步。 |
| R5 | 文件 | 已文件化 | C5 README §7：巢狀設計、不要拿巢狀的臂對 NATIVE 做 McNemar、檢定力（920 題、每題一次、不一致率約 11.7% ⇒ 80% 檢定力約 +3.2 個百分點）。 |

先前 H1–H3、M1–M10 的現況表（上一節）沒有逐條改寫，變動如下：M1／M2／M3 的新缺陷（F02／F03／F11／F04）已修；**M4**（基礎設施錯被當 FAIL）以預檢處理窄的一半、核心 `verifiers.py` 沒動；
M7 的殘餘（F15）已文件化；**M8**（`python_checks` 可被偽造）與 H2 的同帳號繞過仍成立、已文件化，沒有行程外的 verifier；M9（REPAIR 靜默變成 GATE）仍是**部分**（F18 延後）；M10（agent 看到的套件與 receiver 副本從不比對）由 F14 修了。

### 後續項（程式修正階段留下、這次沒做；依範圍規定只記錄）

1. **F18：REPAIR 回饋送達的量測**（canary 或掛鉤紀錄）——跑 REPAIR 臂之前最大的未處理項；在那之前只能靠預註冊的操弄檢查。
2. **把後端簽進 decision**，並讓 repair 的 Stop 掛鉤（`flow.check` 預設 `auto`）與 judge 用同一個後端（F01／F17；要動 `flow._record_decision` 與掛鉤，屬核心）。
3. F20(b)：Stop 掛鉤從 cwd 往上找**最近的**契約，子目錄的契約會遮住 bridge 契約（要改掛鉤）；bridge 的漂移比對只看 `<workspace>/.vacant/contract.json`。
4. F19 的 `--agent-uid` 探針；F01 的「gate／conform 不寫工作區契約」（會改人類的設計，要人類決定）。
5. F04 的 `--reference` 預檢；F05 的 `verifiers.py` rc 126／127／97→UNKNOWN（核心）；預檢之後才出現的 rc=127 競態仍是 FAIL。
6. F15：`status` 重新讀回目的地（核心 `flow.status`／`ledger.state_of`）；目前只靠文件要求評分器自己算雜湊。另：`flow.status` 自己的 `attempts` 數的是 `attempt_started`（judge 試了幾次），bridge 補了 `attempts_used`（裁決數），但核心的欄位名仍會誤導分析者。
7. W3 契約 notes 記程式版本；W5 的冗餘守衛；`python_checks` 偽造（M8）與同帳號繞過（H2）：已文件化，要解決得換成行程外的 verifier／SuiteSpec。
8. 文件階段順手看到、沒動：重現腳本借用 bridge 的私有函式 `_force_rmtree` 清理唯讀快照（bridge 改名時腳本會壞）；`test_replay_r534_gate_scores.py` 的真資料斷言只在設了 `R534_ARCHIVE_ROOT` 時才跑，CI 上是 skip。

### 文件階段做的驗證（2026-10-01）

- 對真封存（43 包、`MANIFEST.tsv` 的 sha256 全部吻合）重跑 `replay_r534_gate_scores.py`：c5／calib1／合併三組數字與上表、BRIDGE_AUDIT 逐格相同；分包對應：calib1＝0001–0004（40 格）、c5＝0006–0042（1,840 格），0005 與 0043 沒有計分格。
- 以 c5 的 A 臂 920 格重算 §2.1 的上限表：748／837／878／130／89、可見沒過 83＝有檔 41＋沒檔 42、可見沒過的格沒有一格 hidden 正確（以上讀 `score.json`，重播腳本印得出來）；撞時限 63（30＋33）、沒撞時限 11＋9（讀每格 `meta.json` 的 `timeout`，agent 上限 `agent_timeout_s`＝1800 秒；83 格裡有檔的 41 格沒有一格可見套件逾時）；拿 C361 當同一批 83 題的第二次：hidden 正確 38、可見過卻 hidden 錯 7（讀 C361 的 `score.json`；撞時限那組與這一組都是一次性計算、沒有收進 repo）。
- 重算 v3.7：`ops/eval/evidence_20260928_v37/replay/v37_c5_all.jsonl` 1,327 次檢查 → continue 30／allow 1,297（findings：`failed_step` 18、`missing_output` 10、`unsourced` 1、`test_claim/stale` 1、`test_claim/none` 0）；v361 472／855 相符。
- 重現腳本：在新 bridge 上跑過，輸出 `control_judge_no_attack=reject`、`pre_tool=allow`、`judge=accept`、`released=true`、`readback_ok=true`、`incorrect_add_2_3=0`、`required_add_2_3=5`（呼叫端環境的 `VACANT_HOME` 設成不存在的路徑也一樣）；兩個變異體（錯解改成回傳 99、套件改成永遠通過）分別印出 99、讓負控制斷言失敗。
- `python3 ops/check_repo_links.py`：OK（沒有死連結／死路徑）。測試：`test_native_acceptance_bridge`、`test_replay_r534_gate_scores`（`R534_ARCHIVE_ROOT` 指到真封存，所以真資料斷言有跑）與 `test_intake_verifier_hardening`／`test_intake_core`／`test_intake_gate_hardening`／`test_intake_server_cli`／`test_adapters_hardening` 一起 231 條全綠（exit 0，0 skip）；`ruff check` 乾淨；`ops/eval/native_acceptance_bridge.py` 786 行（≤ 850；第二輪文字更正後 794 行，見下節）；`git diff -- vacant_network` 為空。

### 第二輪：文件與出處的四處不實（2026-10-01）

只改文字與一條測試，沒有改任何程式行為。四處都是「文件說的和實測不符」；先重現、再改文字。沒有 commit、沒有 push；`vacant_network/` 零改動。

| 處 | 不實的地方 | 重現（2026-10-01） | 改了什麼 |
|---|---|---|---|
| (a) | bridge docstring、契約 `trust_boundary` 註記、README §5.2-6 與 §8、BRIDGE_AUDIT 表格寫「shell 指令不擋」 | 在 bridge 產生的契約上以 `decide_pre_tool` 試：`>`／`>>`／`cp`／`rm -rf`／`tee`／`sed -i`／`touch`／`dd of=`／`python -c "open(…,'w')"` 寫進 receiver home 或 `-suite` 全部 `deny`；`cat` 契約、套件、receiver 金鑰、變數拼路徑再 `>`、`python3 attack.py` 全部 `allow` | 五處文字改成「原生寫入工具＋shell 的**直接**寫法被字串層級檢查拒；間接寫法與所有讀取放行；軟護欄不是邊界」；README §8 補一句 receiver 金鑰不受 `protect_keys` 保護（它只護 agent 自己 `VACANT_HOME` 的金鑰目錄）。新測試 `test_shell_guard_denies_direct_writes_but_not_indirect_forms_or_reads` 把上面兩組釘住（把 `protect_paths` 清空的變異體會讓它失敗），並斷言 docstring／契約註記不再含舊句子。 |
| (b) | C5 README §2.1 寫「從歸檔的 `score.json` 重算（`replay_r534_gate_scores.py`）」，但 63／30／33／20／11／9 與 +38／+7 不是那支腳本的輸出 | 對真封存（`MANIFEST.tsv` 43 包）重算：撞時限的拆分 `{(撞,有檔)：30, (撞,沒檔)：33, (沒撞,有檔)：11, (沒撞,沒檔)：9}` 來自每格 `meta.json` 的 `timeout`，上限是 `agent_timeout_s`＝1800 秒（83 格全部），**不是** `score.json` 的 `suite_timeout_s`＝60 秒（有檔的 41 格 `visible.timed_out` 全是 false）；+38／+7 來自 C361 臂同一批 83 題的 `score.json`（hidden 正確 38、可見過卻錯 7）。腳本只印出 748／837／878／130／89／41（83＝920−837、沒檔 42＝920−878） | §2.1 改成兩種出處分開寫（腳本印得出來的／一次性讀 `meta.json` 與 C361 格算的、沒有入庫），並寫明「撞時限」是 agent 上限不是套件時限；review 文件 R1 列與驗證列同步。**沒有**把 `meta.json` 讀取加進重播腳本（那會改它「只讀 `score.json` 與 `solution.py` 在不在」的讀取範圍，不在這一輪）。 |
| (c) | 本文件的處置與驗證把兩條 bwrap 測試都寫成「要 root＋bwrap／setpriv」 | 兩條的 `skipif` 不同：端到端那條是 `euid != 0 or no setpriv or not _bwrap_usable()`；`test_candidate_cannot_see_receiver_files_under_bwrap` 只有 `not _bwrap_usable()`。在私有 mount namespace 以 nobody（euid 65534）跑這兩條：端到端 skip、bwrap 隱藏檔案那條通過 | W1 兩列與「驗證」一段改成分開寫條件（更正處都標了日期）。 |
| (d) | README §8 把「非 root 評測端＋agent 擁有的工作區」當成唯一算邊界的佈局，卻沒寫要怎麼備好；照做會在 prepare 以一行 EACCES 失敗 | 私有 mount namespace，評測端 nobody、工作區 uid 65533 擁有且 0755：`prepare` → `[Errno 13] Permission denied: '<workspace>/.vacant'`、exit 2、receiver 目錄裡什麼都沒留下（回收正常）；`chgrp <評測端 gid> <workspace>; chmod 775 <workspace>` 之後**同一個 receiver home** 重來成功，接著 agent 寫 `solution.py`、評測端 `judge`（bwrap，accept）＋`release`（`released`、`readback_ok`）通過；agent uid 讀不到 receiver 金鑰、寫不了 receiver home、讀得到 `.vacant/contract.json` 與套件副本 | README §8 新增「分開帳號的佈局要先備好」（工作區對評測端可寫、`.vacant` 之後由評測端擁有、receiver 父目錄的條件、工作區所有者仍可換掉 `.vacant` 但只影響資訊性比對）；bridge docstring 與 BRIDGE_AUDIT「安全界限」各補一句。程式沒改，沒有加「提早檢查工作區可不可寫」。 |

驗證：`ruff check` 乾淨；`python3 ops/check_repo_links.py` OK；`test_native_acceptance_bridge`（89→90 條）、`test_replay_r534_gate_scores`（`R534_ARCHIVE_ROOT` 指到真封存，真資料斷言有跑）與
`test_intake_verifier_hardening`／`test_intake_core`／`test_intake_gate_hardening`／`test_intake_server_cli`／`test_adapters_hardening` 一起 232 條全綠（0 skip）；
`ops/eval/native_acceptance_bridge.py` 794 行（≤ 850）；`git diff -- vacant_network` 為空。

這一輪看到、沒有動的（不在這四處裡，依範圍規定只記錄）：
1. README §2 表格的 `timeout 71／65` 與 `mean wall` 等列同樣沒有點名出處（71／65 對得上每格 `meta.json` 的 `timeout` 總數：A 71、C361 65，不是 `score.json`）。
2. `prepare` 不會在建立任何東西之前檢查「評測端寫得進工作區嗎」，所以 (d) 的失敗發生得比較晚（但會整批回收）；要加提早檢查是程式改動，這一輪沒做。

### 程式修正階段的紀錄（程式修正代理寫，內容沒改）

（以下是程式修正代理在**程式階段結束時**寫的紀錄，只調整了標題層級、內容沒改。其中「沒有做」清單裡的 F15、F16、F19、W4、R1–R5 是文件階段才處理的，現況以上面的總表為準。）

範圍：只動 `ops/eval/native_acceptance_bridge.py`（程式階段結束時 489→786 行；第二輪文件更正後 794 行；上限 850）、`tests/test_native_acceptance_bridge.py`、
`ops/eval/replay_r534_gate_scores.py`＋`tests/test_replay_r534_gate_scores.py`、`decisions/reviews/C5_NATIVE_ACCEPTANCE_20260928/{README,BRIDGE_AUDIT_FIX_R534_REPLAY}.md` 與本節。
`vacant_network/` 零改動（`git diff -- vacant_network` 為空）。沒有新增 canary、agent hook 紀錄讀取、signal handler、shadow-contract 掃描、
匯入／依賴探針、try id、新的 verifier 程式碼。人類的設計都保留：收件端合約 `<receiver_home>/contract.json`＋鎖檢查、flock 序列化、
每個 run 一個新的 receiver home、`release --artifact`。

| 條 | 狀態 | 怎麼處理（沒做的部分寫在「沒有做」） |
|---|---|---|
| F02 | 已修 | 嘗試次數＝裁決數；`--attempt`＝已有裁決＋1。`--sandbox` 加 `choices`；`attempt_started` 之前先做沙箱預檢（`make_sandbox`＋`python3 -c 'print(1)'`，30 秒），失敗＝`infra_void{stage:"preflight",attempt}`、不寫 `attempt_started`、exit 43。judge 內任何例外（`attempt_started` 之後）＝`infra_void{stage:"judge"}`、exit 43；被殺只留 `attempt_started`，沒有裁決所以不計次。同一編號累積 ≥3 次（`infra_void` 或沒有裁決的 `attempt_started`）拒絕、exit 43、「換新的 receiver home 重跑這一格」。 |
| F03 | 已修 | 工作區契約漂移只做位元組 sha256 比對（缺檔／讀不了＝false），報在 judge／release／status 的 `workspace_contract_matches_receiver` 與 `attempt_started`；不 HOLD、不 void、不拒絕、不耗次。release 不再因漂移拒絕。人類的 `test_tampered_workspace_contract_holds_before_acceptance` 依新語意改為 `test_workspace_contract_drift_is_informational_only`（弱化的工作區契約＋錯的解仍被 reject，因為收件端合約不變）；與改名後重複的 `test_agent_editing_visible_copy_…` 合併。 |
| F05 | 以預檢處理 | `python3` 在驗證沙箱跑不起來＝preflight 失敗＝void／43、不計次；沒碰 `verifiers.py`。預檢之後才出現的 rc=127（競態）仍是 FAIL。 |
| F07 | 已修（效果）| 因為 judge 不再依賴工作區契約，每個 session 換全新 /app 不再讓第 2…N 次變 hold。README §5 與 docstring 的 `$TASK` 路徑統一為 `$RUN`，套件副本路徑改成真正的 `<receiver_home>-suite`。 |
| F11 | 已修 | 工作區契約完全不再被解析（位元組比對）；200k 層巢狀不會崩。`main()` 另有一個保底：其他子指令的未預期例外＝一行訊息、exit 2。 |
| F04 | 已修（拒絕那一半）| prepare 拒絕：不是 `__pycache__` 的子目錄、非 `.py` 檔、symlink、帶必要參數（含 keyword-only）的頂層 `check_*`；訊息點名檔案並說「the executor ships only top-level .py files to the checks」。快照不複製 `__pycache__`。 |
| F12 | 已修 | 保留 scaffold 的 `deliverable_present`、`no_secrets_shipped`，在後面 `append` `visible_acceptance`。 |
| F13 | 已修 | `--destination` 的 help 與 docstring 改成實際規則（receiver home 內的 `dir:`）；移除 `--replace`（CLI 與 `prepare()` 參數）。 |
| F14 | 已修 | 新 `--agent-suite`（預設 `<workspace>/tests_visible` 存在才用）；prepare 輸出與契約 notes 記 `agent_visible_suite_sha256`（真的雜湊那個目錄，沒有就 null）、`pinned_suite_sha256`、`agent_visible_suite_matches_pinned`；judge／status 重算並回報（資訊性）。 |
| F09 | 已修 | release 結束碼與 `vacant release` 同表：0 已放行且讀回成立、43 void、44 拒絕、45 放行未確認（效果未知或讀回不成立）；測試釘 `EXIT == intake.cli.EXIT`。 |
| F10 | 已修 | 所有驗證（attempts、目的地、套件形狀、boundary／symlink／父目錄、沙箱預檢）在建立任何東西之前；之後失敗 `chmod -R u+w` 後回收這次建立的父目錄、home、唯讀套件副本與兩份契約並重新丟出例外；呼叫者本來就有的檔案不動。 |
| F08 | 已修 | `prepare`／`judge`／`release`／`status` 拒絕絕對路徑上任何一段是 symlink 的 receiver home。 |
| F01／F17 | 部分 | 非 `--insecure-same-account` 時拒絕 `none`／`unshare` 與解析成它們的 `auto`（prepare 與 judge 都預檢，要求 bwrap）；解析後的後端寫進契約 notes（`sandbox_backend`、`verifier_sandbox`）、`attempt_started`、judge 輸出（並傳給 `flow.submit`，驗證與預檢用同一個後端）；`evaluator_euid` 進 notes；docstring、notes、BRIDGE_AUDIT 寫明 bwrap 不替 root 評測端降權、對抗性邊界需要非 root 評測帳號。 |
| F20 | 部分 | 契約 `effects.protect_paths`＝`[receiver_home, <receiver_home>-suite]`（原生寫入工具被拒；shell 的直接寫法也被字串層級檢查拒、間接寫法與讀取不擋——2026-10-01 第二輪更正，原文寫「讀取與 shell 不擋」）。 |
| F21 | 已修 | 誤名的測試改為 `test_agent_copy_edit_does_not_change_receiver_suite`；新增「receiver 套件被改 ⇒ UNKNOWN ⇒ hold，且用掉一次嘗試」。 |
| F06 | 已修 | 檢視未提交的 `replay_r534_gate_scores.py`：正確，保留。分批次輸出（預設）、`--campaign`、`--merged`；對真封存重算 c5 為 hidden 748／758、有檔 878／886、放行錯 89／88、擋 41／40、配對 699／113／59／49，calib1 為 14／15（20 對）。`BRIDGE_AUDIT_FIX_R534_REPLAY.md` 的表改成 c5 only，另列 calib1，樣板那一句限縮到 20 題校準集。測試用合成封存，不依賴本機路徑；`R534_ARCHIVE_ROOT` 設定時多跑真資料斷言，沒設就 skip。 |
| W1 | 已修 | 測試 13→91 條（見「驗證」）；分開帳號端到端那條要 root＋setpriv＋可用的 bwrap，沒有就 skip；bwrap 隱藏檔案那條只要可用的 bwrap（2026-10-01 第二輪更正）。 |
| W2 | 已修 | `main()` 只對 judge 把 fd 0 導向 `/dev/null`（結束後還原）。 |
| W3 | 已修（一半）| 腳本啟動時把 `Path(__file__).resolve().parents[2]` 放到 `sys.path[0]` 才匯入 `vacant_network`。契約 notes 記程式版本沒有做。 |
| W5 | 一半 | `prepare` 的 `root is not None` 死分支隨重寫消失；`_task_id` 結尾的 `re.fullmatch` 與重複的 attempts 範圍檢查還在。 |

#### 沒有做（依範圍規定，記下來）

- **F18（中，REPAIR 臂靜默退化成 GATE）：沒做。** 需要 canary／掛鉤紀錄，都在禁止清單內。跑 REPAIR 臂之前仍需另外量「真的收到回饋的格數」；
  這是目前最大的未處理項。
- F15（`status.destination_live` 是帳本記的讀回）、F16（`reproduce_same_account_bypass.py` 寫死 `incorrect_add_2_3:0`、無負控制、塞 `VACANT_HOME`；
  腳本在新 bridge 上仍照舊跑通，輸出相同）、F19（`--agent-uid` 探針；現在只多記了 `evaluator_euid`）、W4（雙臂冒煙文件標 `repair` 但沒載入 Pi 掛鉤）。
- F01／F17 的「後端與 honest_bound 簽進 decision」（要動 `flow._record_decision`）、repair 掛鉤（`flow.check` 預設 `auto`）與 judge 共用後端；
  F01 的「gate／conform 不寫工作區契約」（會改人類設計）；F20(b)（Stop 掛鉤從 cwd 找最近契約，要改掛鉤）。
- F04 的 `--reference` 預檢（用參考解跑一次套件）；R1–R5（文件層級：上限表、v3.7 重播數字、非零設定說明、RETRY-NOSUITE、檢定力）。
- 殘餘行為：release 之後 `status` 仍回帳本記下的讀回；`python_checks` 偽造與同帳號繞過仍成立（已文件化）；`prepare` 預檢是 prepare 當下的主機狀態，judge 另外再預檢。

#### 驗證

- 測試：`tests/test_native_acceptance_bridge.py` 13→91 條、`tests/test_replay_r534_gate_scores.py` 5 條（其中 1 條要 `R534_ARCHIVE_ROOT`，沒設就 skip；設了跑過，c5 數字如上）；
  與 `test_intake_verifier_hardening`／`test_intake_core`／`test_intake_gate_hardening`／`test_intake_server_cli`／`test_adapters_hardening` 一起全綠（exit 0，1 skip）；`ruff check` 乾淨。
  有兩條 bwrap 測試，條件不同：分開 uid 端到端（agent uid 讀不到金鑰、讀得到套件副本、寫不了 receiver home，bwrap 下 judge＋release）要 root＋`setpriv`＋可用的 bwrap，沒有就 skip；bwrap 下候選碼看不到 receiver 檔案那條只要可用的 bwrap（原文把兩條都寫成「要 root＋bwrap／setpriv」，2026-10-01 第二輪更正：它的 `skipif` 只有「沒有可用的 bwrap」，在 nobody 身分下跑也通過，端到端那條在 nobody 下 skip）。這個環境（root＋bwrap）兩條都有跑。
- 變異檢查（刻意把守衛改掉、看測試要變紅、再還原；變異體只放在暫存目錄，checkout 沒被動過）：81 個一行變異體逐一跑整份測試，**80 個被殺、1 個存活**
  （U10：「nested files would not run」這句話的措辭，不是守衛）。檢查過的守衛：
  嘗試與預檢（A01–A12、A20–A21：嘗試數＝裁決數、void 上限、預檢失敗不寫 `attempt_started`、`python3` 探測、例外→`infra_void`、接受後不可再判、`--attempt` 精確與上限、conform 必給 `--attempt`）；
  觀察與雜項（A13–A19、A22：位元組比對、agent 套件比對、stdin 導向與還原、`sys.path`、`main` 保底、`make_sandbox` 呼叫時查找）；
  沙箱政策（S01–S09：prepare／judge 的 none／unshare 拒絕、預檢要求 bwrap、`--sandbox` choices、後端與 `evaluator_euid` 的記錄）；
  receiver home 的 symlink 檢查（P01）；套件形狀（U01–U09：子目錄、非 `.py`、symlink、必要參數、keyword-only、`__pycache__`、唯讀 chmod、快照不含 `__pycache__`）；
  prepare 回收（R01–R06：唯讀套件副本、home、工作區契約、父目錄、呼叫者原有的檔案、chmod）；
  W1 點名的邊界（B01–B15：鎖檢查、工作區比對、`_task` 內 boundary 重查與不放寬、目的地越界、只准 `dir:`、release 只放最新接受的、金鑰排除出交付物、`unknown_policy=hold`、可讀檢查、父目錄檢查、receiver 不在工作區內、uid 規則、release 不採工作區目的地、flock）；
  其餘（B16–B33：`stop_check`／`max_feedback_rounds`／`submit_on_end`、`protect_paths`、scaffold claims 不被蓋、release 結束碼三處、既有契約不被覆蓋、`attempts_used`、agent 套件的路徑與雜湊、prepare 內預檢、快照雜湊重驗、task id 截斷、`conflict_policy`、`timeout_s`、EXIT 表）。
- 第一輪存活、測試補強後重跑殺掉的：A16（還原 stdin：pytest 把 fd 0 指到 /dev/null，原測試空轉，改用真的 pipe）、U01（子目錄分支被「不是檔案」分支蓋住，加訊息斷言）、
  R06（回收不 chmod：root 本來就刪得掉，改用有非 root 語意的 `rmtree` 替身；在 nobody 身分手動驗過沒有 chmod 會留下殘餘）、B21（既有契約守衛被「套件副本已存在」蓋住，補「同工作區、新 home」）、U09（symlink 套件根被 `resolve()` 蓋住，補直接呼叫）。
- 沒有單獨變異（互為備援，拿掉一個由另一個補上、外部看不出差別）：prepare 的驗證前置段 vs 建立後同一檢查（`build_contract` 預演、父目錄、`lexists(target)`、可讀）。
