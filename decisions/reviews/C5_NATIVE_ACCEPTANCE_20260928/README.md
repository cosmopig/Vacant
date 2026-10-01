# C5 / Pi 原生平台整合審查：Evidence ≠ Acceptance

> 後續 bridge 安全修正與 R534 封存重算見 [BRIDGE_AUDIT_FIX_R534_REPLAY.md](BRIDGE_AUDIT_FIX_R534_REPLAY.md)。
> 2026-10-01：對 PR #82 修正分支（`6c2405de`）的審查見
> [`FINDINGS_20260930_PR82_FIXBRANCH_REVIEW.md`](../../conclusions/FINDINGS_20260930_PR82_FIXBRANCH_REVIEW.md)，文末「處置」逐條列出已修／已文件化／延後。
> 本頁第 5–8 節已於 2026-10-01 對照**目前**的 bridge 改寫（原本 PR #82 審查前的 CLI 範例不再適用）；
> 第 1–4 節是 C5 的根因分析，**測量數字沒有改**，只在第 2、3 節末尾補了上限表與更正（以「2026-10-01」標出）。

日期：2026-09-28  
來源分支：`claude/vacant-verification-redesign-jv7eou`  
本審查基準：`122a424c3e29e190871ce13a41b049e08900dc4e`（2026-10-01：v3.7 的最終版是 `7db9bacf`／`7c63a132`，見第 3 節末的更正）  
實作分支：`review/c5-native-acceptance-v2-20260928`

## 一句話結論

C5 沒有重現論文裡「單純 Vacant / CONFORM」的幅度。一個**還沒有檢驗過的假說**是：**C361 實際測的是
`mode: evidence`，而不是 CONFORM 的 executable acceptance + retry**。

> 2026-10-01 更正：這一句原本寫成「最主要的原因是」。沒有任何對照把「換成 CONFORM」單獨量過，所以它是假說，不是量到的原因。
> C5 自己的數字（第 2.1 節的上限表）也不支持「換成 CONFORM 就會補回來」：GATE 不可能讓正確交付變多；
> CONFORM 的上限 +9.0 個百分點裡，63／83 是撞時限後重跑、不需要套件就拿得到。
> 要分開「有可執行驗收」與「多給幾次機會」，需要一個預算相同、不用套件的 RETRY-NOSUITE 對照（第 7 節）。

C5 同時還真的踩到一個 Evidence bug：Pi 用 `sh run_tests.sh` 跑完 visible tests，
舊版卻說「沒有跑測試」，造成大量無效重跑。這個問題在本審查進行期間已由上游 v3.7
用較一般化的 `SCRIPT_RUNNER` 修正；**本分支不再覆寫 evidence.py**，只建立上游尚未接上的
native acceptance bridge。

## 1. C361 實際跑的是什麼

Drive 原始 cell 裡：

```json
{"install_json":{"mode":"evidence","agents":["pi"]}, ...}
```

`vacant_home/adapters/install.json` 亦為：

```json
{"mode":"evidence", ...}
```

這條路徑是在 native agent 宣告完成時檢查 trace 是否支持它的敘述，例如：

- 點名的材料有沒有讀；
- 數值是否可追溯；
- 說 tests passed 時 trace 裡有沒有測試；
- 失敗步驟是否被略過。

它**不知道任務正確答案**，也沒有 receiver-owned V 去決定 candidate 是否能 release。
所以這是 consistency/provenance review，不是 CONFORM。

## 2. 原始 C5 資料重算

使用者提供的 Drive 中 `chunk_0006.tar.xz`～`chunk_0043.tar.xz` 共 38 包；
逐包依 `MANIFEST.tsv` 重算 SHA-256 與檔案長度均一致。

> 2026-10-01 註：同一份封存共 43 包，另有 `calib1`（分包 0001–0004，20 題 × 2 臂的校準，不是 C5）；
> c5 的 1,840 格實際在分包 0006–0042（0005 與 0043 沒有計分格）。細節見 `BRIDGE_AUDIT_FIX_R534_REPLAY.md`（F06）。

C5 共 920 個 A/C361 pair，1,840 runs。

| 指標 | A: native Pi | C361: Pi + Evidence |
|---|---:|---:|
| hidden pass | 748 / 920 (81.30%) | 758 / 920 (82.39%) |
| visible pass | 837 | 846 |
| missing solution.py | 42 | 34 |
| timeout | 71 | 65 |
| mean wall | 508.59 s | 537.77 s |
| median wall | 293.45 s | 355.20 s |
| wire requests | 7,648 | 8,594 |
| prompt + completion tokens | 55,291,115 | 60,584,748 |

配對：C-only 59、A-only 49，差 **+1.087 pp**；探索性 exact two-sided McNemar
**p=0.38657**。這份資料沒有建立 C361 的品質增益。

C361 的成本則增加：
- wire requests +12.37%
- prompt+completion tokens +9.57%
- mean wall +5.74%
- median wall +21.04%
- token / hidden-pass candidate 約 +8.13%

A 自己已經平均 8.31 wire requests/task，所以它不是論文的 single-shot OFF；
native Pi 本身已會讀檔、測試、修訂。這也會壓低額外 feedback 的邊際效果。

### 2.1 沒裝組（A）的事後上限表（2026-10-01 補）

從歸檔重算，沒有重跑任何 agent，也沒有改上面的數字。**數字有兩種出處，不要混講**（2026-10-01 更正：原文寫成全部「從 `score.json` 由
`replay_r534_gate_scores.py` 重算」，那不實）：

- **重播腳本印得出來**（`ops/eval/replay_r534_gate_scores.py --campaign c5`，只讀每格 `score.json` 與 `app_final/solution.py` 在不在）：
  A 的 920 格裡，hidden 正確 748；最終有 `solution.py` 878（**有檔卻錯 130**；沒檔 42＝920−878）；可見驗收過 837，其中 hidden 錯 **89**；
  可見驗收沒過 **83**＝920−837＝有檔 41（`gate_refused_file`）＋沒檔 42，而且這 83 格沒有一格 hidden 正確（748 全在可見過的 837 裡）。
- **腳本沒有印、另外讀歸檔算的**（一次性計算，沒有收進 repo）：
  (i) 83 格裡的「**63 格撞時限**（有檔 30、沒檔 33）、沒撞 20（有檔 11、沒檔 9）」讀的是每格 `meta.json` 的 `timeout`——那是 **agent 工作階段上限**
  （`agent_timeout_s`＝1800 秒），**不是** `score.json` 裡可見套件的時限（`suite_timeout_s`＝60 秒；這 83 格的有檔 41 格沒有一格套件逾時）；
  (ii) 「事後多一個工作階段 ≈ +38 對、+7 錯」讀的是 **C361 臂在同一批 83 題的 `score.json`**（hidden 正確 38；可見過卻 hidden 錯 7）。
  (i)(ii) 不是腳本的輸出；要引用它們，請連同這一段出處一起引。

| 臂 | 正確交付 | 交出錯的 | 說明 |
|---|---:|---:|---|
| NATIVE | 748 | 130（交出 878） | 基準 |
| GATE | 748（**不可能變多**） | 89（−41） | 只扣下可見驗收沒過、但有檔的 41 格；從 NATIVE 的評分就能算出，**不必另外跑** |
| CONFORM | **上限** 831（+83，+9.0 個百分點） | **至少 89** | 假設 83 格重跑後全對；可見驗收看不到的 89 格照舊交出。事後估：多一個工作階段 ≈ +38 對、+7 錯（拿 C361 在同一批 83 題的結果當第二次） |
| REPAIR | **上限** ≤ +20 | — | 只有走到交件前檢查的才有機會：83 格裡沒撞時限的 20 格＝11 格有檔但可見沒過＋9 格沒檔；63 格撞時限的輪不到 |

這是事後上限，不是預測：「上限」假設每個被重跑或被修的格都修對；「≈ +38 對、+7 錯」是**探索性**的單次估計（C361 是另一個 arm 的另一次抽樣）。
「撞時限或沒檔就重開一個工作階段」這條**不用套件**的規則已經涵蓋 83 格裡的 72 格（63 撞時限＋9 沒檔但沒撞時限）：
套件本身在**正確交付**上最多多 11 格（1.2 個百分點），在**交出錯的**上多擋 41 格。

## 3. 已證實的 Evidence 誤退

最清楚的 cell：

`c5-C361-humanevalplus-humanevalplus_HumanEval_141-s1`

Pi 第一次 `sh run_tests.sh` 就輸出 26 個具名 pass，最後：

```
0 check(s) failed
```

assistant 說 “All tests passed.”，舊版 Vacant 卻回：

> The final message says "All tests passed", but no test or build command ran in the recorded steps.

模型又跑第二次，仍收到同樣誤退，再跑第三次。該 cell 最終 hidden 1026/1026、
visible 26/26。

上游 v3.7 的 replay 現在直接佐證同一診斷：

| replay | rows | continue | allow | test_claim/none |
|---|---:|---:|---:|---:|
| v3.6.1 | 1,327 | 472 | 855 | 543 findings |
| v3.7 | 1,327 | 32 | 1,295 | 0 |

v3.7 剩下的 findings 是 `failed_step`、`missing_output`、`unsourced`、
`test_claim/stale`，不再是「跑過 test script 卻看不到」。

> 2026-10-01 更正：上表 v3.7 那一列（32／1,295）是**審查前**的 `122a424c`。最終版是 `7db9bacf`／`7c63a132`，
> 對同一份 1,327 次檢查重算（`ops/eval/evidence_20260928_v37/replay/v37_c5_all.jsonl`）是 **continue 30／allow 1,297**，
> `test_claim/none` 仍是 0，剩下的 30 個 findings＝`failed_step` 18、`missing_output` 10、`unsourced` 1、`test_claim/stale` 1；
> v3.6.1 那一列（472／855、543 findings）重算相符。以每一跑**第一次**檢查來看，退回的跑數：Colab 309→29、u274 36→20、S36-nocap 12→12（不變）。
> 上表的數字沒有改；引用請用最終版。

因此：**Evidence parser 的 bug 已由 upstream 正確接手，不應在本 PR 再做一份平行 patch。**

## 4. 為什麼 v3.7 還是不等於論文 Vacant

修掉誤退後，Evidence 只會變得「比較不浪費」，不會自動得到 CONFORM 的機制：

```
Evidence:
native agent -> trace review -> maybe feedback -> allow

CONFORM / Acceptance:
native agent -> freeze candidate -> receiver-owned visible verifier
                                  -> FAIL: retry
                                  -> PASS: release exactly that frozen artifact
```

真正缺的不是更多 regexp，而是 **acceptance / release boundary**。

## 5. 本分支新增：native acceptance bridge

> 2026-10-01：本節與 §6–§8 已改寫成**目前**的 bridge（PR #82 修正分支加上 2026-10-01 的最小修正）；
> 原本 PR #82 版本的描述不再適用。逐條對照見 [`FINDINGS_20260930_PR82_FIXBRANCH_REVIEW.md`](../../conclusions/FINDINGS_20260930_PR82_FIXBRANCH_REVIEW.md) 文末的「處置」。

新增：

`ops/eval/native_acceptance_bridge.py`——四個子指令 `prepare`／`judge`／`release`／`status`。

它不呼叫任何 model API，也不自己造 agent loop；它只把現有 native platform 接到 repo
已經有的 `intake/{contract,flow,verifiers}.py`。

### 5.1 這座橋**不是零設定**

bridge 的每一臂都要評測者給 task id、套件路徑、交付物、receiver 的金鑰與 home——這不是 CLAUDE.md 產品原則裡的
「裝一次、照常用、不寫契約」。它回答的是**機制的上限**（有可執行驗收、有放行邊界時，上面那張上限表能到哪裡），
**不是**「安裝 Vacant 就會變好」。要把結論講成產品，得另外跑零設定的臂（Evidence，見 §7 的第五臂）。

### 5.2 prepare

在 agent 開始前跑一次。**所有檢查都先於建立任何東西**；之後任何一步失敗，都先 `chmod -R u+w` 再回收這次建立的
目錄、唯讀套件副本與兩份契約，然後把例外丟出去（呼叫者本來就有的檔案不動）。

1. 驗證：`--receiver-home` 必填，路徑上任何一段都不得是 symlink，且與工作區互不包含；不同 OS 帳號（§8），
   否則要明寫 `--insecure-same-account`；`--destination` 只收 receiver home **之內**的 `dir:`（預設 `<receiver-home>/released`）；
   已有契約或 `<receiver-home>-suite` 就拒絕——**一個 run 不能被取代**，要重來就換新的 receiver home 與乾淨的工作區；
   `--attempts` 在 1..10（預設 conform 5、其餘 1）。
2. 套件形狀：執行器只把最上層 `*.py` 送去跑，所以 prepare 拒絕不是 `__pycache__` 的子目錄、非 `.py` 檔、symlink、
   沒有頂層 `check_*`／`main` 的 `test_*.py`、帶必要參數的頂層 `check_*`（訊息點名檔案）。
   prepare **沒有真的跑過套件**，只擋這些看得出來的。
3. 沙箱預檢（preflight）：在驗證沙箱裡跑 `python3 -c 'print(1)'`（30 秒）。沒有 `--insecure-same-account` 時還要求後端是 **bwrap**
   （`none`／`unshare` 不對候選碼隱藏檔案；`auto` 解析成它們也拒，沒有可用的 bwrap 就在 agent 開始前失敗）。
   `--sandbox` 只收 `auto|bwrap|unshare|none`。
4. 建立：把 `--suite`（預設 `<workspace>/tests_visible`）複製成唯讀快照 `<receiver-home>-suite`（檔案 0444、目錄 0555，不複製 `__pycache__`），
   釘住 sha256，註冊為 `input:visible_suite`。
5. 契約寫兩份、位元組相同：`<receiver_home>/contract.json`（receiver 簽鎖的權威）與 `<workspace>/.vacant/contract.json`
   （給 agent 端掛鉤用）；`flow.lock` 在 agent 拿到第一個 prompt 之前簽鎖。claims＝scaffold 的 `deliverable_present`、`no_secrets_shipped`
   加上 `visible_acceptance`（`python_checks`、required）。交付物排除 `**/identity.key`、`**/intake/keys/**`。
6. `effects.protect_paths`＝`[<receiver_home>, <receiver_home>-suite]`：原生**寫入**工具在那兩處被拒；shell 指令也有字串層級的檢查，
   **直接**寫進去的會被拒（`>`／`>>` 重導向、`tee`／`cp`／`mv`／`rm`／`touch`／`sed -i`／`dd of=`、帶 `open(`／`write_text` 的 `python -c`——
   2026-10-01 在 bridge 產生的契約上實測）。**不擋**：間接寫法（路徑放在變數裡再 `> $d/…`、先寫一支腳本再 `python3 attack.py`）與**所有讀取**
   （`cat` 契約、套件、金鑰都放行）。這是軟護欄，不是邊界。
7. repair 模式才開 native Stop feedback（`feedback_rounds` 預設 3）；conform／gate 不開。背景 `submit_on_end` 一律關，
   避免與外層的同步 judge 競爭。
8. 契約 notes 記：`bridge_run_id`、`bridge_workspace`、`insecure_same_account`、`evaluator_euid`、解析後的
   `sandbox_backend` 與 `verifier_sandbox`、`agent_visible_suite_{path,sha256}`、`pinned_suite_sha256`、`agent_visible_suite_matches_pinned`。

`--agent-suite`（預設 `<workspace>/tests_visible`，存在才用，否則無）指 **agent 實際看到的那份套件**：prepare 真的雜湊它、和釘住的比，
不同就 `agent_visible_suite_matches_pinned: false`；judge／status 會重算並回報。這只**標出**分歧，不阻止分歧——
agent 的副本是設計上不同、還是事故，要在預註冊裡寫。

每個 run 一個新的 receiver home（`$RUN`＝任務×臂×重複，不是只有 `$TASK`），在 agent 工作區外、由另一個 OS 帳號持有：

```
/app/tests_visible                         # agent 可讀、自己測
/srv/eval/receiver/$RUN/vacant-suite      # bridge 複製並釘住的唯讀套件（來源由 --suite 指定）
/srv/eval/receiver/$RUN/vacant            # receiver keys/ledger/contract.json（每個 run 一個新的）
/srv/eval/receiver/$RUN/vacant/released   # 預設的放行目的地（必須在 receiver home 內）
```

### 5.3 judge

agent session 結束後，由 evaluator 同步執行：

```bash
python ops/eval/native_acceptance_bridge.py judge \
  --workspace /app \
  --attempt 1 \
  --receiver-home /srv/eval/receiver/$RUN/vacant
```

- judge 以 `bridge.lock`（flock）序列化；只開 `<receiver_home>/contract.json`、驗鎖，**只依那一份**裁決。
- **嘗試次數**：只有**裁決**（accept／reject／hold／escalate）用掉一次嘗試。`--attempt` 必須是「已有裁決數＋1」
  （gate／repair 可省略；conform 必須給，外層才不會弄丟重試）。接受之後不能再判。
- **評測端自己的失敗不計次**：判決前的沙箱預檢失敗（`python3` 在驗證沙箱跑不起來、後端不是 bwrap）＝帳本記 `infra_void`
  （stage `preflight`）、不寫 `attempt_started`、exit 43；`attempt_started` 之後 `flow.submit` 內的任何例外＝`infra_void`（stage `judge`）、exit 43；
  被殺的 judge 只留下 `attempt_started`、沒有裁決。這三種同一個編號都可以重判；同一編號累積 3 次失敗
  （`infra_void`，或沒有裁決的 `attempt_started`）judge 就拒絕（exit 43，「void cap reached…，換新的 receiver home 重跑這一格」）。
  **分析時 void 的格分母要留著**，不要因為 exit 43 就丟掉。
- **漂移只是資訊**：`<workspace>/.vacant/contract.json` 與 receiver 的那份做**位元組** sha256 比對（缺檔、讀不了＝false），
  結果印在 judge／release／status 輸出與 `attempt_started` 的 `workspace_contract_matches_receiver`。
  **不 HOLD、不 void、不拒絕、不耗次**：agent 把它改壞或刪掉（`git clean -fd`）、或外層每個 session 換一個全新的 `/app`，都不會讓格子報廢。
  釘住的 receiver 套件被改＝`UNKNOWN`＝hold（這是裁決，用掉一次嘗試）。`agent_visible_suite_matches_pinned` 同樣只回報。
- judge 執行期間 stdin 導向 `/dev/null`（候選碼不能吃掉評測端的 pipe，結束後還原）。
- judge 記錄解析後的 `sandbox_backend`（寫進 `attempt_started`、輸出與契約 notes，並傳給 `flow.submit`）。**簽章的 decision 本身沒有後端欄位**
  （要動 `flow._record_decision`，這次沒做）；跨環境比較時，後端以 `attempt_started` 與契約 notes 為準。
- 結束碼（`vacant submit`／`vacant release` 的同一張表，另加 2）：

  | 指令 | 0 | 40 | 41 | 42 | 43 | 44 | 45 | 2 |
  |---|---|---|---|---|---|---|---|---|
  | judge | accept | reject | hold | escalate | void（infra，沒用掉嘗試；含 void cap） | — | — | 用法錯誤／拒絕／未預期例外（一行 stderr，沒有 traceback） |
  | release | 已放行且讀回成立 | — | — | — | void | 拒絕 | 放行未確認（效果未知，或讀回不成立） | 同上 |

它走正式 `flow.submit`：

```
freeze candidate
 -> content-addressed artifact SHA
 -> verify pinned suite on frozen copy
 -> signed decision
 -> ledger
```

FAIL / UNKNOWN / CONFLICT 都不是 PASS。

### 5.4 release

只有 accepted artifact 才經 receiver gate release：`release --artifact <judge 印出的 artifact_sha256>`，
該值必須是**最新的 accepting 裁決**；release 的是隔離區內**同一個 SHA**，不是重新從可變的 `/app` 複製一次。
目的地只能是 receiver home 內的 `dir:`（檔案落在 `<目的地>/<task-id>/<deliverable>`）；相對路徑與 receiver home 之外的路徑都拒絕；
沒有 `--replace`。**評分只認 exit 0 且 `readback_ok`**，並且讀發布路徑上的檔案，不讀 `/app/solution.py`。

### 5.5 status，以及它不能拿來評分（F15）

`status` 印 `flow.status`（`state`、`decisions`、`void`、`ledger_verified`…）加上 `run_id`、`attempts_used`（＝裁決數，這才是用掉的嘗試）、
`attempts_max`、`workspace_contract_matches_receiver`、`agent_visible_suite_matches_pinned`。注意 `flow.status` 自己的 `attempts`
數的是 `attempt_started`（judge 試了幾次），與 `attempts_used` 不同。

**`status.destination_live` 是 release 當下讀回後記在帳本裡的結果，不是現在的目的地。** 放行之後目的地的檔案被改寫或刪除，
`status` 仍然回 `state: released`、`readback_ok: true`；要再 `release` 一次才會看到 `already_published`／`readback_ok: false`。
所以評分器**必須自己對已發布的檔案算 sha256**，與 accepting 裁決的 `artifact_sha256` 比；不能只讀 `status`。
（目的地在 receiver home 內，分開帳號下 agent 碰不到，所以這是低風險；但評分器要是讀 `status` 就會看不見事後的改動。）

## 6. 三種實驗臂

bridge 支援：

| mode | native Stop feedback | 外層行為 |
|---|---|---|
| gate | 無 | 一次 candidate，FAIL 就拒交 |
| repair | 有 | FAIL 回同一個 native session 修 |
| conform | 無 | FAIL 後外層啟一個**新的完整 native session**，預設最多 5 次 |

重要：CONFORM 的 retry 必須是新的完整 Pi session，不是直接再呼叫裸模型。
2026-10-01：每個 session 都要有可判的工作區，但**不必保留 `.vacant`**——judge 不依賴工作區的契約副本；
保留 `/app` 時第 k+1 個 session 會從上一輪的 `solution.py` 開始，比較接近 REPAIR 而不是獨立重抽，bridge 不記工作區有沒有被重置，
預註冊要寫是哪一種。

**REPAIR 的處理組可能靜默失效（F18，這次沒有修）。** repair 的回饋由 agent 端的 Stop 掛鉤送出，而掛鉤的設計是
**遇到例外或讀不到就放行**（失敗一律放行，`adapters/hookpolicy.decide_stop`）。下列情況掛鉤都放行、沒有回饋：
agent 帳號讀不到 `.vacant/contract.json` 或套件副本（例如評測端是 root、umask 077）、agent 的 `VACANT_HOME` 不可寫、
prepare 之後套件對 agent 變成不可讀、工作區契約被刪或壞掉。收件端的帳本與 `status` **看不出來**，
那一格 judge 之後就是一個普通的 reject——也就是**退化成 GATE**。bridge 沒有任何「回饋真的送達」的量測
（要做得靠 canary 或讀 agent 的掛鉤紀錄，這次修正的範圍明確排除）。因此 **REPAIR 臂在預註冊裡要寫一個操弄檢查：
真的收到至少一次回饋的格數**，REPAIR 對 GATE 的比較以那個數字當分母另報；沒有它，「REPAIR 沒有比 GATE 好」不能解讀成「回饋沒有用」，
因為處理組可能根本沒有送達。

## 7. 建議下一輪確認實驗

| Arm | acceptance | retry |
|---|---|---|
| NATIVE | 無；hidden 只事後評分 | platform 原行為 |
| RETRY-NOSUITE（控制組，**預算相同**） | 無 | 同樣的最多工作階段數與每個工作階段的時限；撞時限或沒有檔就**重跑**一個新的完整 native session，留最後一次 |
| GATE-ONLY | pinned visible suite | 無 |
| NATIVE-CONFORM | pinned visible suite | fresh full native session |
| NATIVE-REPAIR | pinned visible suite | same native session + visible failure feedback |

Evidence v3.7 可另列第五臂，但不要再叫 CONFORM。

**為什麼要 RETRY-NOSUITE（2026-10-01 補）**：§2.1 的上限表顯示，CONFORM 的 +83 有 63 格是「撞時限」、再 9 格是「沒檔」，
這兩種**不需要套件**，只要開新的工作階段重跑就拿得到。沒有這個對照，CONFORM 比 NATIVE 好多少，無法分開「有可執行驗收」與「多給了幾次機會」。

- **確認性的比較**是 CONFORM 對 RETRY-NOSUITE（同樣的最多工作階段數、同樣的每次時限），主要指標 `released AND hidden_pass`；
  wrong release 是 **Holm 共同主要**。
- **巢狀設計**：CONFORM 的第 1 次工作階段就是 NATIVE 那一跑；REPAIR／Evidence 從第一次交件前檢查的快照分岔。
  **不要拿巢狀的臂對 NATIVE 做 McNemar**（那一對的不一致格有一邊幾乎是 0）。
- **檢定力**：每題跑一次、920 題、不一致率約 11.7%（C5 的 A 對 C361：108／920）⇒ 80% 檢定力大約只看得到 **+3.2 個百分點**。
  REPAIR 的上限只有 ≤ +2.2（20／920）、Evidence 也一樣看不到；這個樣本量下的零結果要寫成「沒有量到差別、不能排除小效果」，不是「沒有效果」。
- GATE-ONLY 的結果用評分器從 NATIVE 就能算出（只把可見驗收沒過的格改成「未交」），**不必另外花機時**；
  它在這裡只當機制的對照與 release 路徑的端到端檢查。
- 每一臂有沒有載入 Vacant 掛鉤、載入的是哪個 mode，要寫進預註冊與**每一格的紀錄**（W4：Pi 雙臂冒煙文件曾標 `repair`，實際沒有載入 Pi 掛鉤）。
- 每臂回報 reject／hold／void 各幾格；REPAIR 另報真的收到回饋的格數（§6）。

主要指標應改成：
- `released AND hidden_pass`
- wrong release
- reject / HOLD / verifier infra void
- candidate hidden quality
- token / wall / requests / cost per correct release

hidden GT 只能在 selection/release 之後評分，不得回流 retry。

## 8. 信任邊界

`python_checks` 適合這批 C5 的非對抗 coding benchmark，但 repo 自己也明示：
candidate code 與 Python checks 在同一 interpreter，**防意外、不防惡意**。

若要把研究推到「對抗性 agent 的可信交付」，下一步應換成 receiver-side `command`
verifier / data-driven suite，並把 receiver keys、suite、runner 放到另一個 OS account/process
甚至另一台機器。

這也是 bridge 的 `--receiver-home` 的原因：signing state 不需要再像 C5 archive 那樣
落在 agent 的 `VACANT_HOME`。

2026-10-01 對照目前 bridge 的邊界（分開帳號與同帳號）：

- **分開帳號**（agent 以一個 uid 跑、receiver home 由另一個 uid 持有、0700）：沙箱後端**必須是 bwrap**，prepare 與 judge 都預檢，
  `none`／`unshare` 與解析成它們的 `auto` 都拒。**評測端必須是非 root 帳號**才算邊界：bwrap 不會替 root 評測端降權
  （root 跑的 bwrap 保有 capability），bridge 只把 `evaluator_euid` 記進契約 notes，**不會拒絕 root**。
- **分開帳號的佈局要先備好**（2026-10-01 補；在私有 mount namespace 裡以 nobody 當評測端、另一個 uid 擁有工作區實測）：
  `prepare` 要在**工作區裡**寫 `<workspace>/.vacant/contract.json`，而這個佈局裡工作區是 agent 的 uid 擁有的，所以**評測端必須寫得進工作區目錄**，
  例如 `chgrp <評測端 gid> /app && chmod 775 /app`（agent 不能在那個群組裡）；沒做就在 prepare 以一行
  `[Errno 13] Permission denied: '<workspace>/.vacant'` 失敗（exit 2；已全部回收，receiver home 與套件副本都沒留下，備好後同一個 home 可以重來）。
  備好之後：`.vacant` 由評測端擁有；評測端 umask 是 022 時是 0755／0644，agent 的 Stop 掛鉤讀得到（umask 077 會變成 0700／0600，agent 讀不到，REPAIR 就不會回饋——prepare 前先設 `umask 022`）；agent 讀不到 receiver 金鑰、寫不了 receiver home。
  `<receiver-home>` 的父目錄要由評測端擁有、且 group／other 不可寫（`_check_parent`）。工作區所有者仍可搬走或換掉 `.vacant`——
  那只會讓 `workspace_contract_matches_receiver` 變 false，不影響裁決（§5.3）。
- **同帳號**必須明寫 `--insecure-same-account`（簽進契約），而且那只是非對抗實驗的例外：agent 能改套件、重簽鎖、放行錯的解。
  `ops/eval/evidence_20260928_pi_plugin/reproduce_same_account_bypass.py` 現在先跑一個**負控制**（同一份錯解、沒有攻擊→ reject），
  攻擊者只從工作區契約找 receiver 路徑，最後印出的 `incorrect_add_2_3` 是實際執行已發布的 `solution.py` 量到的（要求 5）。
- **「是不是同帳號」是啟發式（F19）**：`prepare` 只比較工作區 owner 的 uid 與評測端的 euid。簽進契約的 `insecure_same_account: false`
  因此只代表這個比較，**不代表量到 agent 真的用另一個 uid 在跑**——工作區 owner 是別的 uid、agent 卻以評測端的 uid 執行時，prepare 照過；
  反過來（root 擁有工作區、agent 以 65534 跑）會被誤拒。做法：**讓 agent 以工作區 owner 的 uid 執行**，並把 agent 的實際 uid 寫進實驗紀錄。
  （`--agent-uid` 探針這次沒做。）
- `effects.protect_paths` 擋原生**寫入**工具，以及 shell 指令裡**直接**寫進 receiver home／套件副本的寫法（字串層級；見 §5.2-6 的清單）；
  **間接寫法與所有讀取都放行**（包括 receiver 的金鑰：`protect_keys` 只護 agent 自己 `VACANT_HOME` 的金鑰目錄）。契約副本（`.vacant/contract.json`）
  會洩漏 receiver 與套件的路徑，分開帳號下由 OS 權限擋，同帳號下不擋。
- `python_checks` 偽造（候選碼在 import 時直接寫出通過紀錄）在 bwrap 下仍成立，已文件化、沒有行程外的 verifier。

## 9. Archive 安全性

原 C5 archive 內含：

`vacant_home/intake/keys/*/identity.key`

本審查沒有讀取 private-key 內容。下一版 exporter 應 deny-list：
- `**/identity.key`
- auth/token/session secret
- receiver signing state

若該批 key 曾跨 cell 或用於非實驗環境，應 rotate；僅從 archive 內存在 key 無法證明
它們是否真的被重用。

## 10. 本 PR 的邊界

這份 PR **不再修改 v3.7 Evidence**。它只做：
- 保存 C5 根因與重算結果；
- 加入 native executable acceptance bridge；
- 加入 pin / reject / accept / release / drift / conform-attempt 的 E2E tests。

2026-10-01：PR #82 修正分支之上又做了一輪最小修正（嘗試記帳、沙箱釘住、結束碼、prepare 原子性等；測試 13→91 條）。
這些測試與修正驗證的是**機制**，沒有任何一條是量到答對率的證據：真批次前仍要先做第 7 節的冒煙
（每臂 reject／hold／void 各幾格、REPAIR 真的收到回饋的格數）。已知沒修、只寫進文件的缺口（F18 REPAIR 靜默退化、F19 同帳號是啟發式、
`python_checks` 偽造、同帳號繞過）見審查文件文末的處置。

它不宣稱：
- C5 舊結果因為修 parser 就能改寫；
- native acceptance 已量到論文相同增益；
- C5 可以再次充當完全 unseen confirmation set。

要回答「移植到 native agent platform 後是否真的恢復增益」，仍需要用上面的四臂設計重跑
一個新的 holdout。
