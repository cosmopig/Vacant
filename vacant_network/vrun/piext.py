"""這支在架構裡承重什麼：**pi 的產品版 extension——「裝一次、打開 pi、`/vacant on`」的那一支檔。**

`vacant install --agent pi` 之前的形狀是改寫 `~/.pi/agent/models.json`（把使用者每一個
provider 的 `baseUrl` 全部改道、再加一個 `vacant` provider），而那一格從來沒有被
`requests_seen` 證實過（`possess.CHANNEL_MEASURED["pi"] == ""`）。2026-09-22 人類的
要求是：

    pip install vacant-network
    vacant install            # 或裸打 vacant 讓它引導
    pi                        # 之後照舊；輸入框裡 /vacant on|off|status

pi 0.87.0 的 extension API（`docs/extensions.md`，2026-09-22 從原始碼讀的）讓這件事
**不必碰 `models.json`**：

  · `pi.registerProvider("vacant", {baseUrl, api:"openai-completions", apiKey, models})`
    —— provider 在 runtime 註冊，使用者自己的 provider **一個都不改道**。
  · `pi.setModel(model)` —— session 層的選擇，不改 `defaultProvider`。
  · `pi.registerCommand("vacant", …)` —— `/vacant on|off|status`。
  · 七個掛鉤事件 —— 與 2026-09-20 A 級那一跑用的**同一組**，經 `hookcli` 落 JSONL。

本模組做兩件事：
  (1) 把那支 extension **渲染成文字**（python 路徑、套件路徑、埠、state 目錄、裝機當下抓到的
      模型清單都烤進去）。寫進 `~/.pi/agent/extensions/vacant.ts` 的是 `possess.wire_pi`
      （`write_tracked`，可逐位元還原）。
  (2) 2026-09-24 起：那支 extension 的**互動閘門的 python 端**
      （`python -m vacant_network.vrun.piext gate <snapshot|begin|judge>`，見「互動模式的閘門」）。
      判準與收據全部重用既有件（`gateshim`／`launcher`／`acceptance`／`attest`／`receipts`），
      本模組只負責把「一個長 session 裡的一輪」接到它們身上。

## 為什麼是 `.ts` 而內容是純 JS

pi 的 `isExtensionFile` 只認 `.ts`／`.js`（`chunk-4DKZACXI.js`，jiti 載入）。純 JS 是
合法 TS，而純 JS 才能用 `node --check` 驗語法（`tests/test_vrun_possess.py`）。

## 誠實邊界（改碼請保留）

1. **裝了 extension ≠ 被中介。** 唯一算數的證據仍是常駐 proxyd journal 的
   `requests_seen`；`vacant possess status` 的 `wired`／`proven` 兩欄不變。
2. **agent 刪得掉這支檔**（`DECISION_20260920_AGENT_HOOKS_MEASURED.md` §三）。刪掉的
   那一跑 canary 不會燒 ⇒ 收據自動降級。本檔不假裝這是保證；保證只在 kernel。
3. **`/vacant off` 是使用者的選擇，不是失效**——但那一段要留痕：extension 會寫一筆
   `vacant_off`（含切去哪個 provider）進掛鉤日誌，收據不替它說謊。
   反方向同理：用 Ctrl+P／`/model` 切**回** `vacant` 會寫一筆 `vacant_on`（`source`＝
   `cycle`／`set`／`restore`）。不變式是**每一次轉換（任一方向）恰好一筆**；
   2026-09-24 實測前只有切走那一邊有痕跡，切回來之後日誌一路說「off」而呼叫其實又經過
   Vacant。⚠ 這仍只是**掛鉤日誌的敘述**，不是中介的證據（邊界 1）。
4. **fail-closed 不用另外寫**：模型一旦指到 `vacant` provider，proxyd 沒起來就是
   connection refused，pi 不會自己換 provider。`session_start` 會探一次並通知，讓使用者
   分得出「Vacant 那一層壞了」與「模型壞了」。
5. ~~**互動 session 不出裁決收據。**~~ ⇒ 2026-09-24 起互動 session **有**閘門：掛在
   `agent_before_settle`（`decisions/notes/NOTE_20260922_PI_OPENCODE_SLASH_VACANT_PLAN.md`
   §3.3），設計與它自己的誠實邊界 G1–G10 在下面「互動模式的閘門」那一節。
   ⚠ 三件事沒變：(i) 這條路的收據與 shim 那條**是兩條路、兩份證據**，不可合講；
   (ii) `possess.extension_proof` 仍然**只證通道**，不因為有了這個閘門而多證什麼；
   (iii) 這個閘門**不擋交付**（檔案已經在工作區裡），是標記不是攔截（G2）。
6. 掛鉤日誌**只落雜湊**（`hookcli` 邊界 1）；本檔不落 prompt、不落工具輸入原文。
7. **金鑰：借，不存。** `vacant` provider 的 `apiKey` 在 pi 行程裡、factory 那一刻，從
   `models.json` 裡 **baseUrl 等於 proxyd 上游**的那個 provider 抄它的 `apiKey` **設定字串**
   （字面值、`$VAR`／`${VAR}`、`!命令` 都原樣抄，交給 pi 自己解析；裸的 `MY_KEY`
   在 pi 是**字面值**，不是環境變數名）。所以 Authorization 帶的是
   使用者自己的金鑰，proxyd `sentinel=""` 原樣穿透、**永不持有**；本檔與 `possess` 的
   state 也**從不寫入金鑰**（烤進來的只有 provider id 與上游 url）。比對條件是 baseUrl
   相等——金鑰只送回它本來就要去的主機。找不到 ⇒ 送佔位 `sk-vacant-possess`，
   `session_start` 會講。金鑰在 `auth.json` 的內建 provider **不借**（`NEVER_TOUCH`）。
   ~~⚠ **沒量過**：pi 0.87.0 的 `registerProvider({apiKey})` 是否跟 `models.json` 走同一套
   解析（env 名／`!命令`）是從文件推的，**還沒有一跑真的用借來的金鑰打到要金鑰的上游**。~~
   ⇒ 2026-09-24 在 vacant-dev 用真 pi 0.87.0 量過：字面值、`$VAR`、`!命令` 三種借法都
   真的打到要金鑰的上游（解析與 `models.json` 同一套）。`${VAR}` 寫法沒有單獨量過借用。
   provider 的自訂 `headers`／`authHeader` 也沒有抄。
8. 上游是 sink（裝機時沒找到上游）⇒ 仍然切到 `vacant`（fail-closed，不偷偷直連），
   但 `session_start` 會用 error 等級講清楚「每一通都會被擋、怎麼修、`/vacant off` 回原模型」。
9. **模型清單也是借的，而且只有借的那份靠得住。** 裝機時的 `probe_models`、extension 的
   `refreshModels` 與 `proxyAlive` 都**不帶 Authorization**（金鑰是設定字串，只有 pi 會
   解析；本檔不自己跑 `!命令`）⇒ 上游要金鑰就一律 401（2026-09-24 實測），烤進來的清單
   是空的、`refreshModels` 也拿不到。所以 `vacant` provider 的模型次序是：
   **邊界 7 那個 provider 的 `models`**（只抄 id／name／contextWindow／maxTokens／
   reasoning／input；`cost` 歸零、`headers`／`authHeader`／`compat` 不抄）→ 裝機時烤進來的
   → `DEFAULT_MODEL`。落到最後那一格時清單是**猜的**：上游沒有那個 id 就每一通 404
   （fail-closed，不會繞開），`session_start` 會講。`/vacant on` 先找使用者**現在用的那個
   id**（＝同一個模型、經過 Vacant），找不到才依 `VACANT_AGENT_MODEL`→`DEFAULT_MODEL`→
   第一個。⚠ 同 id 不保證同一個模型設定：借來的欄位以外（`compat`、自訂 headers）不一樣。

## 互動模式的閘門（`agent_before_settle`，2026-09-24）

2026-09-24 在 vacant-dev 用真 pi 0.87.0 量過常駐 extension 那條路
（`ops/vacantrun/possess_pi_ext_real_20260924/README.md` §三）：**只有通道、沒有閘門**
——R534 五題裡兩題 agent 退出碼 0、沒寫 `solution.py`，沒有任何東西擋。本節補的就是那個洞。

### 觸發點：文件怎麼說（**以 pi 0.87.0 的 `docs/extensions.md` 為準，不是猜的**）

  · 「`agent_before_settle` is the final actionable boundary: it can append session entries
    and request one continuation.」「`agent_settled` is final and notification-only」
    （extensions.md「agent_start / agent_end / agent_before_settle / agent_settled」）。
    ⇒ `agent_end` **不是**收手點（之後還可能自動重試、壓縮、跑排隊訊息）；
      `agent_before_settle` 才是「這一回合 agent 不會再自己動了」而且還能介入的那一刻。
  · payload：`{type, entries, continue, context:{…, canContinue}, outcome}`，
    `outcome ∈ completed | aborted | error`（`dist/core/extensions/types.d.ts`
    `BoundaryState`）。回傳 `{entries?, continue?}`；entry 只准
    `custom`／`custom_message`／`context_edit`／`compaction`。
  · 「`continue: true` ensures one next provider request」「an unconditional `continue: true`
    … can create an endless loop」⇒ **續跑一定要有上限**（`VACANT_PI_GATE_MAX_ROUNDS`）。
  · 「Error and aborted responses remain hard exits」「If the run is aborted while
    `agent_before_settle` handlers are running … requested continuation is suppressed」
    ⇒ `outcome != completed` **永不要求續跑**。
  · 「A `custom_message` draft contributes a user-role model message but is
    extension-authored」⇒ 回饋是一則**我們寫的** user-role 訊息，不是使用者打的（G6）。
  · 讀碼（**不是量測**）：`dist/core/agent-session.js` `_runAgentPrompt` 在每一次使用者
    prompt 的迴圈尾端呼叫 `_runBeforeSettleBoundary`，handler 是被 `await` 的；print／json／
    rpc 模式共用同一個 `AgentSession` ⇒ 用完整路徑打 `pi -p` 也會觸發本閘門。

### 1. 驗收從哪來（與 shim **同一套規則**，外加「session 開頭快照＋雜湊釘在記憶體」）

  · 規則逐字重用 `gateshim.resolve_suite`：`VACANT_SUITE`（建議放**工作區外**）→
    `.vacant/suite`／`tests_visible`／`.vacant.toml`（由 cwd 往上找到 git 根為止）。
    收據上的 `suite_source` 與 shim 同一組字。
  · **快照在 `session_start` 拍**（這個 session 的 agent 還沒動過任何一輪之前），複製到
    `~/.vacant-run/pi_<run_id>_s<k>/suite/`（**工作區外**；在工作區裡 ⇒ 整個 session 停用，
    同 `launcher` 那條擋門）。快照的樹雜湊 `suite_sha256` **釘在 pi 行程的記憶體裡**，每一輪
    驗收前重算比對：對不上 ⇒ `infra_void`（`suite_snapshot_changed`，不判拒交也不判通過）。
  · 每一輪另外重算**原始來源**的樹雜湊：agent（或人）在 session 中途改了 `.vacant/suite`
    ⇒ 驗收**照樣用快照**，收據記 `suite_drift=true`，通知講出來。
  · 為什麼這樣而不是 shim 的「每跑複製一份」：shim 一跑一個行程，複製的那一刻 agent 還沒
    起來；互動 session 有很多輪，**第二輪讀到的來源可能是第一輪的 agent 改過的**。
  · 找不到驗收 ⇒ 每一輪都是 `stop_reason="ungated"`、`accepted=null`（收據
    `accepted_is_null=true`），**不是通過**——shim 退出碼 `21` 的同一個語意。
    找到驗收目錄但裡面沒有 `test_*.py` ⇒ `no_suite` 拒交（fail-closed，同 launcher）。
  · 使用者中途才加驗收 ⇒ `/new`（`session_start` 會重拍）或重開 pi。

### 2. 何時判、判什麼

  `before_agent_start`（使用者送出 prompt）記起點：journal 行數、時間、工作區樹雜湊（有驗收
  才算）。`agent_before_settle` ⇒ `python -m vacant_network.vrun.piext gate judge`：
  凍結工作區（`launcher._freeze`，TOCTOU 對不上 ⇒ `infra_void`）→ 在凍結副本上跑
  `acceptance.run_suite(suite="visible")`（沙箱 `none`，同 shim）→ `attest.attest` 量級別
  → 簽收據。`outcome=aborted`（使用者按 Esc）**不判**、照實通知；`error` 照判、不續跑。

### 3. 收據怎麼對應「哪一輪」

  · **一次 settle 評估＝一個 run 目錄**：`~/.vacant-run/pi_<run_id>_s<session>/p<prompt>_r<round>/`，
    形狀**與 shim 那條逐字相同**（`rows.jsonl`＋`receipts_RUN-ON.ndjson`＋`.pub.json`＋
    `run_RUN-ON.json`＋`visible_RUN-ON.json`＋`possess.json`／`NOT_CERTIFIED.json`），
    `ws_attempt`／`ws_verdict` 各一筆 ⇒ `verify_receipts --glob '<那個目錄>'` 一個字都不用改。
  · 為什麼不是一個 session 一條鏈：鏈要同一把私鑰從頭簽到尾，而本閘門每一輪是**另一個
    python 行程**；要嘛把私鑰落盤（違反 RECORD_SPEC §7），要嘛養一個常駐簽章行程（多一個
    會死的東西）。所以每一輪一把一次性金鑰、簽完即丟，輪與輪之間用簽進鏈的
    `prev_receipt_head`（上一輪 `ws_verdict` 的雜湊）串起來。
  · 簽進 `ws_verdict` 的定位欄位：`session_run_id`（＝掛鉤日誌的 run_id）、`session_seq`、
    `prompt_seq`、`gate_round`、`final_for_prompt`、`continuation_requested`、
    `trigger="agent_before_settle"`、`run="pi-settle"`（shim 那條是 `"vacant-run"`）、
    `settle_outcome`、`settle_verdict`、`suite_source`／`suite_sha256`／`suite_drift`、
    `blocks_delivery=false`。
  · **不發退出碼**（NOTE §3.3-2：觸發點變了，`0`／`20` 不可重用）：互動裁決是
    `settle_verdict ∈ pass | fail | ungated | no_mediation | infra_void` 這個新欄位。
    對應關係：`fail`≈shim `20`、`ungated`≈`21`、`infra_void`≈`22`、`no_mediation`≈`23`
    （wire 0 通 ⇒ 蓋過 pass／fail／ungated，唯獨不蓋 infra_void——**`23` 的紀律逐字沿用**）。
    **級別（`tier`）是另一個正交的欄位，永不蓋 `settle_verdict`**（所以也不蓋 infra_void）；
    `VACANT_ATTEST=fail` 且 C 級 ⇒ 照 shim：寫 `NOT_CERTIFIED.json`、不寫 `possess.json`。

### 4. 判了之後

  · 每一輪都 `ctx.ui.notify`（沒有 UI 的 print／json 模式寫 stderr）＋ 掛鉤日誌一筆
    `gate_verdict`（只落雜湊）＋ run 目錄。沒有驗收的 session 只在第一輪講一次
    「沒有驗收可跑」，之後靜靜落收據（`/vacant status` 看最後一輪）。
  · 回饋續跑（**預設關**，`VACANT_PI_GATE_FEEDBACK=revise` 才開，`VACANT_PI_GATE_MAX_ROUNDS`
    預設 3）：沒過、還有額度、`outcome=completed`、`canContinue`、而且 wire > 0 ⇒ 回
    `{entries:[…, custom_message], continue:true}`。回饋文字**只由可見驗收的
    `acceptance.render_failures` 組成**，表頭講明是機器輸出，正文逐字沿用 R534
    `piarms.FEEDBACK_TEMPLATE`（那一段在真 pi 上跑過，換字＝引入沒量過的變因），KS-1 可執行防呆。

### 5. 開關（全部讀 pi 啟動時的環境；agent 的工具改不到 pi 行程自己的環境）

| 變數 | 預設 | 意思 |
|---|---|---|
| `VACANT_PI_GATE` | `on` | `off`／`0`／`false`／`no` ⇒ 這個行程沒有閘門（G1） |
| `VACANT_PI_GATE_FEEDBACK` | `off` | 只有 `revise` 才開回饋續跑（G6） |
| `VACANT_PI_GATE_MAX_ROUNDS` | `3` | 回饋開著時一個 prompt 最多幾輪（含第一輪；1–10） |
| `VACANT_PI_GATE_TIMEOUT_S` | `600` | python 端一次評估的總逾時；逾時 ⇒ 那一輪沒有裁決（照實通知） |
| `VACANT_PI_GATE_WIRE_WAIT_S` | `2` | 等 proxyd 把最後一通寫進 journal 的上限（G4） |
| `VACANT_PI_GATE_KEEP_FROZEN` | 空 | `1` ⇒ 留下每一輪的凍結副本（預設刪，雜湊已綁進收據） |
| `VACANT_SUITE`／`VACANT_TEST_TIMEOUT`／`VACANT_ATTEST` | — | 與 shim 同義（`gateshim`） |

### 6. 證據等級（**不准混講**）

  · **L-fake 測過**（`tests/test_vrun_piext_gate.py`：假 pi、真 python 閘門、真驗收、真收據、
    真 hookcli；「模型呼叫」＝測試往 journal 寫一行）：沒交件 ⇒ `fail`＋收據驗得過；交了且過 ⇒
    `pass`；沒有驗收 ⇒ `ungated`／`accepted_is_null`；空驗收目錄 ⇒ `no_suite` 拒交；wire 0 通 ⇒
    `no_mediation`＋驗章器判 VOID；回饋續跑只含可見驗收（canary 零命中＋翻紅負控制）、有上限、
    error／`canContinue=false` 不續跑；agent 改來源 ⇒ `suite_drift` 而裁決不變；改快照 ⇒
    `infra_void` 不簽；KS-1 髒訊息 ⇒ 作廢；`/vacant off` ⇒ 不判且 off 痕跡仍恰好一筆；Esc 不判；
    `VACANT_PI_GATE=off`；print 模式寫 stderr；掛鉤日誌只有雜湊、金鑰不落盤；每輪對帳切窗
    （不切窗的反事實會把多出來的一通解釋掉）。
  · **要真 pi 才能驗**（G7）：真 pi 0.87.0 在收手時 `await` 這個 handler、`custom_message`
    的顯示與它在下一通 request 裡的樣子、續跑是否恰好多一通、follow-up 排隊的行為、真 TUI 裡
    notify 的長相、以及 R534 那兩格「退出碼 0 沒寫檔」在這條路上是否真的被判成 `fail`。
    **在那一跑之前，「互動模式有閘門」只能講到 L-fake。**

### 互動閘門的誠實邊界（改碼請保留）

  G1. **agent 刪得掉這支 extension 檔，使用者可以 `/vacant off`、`VACANT_PI_GATE=off`**
      ⇒ 那一段沒有閘門。刪掉的效果從下一次載入起算（當下這個行程裡的閘門還在）。
      不准寫「不會被繞過」；保證只在 kernel（enclosure），而互動 pi 不在圍牆裡。
  G2. **不擋交付。** settle 那一刻檔案早就在工作區裡了，`fail` 是標記不是攔截；用完整路徑打
      `pi -p` 時 pi 的退出碼**不變**（本閘門改不了它）。「擋下來」只在 shim 那條（行程結束、
      退出碼 20）成立，兩條不可合講。
  G3. **驗收做到的是「改了看得見」，不是「改不到」**：agent 與使用者同一個 OS 使用者、沒有沙箱
      ⇒ 原始驗收與 `~/.vacant-run` 裡的快照它都寫得到。快照雜湊釘在 pi 行程記憶體 ⇒ 快照被改
      ⇒ `infra_void`；來源被改 ⇒ `suite_drift`。**session 開頭之前**（上一個 session）被改的
      看不出來，除非拿收據上的 `suite_sha256` 去對。
  G4. **wire 計數是共用 journal 的時間窗**：常駐 proxyd 是整台機器一支 ⇒ `requests_seen`
      ＝這一輪窗內**非 canary** 的通數，同機器別的 session／agent 同時打會算進來（上偏）；
      proxyd 還沒寫完索引就讀到 ⇒ 等到與本 session 掛鉤的 `before_provider_request` 筆數對上
      （最多 `VACANT_PI_GATE_WIRE_WAIT_S`），等不到 ⇒ `wire_count_semantics="lower_bound"`。
      **任何 canary 都不算**（讀碼：shim 那條的 `requests_seen` 是 ephemeral proxy 的總通數，
      hookcli 在 `session_start` 打的那一通 canary 也經過它；這裡更嚴，兩條的數字不可直接比）。
  G5. **級別由探針決定**：互動 pi 不在圍牆裡 ⇒ 量出來最多 B′（canary 有燒），不准說 A。
  G6. **回饋預設關**，理由三條：(i) 互動使用者在場，自動續跑會在他沒下指令時燒 token、改工作區；
      (ii) 回饋是 extension 寫的 user-role 訊息——launcher 守的是「零偽造發言」，預設不替使用者
      說話；(iii) R534 真模型上「沒過→重改」出現 0 次，沒有證據說自動續跑有用。開了之後能說的
      只有「回饋一定出現在模型的輸入裡」，**不能說不可忽略、不能說提高通過率**（`retry` V2 邊界）。
      互動路徑**根本沒有隱藏驗收**；回饋只吃 `suite="visible"` 的結果（測試有 canary 負控制）。
  G7. 觸發點與 payload 以 pi 0.87.0 文件為準；**沒量過**：真 pi 上 `custom_message` 的顯示、
      續跑那一通是否真的只多一次 provider request、使用者在串流中排隊的 follow-up 會不會燒
      `before_agent_start`（不燒的話那一次評估沿用上一輪的終點當起點、`gate_round` 往上加）。
      本節全部是 **L-fake**（假 pi）直到有真 pi 的一跑。
  G8. 每一輪一把一次性金鑰，**私鑰不落盤**；`prev_receipt_head` 讓「刪掉中間一張」看得出來，
      「刪掉最後一張」看不出來。收據的究責宣稱只到「事後沒被改過」，不是「由某個已知的人簽的」。
  G9. **成本**：有驗收時每一輪都凍結（複製）整個 cwd；在 `$HOME` 或 `/` 開 pi ⇒ 收據目錄落在
      工作區裡 ⇒ 整個 session 停用並講出來。
  G10. **不改 `/vacant off|on` 的痕跡不變式**：閘門自己的事件是 `gate_*`（只落雜湊），唯一新增的
      `user_prompt_submit`（`source="vacant-gate"`）只在回饋續跑時寫，是那一通續跑呼叫的回合開端，
      不是 on／off 轉換。
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import pathlib
import re
import shutil
import sys
import time
from typing import Any

from ..memory import assert_ks1_clean

#: 我們註冊進 pi 的 provider id。**要看得出是誰接的**——狀態列會顯示 `(vacant) <model>`。
PROVIDER_ID = "vacant"

#: 裝機時抓不到上游模型清單的時候烤進去的那一個（與 `possess`／`gateshim` 同一個預設）。
DEFAULT_MODEL = "gemma-4-12b-it-qat"

#: extension 檔名（相對 `~/.pi/agent/`）。
EXTENSION_REL = ".pi/agent/extensions/vacant.ts"

#: 本檔渲染出來的 extension 第一行要有這個標記——`status`／測試用它認「這支是我們寫的」。
MARK = "// vacant-possess-extension/1"

# ── 互動閘門的常數（設計見模組 docstring「互動模式的閘門」）──────────────────
#: 簽進收據 `run` 欄位的值。shim 那條是 `"vacant-run"`——**兩條路的收據靠這一欄分得開**。
GATE_RUN_TAG = "pi-settle"
#: 觸發點（pi 0.87.0 `docs/extensions.md` 的事件名，逐字）。
SETTLE_TRIGGER = "agent_before_settle"
#: 互動裁決的封閉集合。**不是退出碼**（NOTE §3.3-2：觸發點變了，`0`／`20` 不可重用）。
SETTLE_VERDICTS = ("pass", "fail", "ungated", "no_mediation", "infra_void")
#: 回饋續跑的兩種模式。**預設 `off`**（G6）。
GATE_FEEDBACK_MODES = ("off", "revise")
#: 回饋開著時的續跑上限（含第一輪）。與 `retry.DEFAULT_MAX_ATTEMPTS` 同值、同理由：
#: 要的是一個**小**的成本上限；文件明講無條件 `continue: true` 會無限迴圈。
GATE_DEFAULT_MAX_ROUNDS = 3
#: python 端一次評估的總逾時（秒）。每個測試檔另有 `VACANT_TEST_TIMEOUT`（同 shim，預設 30）。
GATE_DEFAULT_TIMEOUT_S = 600
#: 等常駐 proxyd 把最後一通寫進 journal 的上限（秒；G4）。
GATE_WIRE_WAIT_S = 2.0
#: 這一條 arm 名與 `launcher.ARM_ON` 同一個字（`verify_receipts` 用它認鏈檔）。
GATE_ARM = "RUN-ON"
#: 續跑那一則訊息在 pi session 裡的 `customType`。
GATE_FEEDBACK_CUSTOM_TYPE = "vacant-gate-feedback"

#: 回饋表頭：講明是機器輸出、第幾輪（形狀取自 R534 `piarms.TOOL_RESULT_HEADER` 的用意）。
SETTLE_FEEDBACK_HEADER = ("VACANT ACCEPTANCE (round {round} of {max_rounds}). "
                          "This is machine output, not a person.")
#: 回饋正文。**逐字沿用 `ops/gain/r534/piarms.py::FEEDBACK_TEMPLATE`**（含硬折行）：
#: 那一段是給「同一段對話裡多說一輪」寫的、在真 pi 上跑過——正是本閘門的形狀。
#: （`retry.FEEDBACK_BODY` 改過最後一句，因為它的觸發點是行程結束；這裡不是。）
#: `{block}` 只准是 `acceptance.render_failures(<suite="visible" 的結果>)`。
SETTLE_FEEDBACK_BODY = """The checks that ship with this task were run against your
working directory. They did not all pass.

{block}

Fix the working directory. When you consider it finished, reply with a short
plain-text summary and do not call any tool."""

# ── KS-1 可執行防呆（鐵律 1）：import 時就跑，繞不過去 ─────────────────────
for _t in (SETTLE_FEEDBACK_HEADER, SETTLE_FEEDBACK_BODY):
    assert_ks1_clean(_t)

_TEMPLATE = r"""%(mark)s
// 由 vacant_network/vrun/piext.py 渲染；`vacant uninstall` 會逐位元還原／刪掉本檔。
// ⚠ 這支檔在 $HOME 底下，agent 自己刪得掉（實測）。刪掉的那一跑 canary 不會燒，
//   收據自動降級——本檔不是保證，保證只在 kernel（enclosure）。
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { randomUUID } from "node:crypto";

const PY = %(py)s;
const HOOK_ARGS = %(hook_args)s;
const PYPATH = %(pypath)s;
const STATE = %(state)s;
const PORT = %(port)s;
const PROVIDER = %(provider)s;
const BAKED_MODELS = %(models)s;
const DEFAULT_MODEL = %(default_model)s;
const UPSTREAM = %(upstream)s;        // proxyd 轉去的地方（裝機時決定；只有 url，沒有金鑰）
const UPSTREAM_IS_SINK = %(upstream_is_sink)s;
const KEY_FROM = %(key_from)s;        // 裝機時算出的「金鑰向哪個 provider 借」（只是提示，runtime 仍比對 baseUrl）
const PI_AGENT_DIR = %(pi_agent_dir)s;
const PROXY = %(proxy)s;          // 字面值（不是算出來的）：status／測試要在檔案裡直接看得到端點
const BASE = PROXY + "/v1";
const GATE_ARGS = %(gate_args)s;  // 互動閘門的 python 端（piext.py「互動模式的閘門」）
const JOURNAL = join(STATE, "proxyd", "wire", "index.jsonl");   // 常駐 proxyd 的 journal（整台機器共用，G4）

// ── 掛鉤契約 vacant-hook/1：每個事件 spawn 一次 hookcli，落 JSONL ─────────────
const runId = randomUUID();
const hookLog = join(STATE, "hooks", "pi_" + runId + ".jsonl");

function hookEnv() {
  const env = Object.assign({}, process.env);
  env.VACANT_HOOK_LOG = hookLog;
  env.VACANT_RUN_ID = runId;
  env.VACANT_HOOK_AGENT = "pi";
  env.VACANT_RUN_PROXY = PROXY;
  env.PYTHONPATH = PYPATH + (process.env.PYTHONPATH ? ":" + process.env.PYTHONPATH : "");
  return env;
}

function fire(event, payload) {
  try {
    mkdirSync(join(STATE, "hooks"), { recursive: true });
    spawnSync(PY, [...HOOK_ARGS, event], {
      input: JSON.stringify(payload || {}),
      timeout: 20000, stdio: ["pipe", "ignore", "ignore"], env: hookEnv(),
    });
  } catch (e) { /* 掛鉤壞掉不可以弄死 agent（hookcli 誠實邊界 3） */ }
}

function notify(ctx, text, level) {
  try { if (ctx && ctx.hasUI && ctx.ui) ctx.ui.notify(text, level || "info"); }
  catch (e) { /* print 模式沒有 UI */ }
}

// ── 互動模式的閘門（agent_before_settle）──────────────────────────────────────
//   設計與誠實邊界 G1–G10 在 piext.py「互動模式的閘門」。⚠ 這不是保證：agent 刪得掉
//   這支檔、使用者 /vacant off 就沒有閘門；裁決**不擋檔案**（標記不是攔截）。
function envOn(name, dflt) {
  const raw = process.env[name];
  const v = String(raw === undefined || raw === null || raw === "" ? dflt : raw).trim().toLowerCase();
  return !(v === "off" || v === "0" || v === "false" || v === "no");
}
function envInt(name, dflt, lo, hi) {
  const n = parseInt(String(process.env[name] || ""), 10);
  return Number.isFinite(n) && n >= lo && n <= hi ? n : dflt;
}
const GATE_ON = envOn("VACANT_PI_GATE", "on");
// 回饋續跑**預設關**（理由 G6）：只有明講 revise 才開；其他任何字都是關。
const GATE_FEEDBACK = String(process.env.VACANT_PI_GATE_FEEDBACK || "").trim().toLowerCase() === "revise" ? "revise" : "off";
const GATE_MAX_ROUNDS = GATE_FEEDBACK === "revise" ? envInt("VACANT_PI_GATE_MAX_ROUNDS", %(gate_max_rounds)s, 1, 10) : 1;
const GATE_TIMEOUT_MS = envInt("VACANT_PI_GATE_TIMEOUT_S", %(gate_timeout_s)s, 5, 7200) * 1000;

// 這個行程的閘門狀態。**快照雜湊只活在這裡**（pi 行程的記憶體），agent 的工具碰不到（G3）。
const gate = { sessionSeq: 0, snap: null, promptSeq: 0, round: 0, begin: null,
               prevHead: null, last: null, ungatedSaid: false, skipSaid: false };

// 跑一次 python 端。**非同步**：驗收可能要幾十秒，spawnSync 會把 TUI 的事件迴圈整個卡住。
// **永遠 resolve、不 reject**：閘門壞掉不可以弄死 agent，但要照實講（ok:false ＋ error）。
function gatePy(op, payload, timeoutMs) {
  return new Promise((resolve) => {
    let done = false, out = "", err = "", timer = null, child = null;
    const finish = (v) => { if (done) return; done = true; if (timer) clearTimeout(timer); resolve(v); };
    const ms = timeoutMs || 60000;
    try {
      child = spawn(PY, [...GATE_ARGS, op], { env: hookEnv(), stdio: ["pipe", "pipe", "pipe"] });
    } catch (e) { finish({ ok: false, op, error: "spawn：" + String((e && e.message) || e) }); return; }
    timer = setTimeout(() => {
      try { child.kill("SIGKILL"); } catch (e) { /* 已經結束 */ }
      finish({ ok: false, op, error: "逾時 " + Math.round(ms / 1000) + " 秒（VACANT_PI_GATE_TIMEOUT_S）" });
    }, ms);
    child.stdout.on("data", (d) => { out += d; });
    child.stderr.on("data", (d) => { err += d; });
    child.stdin.on("error", () => { /* python 先死了；close 會回報 */ });
    child.on("error", (e) => finish({ ok: false, op, error: String((e && e.message) || e) }));
    child.on("close", (code) => {
      const lines = out.split("\n").filter((x) => x.trim());
      try { finish(JSON.parse(lines[lines.length - 1])); }
      catch (e) { finish({ ok: false, op, error: "rc=" + code + "：" + err.slice(-600) }); }
    });
    try { child.stdin.end(JSON.stringify(payload || {})); } catch (e) { /* close 會回報 */ }
  });
}

function gateCwd(ctx) { return (ctx && typeof ctx.cwd === "string" && ctx.cwd) ? ctx.cwd : process.cwd(); }

// 裁決要讓人看得到：TUI 用 notify；print／json 模式沒有 UI ⇒ 寫 stderr（stdout 是 agent 的）
function gateSay(ctx, text, level) {
  if (ctx && ctx.hasUI && ctx.ui) { notify(ctx, text, level); return; }
  try { process.stderr.write("[vacant] " + text + "\n"); } catch (e) { /* 沒有 stderr */ }
}

function gateSnapText() {
  const s = gate.snap;
  if (!GATE_ON) return "關（VACANT_PI_GATE=off）⇒ 這個行程沒有裁決";
  if (!s) return "還沒快照驗收（session_start 沒看到）";
  if (!s.ok) return "**壞了**：" + (s.error || "") + " ⇒ 沒有裁決（不是通過）";
  if (s.disabled) return "**停用**：" + s.disabled;
  if (!s.snapshot_dir) return "沒有驗收可跑（" + s.suite_source + "）⇒ 每一輪 accepted=null，**不是通過**";
  return "驗收來源 " + s.suite_source + "（" + s.suite_src + "）；快照 sha256 " +
         String(s.suite_sha256 || "").slice(0, 12) + "…（" + (s.snapshot_when || "") + " 拍的，之後改來源不影響裁決）";
}

function gateFeedbackText() {
  return GATE_FEEDBACK === "revise"
    ? "開：沒過就把**可見驗收**的失敗回饋給 agent，最多 " + GATE_MAX_ROUNDS + " 輪"
    : "關（預設；VACANT_PI_GATE_FEEDBACK=revise 才開）";
}

// session 開頭（**這個 session 的 agent 還沒動過任何一輪**）拍驗收快照（G3）。
async function gateSnapshot(ctx, when) {
  gate.sessionSeq += 1;
  gate.promptSeq = 0; gate.round = 0; gate.begin = null; gate.prevHead = null;
  gate.last = null; gate.ungatedSaid = false; gate.skipSaid = false;
  const r = await gatePy("snapshot", { cwd: gateCwd(ctx), run_id: runId,
                                       session_seq: gate.sessionSeq, when }, GATE_TIMEOUT_MS);
  gate.snap = r;
  fire("gate_snapshot", { ok: !!(r && r.ok), when, suite_source: (r && r.suite_source) || null,
                          suite_sha256: (r && r.suite_sha256) || null, disabled: (r && r.disabled) || null });
  return r;
}

// 使用者送出 prompt：記這一輪的起點（journal 行數、時間、工作區樹雜湊）。
async function gateBegin(ctx) {
  if (!gate.snap) await gateSnapshot(ctx, "before_agent_start");   // 不該發生；照實記在哪一刻拍的
  gate.promptSeq += 1;
  gate.round = 1;
  gate.begin = null;
  const s = gate.snap;
  if (!s || !s.ok || s.disabled) return;
  const r = await gatePy("begin", { cwd: gateCwd(ctx), journal: JOURNAL,
                                    suite_present: !!s.snapshot_dir }, GATE_TIMEOUT_MS);
  gate.begin = (r && r.ok)
    ? { ts: r.ts, journal_offset: r.journal_offset, ws_start_sha256: r.ws_start_sha256 }
    : { error: (r && r.error) || "begin 失敗" };
}

// agent 這一回合不會再自己動了 ⇒ 驗收 ⇒ 收據 ⇒（可選）把可見驗收的失敗回饋給它、要求一次續跑。
async function gateSettle(event, ctx) {
  if (!GATE_ON) return undefined;
  if (!enabled) {                      // /vacant off 是使用者的選擇：那一段沒有閘門（G1），留一筆
    fire("gate_skipped", { reason: "vacant_off" });
    gate.begin = null;
    return undefined;
  }
  const outcome = event && event.outcome;
  if (outcome === "aborted") {         // 使用者按 Esc：agent 沒有宣告完成 ⇒ 不判
    fire("gate_skipped", { reason: "aborted" });
    gateSay(ctx, "Vacant 閘門：這一輪被中斷 ⇒ **沒有裁決**（不是通過，也不是拒交）。", "warning");
    gate.begin = null;
    return undefined;
  }
  const s = gate.snap;
  if (!s || !s.ok || s.disabled) {
    fire("gate_skipped", { reason: !s ? "no_snapshot" : (!s.ok ? "snapshot_failed" : "disabled") });
    if (!gate.skipSaid) { gateSay(ctx, "Vacant 閘門：" + gateSnapText(), "error"); gate.skipSaid = true; }
    gate.begin = null;
    return undefined;
  }
  if (!gate.begin || gate.begin.error) {
    fire("gate_skipped", { reason: "no_round_begin" });
    gateSay(ctx, "Vacant 閘門：這一輪沒有起點紀錄（" + ((gate.begin && gate.begin.error) || "回合中途才打開？") +
                 "）⇒ **沒有裁決**（不是通過）。", "warning");
    gate.begin = null;
    return undefined;
  }
  const req = {
    cwd: gateCwd(ctx), run_id: runId, session_seq: gate.sessionSeq, session_dir: s.session_dir,
    prompt_seq: gate.promptSeq, gate_round: gate.round, max_rounds: GATE_MAX_ROUNDS,
    feedback: GATE_FEEDBACK,
    suite: s.snapshot_dir ? { source: s.suite_source, src: s.suite_src, snapshot_dir: s.snapshot_dir,
                              sha256: s.suite_sha256, src_sha256: s.suite_src_sha256 } : null,
    begin: gate.begin, outcome: outcome || null,
    can_continue: !!(event && event.context && event.context.canContinue === true),
    hook_log: hookLog, journal: JOURNAL, proxy: PROXY, prev_receipt_head: gate.prevHead,
  };
  const r = await gatePy("judge", req, GATE_TIMEOUT_MS);
  if (!r || !r.ok) {
    fire("gate_error", { prompt_seq: gate.promptSeq, gate_round: gate.round });
    gateSay(ctx, "Vacant 閘門壞了：" + ((r && r.error) || "") + " ⇒ 這一輪**沒有裁決**（不是通過）。", "error");
    gate.begin = null;
    return undefined;
  }
  gate.last = r;
  if (r.receipt_head) gate.prevHead = r.receipt_head;
  fire("gate_verdict", { prompt_seq: gate.promptSeq, gate_round: gate.round, settle_verdict: r.settle_verdict,
                         stop_reason: r.stop_reason, receipt_head: r.receipt_head || null, cont: !!r.continue });
  if (r.settle_verdict !== "ungated" || !gate.ungatedSaid) {
    gateSay(ctx, (r.notify && r.notify.text) || ("Vacant 閘門：" + r.settle_verdict),
            (r.notify && r.notify.level) || "info");
    if (r.settle_verdict === "ungated") gate.ungatedSaid = true;
  }
  // 下一次評估（回饋續跑、或沒燒 before_agent_start 的排隊訊息）的起點＝這一次的終點
  gate.begin = r.end || null;
  gate.round += 1;
  if (r.continue === true && typeof r.feedback_text === "string" && r.feedback_text) {
    // 續跑那一通模型呼叫的回合開端：一則 extension 寫的 user-role 訊息送進了對話 ⇒ 對帳要看得到
    // 它，否則那一通是 unexplained。**一定寫在 gate.begin 設好之後**（時間要落在這一輪的窗裡）。
    fire("user_prompt_submit", { source: "vacant-gate", gate_round: gate.round });
    const prior = Array.isArray(event && event.entries) ? event.entries : [];
    return { entries: [...prior, { type: "custom_message", customType: "vacant-gate-feedback",
                                   content: r.feedback_text, display: true }],
             continue: true };
  }
  return undefined;
}

// src ＝ 使用者 models.json 裡那個 provider 的 model 條目（借來的；可缺）。
// 只抄 name／reasoning／input／contextWindow／maxTokens；cost 不抄（我們不替別人記帳）、
// headers／authHeader／compat 不抄（誠實邊界 7、9）。
function modelDef(id, src) {
  const s = src && typeof src === "object" ? src : {};
  const pos = (v, d) => (typeof v === "number" && isFinite(v) && v > 0 ? v : d);
  const input = Array.isArray(s.input) ? s.input.filter((x) => typeof x === "string" && x) : [];
  return { id,
           name: typeof s.name === "string" && s.name ? s.name : id,
           reasoning: typeof s.reasoning === "boolean" ? s.reasoning : false,
           input: input.length ? input : ["text"],
           cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
           contextWindow: pos(s.contextWindow, 131072),
           maxTokens: pos(s.maxTokens, 16384) };
}

// models.json 的 `models` 陣列 → modelDef 清單（條目可以是物件或裸 id 字串；重複 id 只留第一個）
function modelDefsFrom(list) {
  const out = [], seen = new Set();
  for (const m of Array.isArray(list) ? list : []) {
    const id = typeof m === "string" ? m : (m && typeof m.id === "string" ? m.id : "");
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(modelDef(id, typeof m === "object" ? m : null));
  }
  return out;
}

async function proxyAlive(signal) {
  try {
    const r = await fetch(BASE + "/models?vacant_canary=status-" + runId, { signal });
    return { listening: true, status: r.status };
  } catch (e) {
    return { listening: false, status: null, error: String(e && e.message || e) };
  }
}

function heartbeat() {
  try {
    const p = join(STATE, "proxyd", "heartbeat");
    if (!existsSync(p)) return null;
    return JSON.parse(readFileSync(p, "utf-8"));
  } catch (e) { return null; }
}

function hookLines() {
  try { return existsSync(hookLog) ? readFileSync(hookLog, "utf-8").split("\n").filter(Boolean).length : 0; }
  catch (e) { return 0; }
}

// ── 借：使用者自己那個 provider 的 apiKey 設定字串＋模型清單（誠實邊界 7、9）───
//   只借 baseUrl 等於 UPSTREAM 的；抄的是**設定字串**，解析交給 pi。不寫任何檔。
//   models.json 只在 factory 那一刻讀一次。
function normUrl(u) { return String(u || "").trim().replace(/\/+$/, ""); }
function upstreamProviders() {
  if (!UPSTREAM || UPSTREAM_IS_SINK) return [];
  try {
    const dir = process.env.PI_CODING_AGENT_DIR || PI_AGENT_DIR;
    if (!dir) return [];             // 不知道 pi 設定在哪 ⇒ 不借（絕不讀 cwd 的 models.json）
    const doc = JSON.parse(readFileSync(join(dir, "models.json"), "utf-8"));
    const provs = (doc && doc.providers) || {};
    const ids = Object.keys(provs).filter((id) => id !== PROVIDER && id !== "vacantproxy");
    ids.sort((a, b) => (b === KEY_FROM) - (a === KEY_FROM));
    return ids.map((id) => ({ id, p: provs[id] || {} }))
      .filter((x) => normUrl(x.p.baseUrl) === normUrl(UPSTREAM));
  } catch (e) { return []; /* 讀不到 models.json ⇒ 不借 */ }
}
const MATCHED = upstreamProviders();
function borrowKey() {
  for (const { id, p } of MATCHED) {
    if (typeof p.apiKey === "string" && p.apiKey) return { provider: id, apiKey: p.apiKey };
  }
  return null;
}
const BORROWED = borrowKey();
// 模型清單：先看借金鑰的那一個 provider，再看其他 baseUrl 相同的（同一台主機，同一份目錄）。
function borrowModels() {
  const first = BORROWED ? MATCHED.filter((x) => x.id === BORROWED.provider) : [];
  for (const { id, p } of first.concat(MATCHED.filter((x) => !BORROWED || x.id !== BORROWED.provider))) {
    if (modelDefsFrom(p.models).length) return { provider: id, raw: p.models };
  }
  return null;
}
const BORROWED_MODELS = borrowModels();
// ⚠ 要金鑰的上游對「不帶 Authorization 的探測」一律 401 ⇒ 裝機時 BAKED_MODELS 是空的、
//   refreshModels 也拿不到 ⇒ 若只剩 DEFAULT_MODEL，那是**猜的**，上游多半沒有這個 id（每一通 404）。
//   所以次序是：借來的清單 → 裝機時烤進來的 → DEFAULT_MODEL（誠實邊界 9）。
const MODEL_SOURCE = BORROWED_MODELS ? "borrowed" : (BAKED_MODELS.length ? "baked" : "default");
function baseModels() {                // 每次回新物件（pi 可能改它拿到的陣列）
  if (BORROWED_MODELS) return modelDefsFrom(BORROWED_MODELS.raw);
  return (BAKED_MODELS.length ? BAKED_MODELS : [DEFAULT_MODEL]).map((id) => modelDef(id));
}
function modelSourceText() {
  if (MODEL_SOURCE === "borrowed") return "借自 models.json 的「" + BORROWED_MODELS.provider + "」";
  if (MODEL_SOURCE === "baked") return "裝機時經 proxyd 問到的";
  return "**猜的**（只有 " + DEFAULT_MODEL + "；上游沒有這個 id 就每一通 404）";
}

// ── 狀態：這個 session 有沒有開、開之前用的是哪個模型 ────────────────────────
let enabled = true;
let previous = null;   // {provider, id} —— /vacant off 切回去用
// 不變式：**每一次轉換（任一方向）恰好一筆痕跡**。
// /vacant off 自己已經寫過一筆 vacant_off；它接著呼叫 pi.setModel(previous) 會觸發
// model_select（實測：extension 的 await pi.setModel 會在 await 之內同步觸發），那一筆不可以再寫。
let offInProgress = false;
// 反方向同理：switchOn 自己會寫 vacant_on；它的 pi.setModel(target) 觸發的 model_select 不再寫。
let onInProgress = false;
// 我們最後知道的「現在在不在 vacant 上」（true／false／null＝不知道）。
// model_select 帶 previousModel 時以它為準；沒帶才用這個判斷是不是一次轉換。
let onVacantNow = null;

function pickVacantModel(ctx) {
  const reg = ctx && ctx.modelRegistry;
  if (!reg) return null;
  const cur = ctx && ctx.model;
  // 「/vacant on」＝**同一個模型，經過 Vacant**：先找使用者現在用的那個 id，
  // 再 VACANT_AGENT_MODEL、DEFAULT_MODEL，最後才是 vacant provider 的第一個。
  const ids = [];
  if (cur && typeof cur.id === "string" && cur.id) ids.push(cur.id);
  if (process.env.VACANT_AGENT_MODEL) ids.push(process.env.VACANT_AGENT_MODEL);
  ids.push(DEFAULT_MODEL);
  for (const id of ids) {
    try { const m = reg.find(PROVIDER, id); if (m) return m; } catch (e) { /* 下一個 */ }
  }
  try {
    const all = typeof reg.getAll === "function" ? reg.getAll() : [];
    for (const m of all) if (m && m.provider === PROVIDER) return m;
  } catch (e) { /* 沒有 */ }
  for (const d of baseModels()) {       // registry 沒有 getAll 時的最後一招
    try { const m = reg.find(PROVIDER, d.id); if (m) return m; } catch (e) { /* 下一個 */ }
  }
  return null;
}

async function switchOn(pi, ctx, why) {
  const cur = ctx && ctx.model;
  if (cur && cur.provider === PROVIDER) { onVacantNow = true; return true; }
  const target = pickVacantModel(ctx);
  if (!target) {
    notify(ctx, "Vacant：找不到 provider「" + PROVIDER + "」的模型 ⇒ 沒有切換。**這個 session 沒經過 Vacant。**", "error");
    fire("vacant_on_failed", { reason: "no_model" });
    return false;
  }
  previous = cur ? { provider: cur.provider, id: cur.id } : previous;
  let ok = false;
  onInProgress = true;
  try { ok = await pi.setModel(target); } finally { onInProgress = false; }
  if (!ok) {
    notify(ctx, "Vacant：pi.setModel 回 false（provider 沒有 auth？）⇒ 沒有切換。**這個 session 沒經過 Vacant。**", "error");
    fire("vacant_on_failed", { reason: "setModel_false" });
    return false;
  }
  onVacantNow = true;
  fire("vacant_on", { source: why, model: target.provider + "/" + target.id });
  return true;
}

export default function (pi) {
  // ── 通道：runtime 註冊 provider，**不動使用者的 models.json** ──────────────
  pi.registerProvider(PROVIDER, {
    name: "Vacant（常駐 proxyd :" + PORT + "）",
    baseUrl: BASE,
    // 使用者自己的金鑰設定字串（借來的）或佔位；proxyd sentinel="" ⇒ Authorization 原樣穿透
    apiKey: BORROWED ? BORROWED.apiKey : "sk-vacant-possess",
    api: "openai-completions",
    compat: { supportsDeveloperRole: false, supportsReasoningEffort: false },
    // 借來的清單 → 裝機時烤進來的 → DEFAULT_MODEL（誠實邊界 9）
    models: baseModels(),
    // 上游目錄變了就重抓；這一通同時是一次會進 journal 的 canary。
    // ⚠ **永遠不回空清單、也不 throw**：proxyd 起來了但上游是 sink／掛了時，
    //   /v1/models 會回 502（常常不是 JSON）或 JSON 錯誤體。若照回 `[]`（或拋錯讓 pi
    //   自己決定），pi 可能拿它蓋掉 provider 的模型清單 ⇒ 烤進去的模型消失、
    //   pickVacantModel 找不到 ⇒ `/vacant on`／session_start 報「沒有模型」而**沒有切過去**，
    //   使用者就安靜地停在原 provider 上。那不是 fail-closed，是 fail-open。
    //   pi 0.87.0 對 refreshModels 拋錯時保留舊清單還是清空，NOTE_20260922 沒有讀到
    //   ⇒ 不賭它：非 2xx／例外／空清單一律回 baseModels()（與註冊時同一份）。模型仍指到
    //   vacant，上游壞掉就在連線那一刻失敗（誠實邊界 4），而不是在選模型那一刻繞開。
    // ⚠ 這一通**不帶 Authorization**（金鑰是設定字串，只有 pi 會解析）⇒ 要金鑰的上游
    //   在這裡永遠 401，清單只能靠借的（2026-09-24 vacant-dev 實測）。
    // 上游 2xx 且有清單（不要金鑰的本機上游）時：
    //   · 有借來的清單 ⇒ **聯集，借來的在前、原樣保留**。理由：使用者設定的 contextWindow／
    //     maxTokens／reasoning 才是「同一個模型」——只照上游 id 重建會把它們重設成預設值，
    //     那正是 LCB 兩臂對照第一版整批作廢的干擾（contextWindow 262144 vs 131072）。
    //     也**不刪**上游沒列的借來 id：有些伺服器只列已載入的模型，刪了會把使用者
    //     正在用的模型從 session 底下抽走。上游多列的 id 補在後面（它們真的在那台主機上）。
    //   · 沒有借來的清單 ⇒ 上游的活清單取代裝機時的快照（兩者本來就是同一個來源）。
    async refreshModels({ signal }) {
      const base = baseModels();
      try {
        const r = await fetch(BASE + "/models?vacant_canary=refresh-" + runId, { signal });
        if (!r || !r.ok) return base;
        const body = await r.json();
        const data = Array.isArray(body && body.data) ? body.data : [];
        const live = modelDefsFrom(data.filter((m) => m && typeof m.id === "string").map((m) => m.id));
        if (!live.length) return base;
        if (!BORROWED_MODELS) return live;
        const have = new Set(base.map((m) => m.id));
        return base.concat(live.filter((m) => !have.has(m.id)));
      } catch (e) {
        return base;
      }
    },
  });

  // ── /vacant on | off | status ────────────────────────────────────────────
  pi.registerCommand("vacant", {
    description: "Vacant：on（切到中介）／off（切回原模型，留痕）／status（proxyd、通數、掛鉤日誌、閘門）",
    getArgumentCompletions: (prefix) => {
      const items = ["on", "off", "status"].filter((x) => x.startsWith(prefix || ""))
        .map((x) => ({ value: x, label: x }));
      return items.length ? items : null;
    },
    handler: async (args, ctx) => {
      // 只有空白與 "status" 是 status；**其他字一律不當 status 跑**（實測 `/vacant statusReply…`
      // 曾印出 status——打錯字不可以看起來像成功）。
      const sub = String(args || "").trim().split(/\s+/)[0] || "status";
      if (sub !== "on" && sub !== "off" && sub !== "status") {
        notify(ctx, "用法：/vacant on | off | status（收到「" + sub.slice(0, 40) + "」，什麼都沒做）", "warning");
        return;
      }
      if (sub === "on") {
        enabled = true;
        if (await switchOn(pi, ctx, "command")) {
          notify(ctx, "Vacant 開：模型呼叫經 " + PROXY + "（provider「" + PROVIDER + "」）", "info");
        }
        return;
      }
      if (sub === "off") {
        enabled = false;
        const cur = ctx && ctx.model;
        const to = previous;
        fire("vacant_off", { from: cur ? cur.provider + "/" + cur.id : null,
                             to: to ? to.provider + "/" + to.id : null });
        if (to && ctx && ctx.modelRegistry) {
          let m = null;
          try { m = ctx.modelRegistry.find(to.provider, to.id); } catch (e) { m = null; }
          let switched = false;
          if (m) {
            offInProgress = true;
            try { switched = await pi.setModel(m); } finally { offInProgress = false; }
          }
          if (switched) {
            onVacantNow = false;
            notify(ctx, "Vacant 關：切回 " + to.provider + "/" + to.id + "。⚠ 這一段不經過 Vacant，掛鉤日誌記了一筆 vacant_off。", "warning");
            return;
          }
        }
        notify(ctx, "Vacant 關：沒有可切回的先前模型，用 /model 自己選。⚠ 之後的呼叫不經過 Vacant，日誌記了一筆 vacant_off。", "warning");
        return;
      }
      // status
      const alive = await proxyAlive(ctx && ctx.signal);
      const hb = heartbeat();
      const cur = ctx && ctx.model;
      const onVacant = !!(cur && cur.provider === PROVIDER);
      const lines = [
        "Vacant status（這個 session）",
        "  模型      " + (cur ? cur.provider + "/" + cur.id : "－") + (onVacant ? "  ✓ 經過 Vacant" : "  **✗ 不經過 Vacant**"),
        "  proxyd    " + PROXY + "  在聽：" + (alive.listening ? "是（/v1/models → " + alive.status + "）" : "**否**（" + (alive.error || "") + "）"),
        "  通數      " + (hb ? "requests_seen=" + hb.requests_seen + "（機器層級的總量，不是這個 session 的）" : "－ 沒有 heartbeat"),
        "  模型清單  " + modelSourceText(),
        "  掛鉤日誌  " + hookLog + "（" + hookLines() + " 筆）",
        "  閘門      " + gateSnapText(),
        "  回饋      " + gateFeedbackText(),
        "  最後裁決  " + (gate.last ? gate.last.settle_verdict + "（" + gate.last.stop_reason + "）wire " +
                           gate.last.requests_seen + " 通　收據 " + gate.last.run_dir : "－"),
        "  ⚠ 互動模式的裁決不擋檔案（標記不是攔截）；agent 刪得掉這支 extension，/vacant off 就沒有閘門。",
      ];
      notify(ctx, lines.join("\n"), onVacant && alive.listening ? "info" : "warning");
    },
  });

  // ── 掛鉤七事件（與 2026-09-20 A 級那一跑同一組）＋ 預設開 ───────────────────
  pi.on("session_start", async (event, ctx) => {
    fire("session_start", { source: "pi-extension", reason: event && event.reason });
    // 閘門的驗收快照要在**這個 session 的第一輪之前**拍（G3）；/vacant off 之下也拍，
    // 之後 /vacant on 才有快照可用（off 的那一段本來就不判）。
    if (GATE_ON) await gateSnapshot(ctx, "session_start");
    if (enabled) {
      const alive = await proxyAlive(ctx && ctx.signal);
      if (!alive.listening) {
        notify(ctx, "Vacant：常駐 proxyd " + PROXY + " **沒在聽**。模型仍會指到它 ⇒ 會 connection refused（fail-closed，不會偷偷直連）。看 `vacant possess status`。", "error");
      }
      if (UPSTREAM_IS_SINK) {
        notify(ctx, "Vacant：裝機時沒找到你的模型端點 ⇒ proxyd **沒有真上游**，每一通模型呼叫都會被擋（502，fail-closed，不會偷偷直連）。修法：`vacant uninstall` 後 `vacant install --agent pi --upstream openai=<你的端點>`；暫時要用原模型打 /vacant off。", "error");
      } else {
        if (!BORROWED) {
          notify(ctx, "Vacant：models.json 裡沒有 baseUrl 等於 " + UPSTREAM + " 的 provider ⇒ 送的是佔位金鑰；上游要金鑰就會 401。", "warning");
        }
        if (MODEL_SOURCE === "default") {
          notify(ctx, "Vacant：provider「" + PROVIDER + "」的模型清單是猜的（只有 " + DEFAULT_MODEL + "）——models.json 裡 baseUrl 等於 " + UPSTREAM + " 的 provider 沒有 `models`，裝機時不帶金鑰的探測也沒拿到清單。你的上游沒有這個 id 就每一通 404；修法：在那個 provider 的 `models` 列出你用的模型。", "warning");
        }
      }
      await switchOn(pi, ctx, "session_start");
    }
    if (GATE_ON) {
      const s = gate.snap;
      const lvl = (!s || !s.ok || s.disabled) ? "error" : (s.snapshot_dir ? "info" : "warning");
      notify(ctx, "Vacant 閘門：" + gateSnapText() + "\n  回饋：" + gateFeedbackText() +
                  "\n  ⚠ 裁決不擋檔案（標記不是攔截）；agent 刪得掉這支 extension，/vacant off 就沒有閘門。", lvl);
    }
  });
  pi.on("before_agent_start", async (event, ctx) => {
    // 起點要在 user_prompt_submit **之前**記（那一筆的時間要落在這一輪的窗裡，對帳才數得到）
    if (GATE_ON && enabled) await gateBegin(ctx);
    fire("user_prompt_submit", { source: "pi-extension" });
  });
  pi.on("tool_call", (event) => {
    fire("pre_tool_use", { tool_name: event && event.toolName, tool_input: (event && event.input) || {} });
  });
  pi.on("tool_result", (event) => { fire("tool_result", { tool_name: event && event.toolName }); });
  pi.on("before_provider_request", () => { fire("before_provider_request", {}); });
  pi.on("model_select", (event) => {
    // 使用者用 /model／Ctrl+P 切換（event.source＝"set"／"cycle"／"restore"）。**留痕，不擋。**
    // 不變式：每一次轉換（任一方向）恰好一筆——
    //   · 切離 vacant ⇒ vacant_off；/vacant off 自己寫過（offInProgress）⇒ 跳過。
    //   · 切回 vacant ⇒ vacant_on；switchOn 自己會寫（onInProgress）⇒ 跳過。
    //     少了這條，Ctrl+P 切走再切回來，日誌會一路說「off」而呼叫其實又經過 Vacant 了（實測）。
    //   · vacant↔vacant（換 vacant 底下的模型）、別家↔別家 不是轉換 ⇒ 不寫。
    const m = event && event.model;
    if (!m) return;
    const prev = event.previousModel;
    const wasVacant = prev && prev.provider ? prev.provider === PROVIDER : onVacantNow;   // null＝不知道 ⇒ 當成轉換
    const source = event.source || "model_select";
    const toVacant = m.provider === PROVIDER;
    onVacantNow = toVacant;
    if (toVacant) {
      if (onInProgress || wasVacant === true) return;
      if (prev && prev.provider) previous = { provider: prev.provider, id: prev.id };   // /vacant off 切回它
      fire("vacant_on", { source, model: m.provider + "/" + m.id,
                          from: prev && prev.provider ? prev.provider + "/" + prev.id : null });
    } else {
      if (offInProgress || wasVacant === false) return;
      fire("vacant_off", { from: PROVIDER, to: m.provider + "/" + m.id, source });
    }
  });
  pi.on("agent_end", () => { fire("stop", {}); });
  // 互動模式的閘門：文件說 agent_before_settle 是「the final actionable boundary」（見 piext.py）
  pi.on("agent_before_settle", async (event, ctx) => gateSettle(event, ctx));
  pi.on("session_shutdown", () => { fire("session_end", {}); });
}
"""


def render(*, port: int, state_dir: str, python: str | None = None,
           package_path: str = "", models: list[str] | None = None,
           default_model: str | None = None, upstream: str = "",
           upstream_is_sink: bool = False, key_from: str = "",
           pi_agent_dir: str = "") -> str:
    """把 extension 渲染成文字。**純函式**：不讀環境、不碰檔案。

    ⚠ 參數裡**沒有金鑰**，也不准加：金鑰在 pi 行程裡借（誠實邊界 7）。
    """
    py = python or sys.executable
    return _TEMPLATE % {
        "mark": MARK,
        "py": json.dumps(py),
        "hook_args": json.dumps(["-m", "vacant_network.vrun.hookcli"]),
        "pypath": json.dumps(package_path),
        "state": json.dumps(state_dir),
        "port": json.dumps(int(port)),
        "proxy": json.dumps(f"http://127.0.0.1:{int(port)}"),
        "provider": json.dumps(PROVIDER_ID),
        "models": json.dumps(list(models or []), ensure_ascii=False),
        "default_model": json.dumps(default_model or DEFAULT_MODEL),
        "upstream": json.dumps(upstream or ""),
        "upstream_is_sink": json.dumps(bool(upstream_is_sink)),
        "key_from": json.dumps(key_from or ""),
        "pi_agent_dir": json.dumps(pi_agent_dir or ""),
        "gate_args": json.dumps(["-m", "vacant_network.vrun.piext", "gate"]),
        "gate_max_rounds": json.dumps(int(GATE_DEFAULT_MAX_ROUNDS)),
        "gate_timeout_s": json.dumps(int(GATE_DEFAULT_TIMEOUT_S)),
    }


def probe_models(port: int, timeout: float = 5.0) -> list[str]:
    """裝機當下透過 proxyd 問一次 `/v1/models`，拿到就烤進 extension。

    拿不到（上游是 sink、沒開）⇒ 回空清單，**不是錯**：extension 會退回
    `DEFAULT_MODEL`／`VACANT_AGENT_MODEL`，並靠 `refreshModels` 之後再抓。
    ⚠ 本探測**不帶 Authorization** ⇒ 上游要金鑰就 401 ⇒ 也回空清單（2026-09-24 實測）。
    那時靠的是 extension 在 pi 行程裡借 `models.json` 同一個 provider 的 `models`
    （誠實邊界 9），不是這裡。
    """
    import urllib.request
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{int(port)}/v1/models?vacant_canary=install",
                timeout=timeout) as r:
            body = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:                                        # noqa: BLE001
        return []
    data = body.get("data") if isinstance(body, dict) else None
    out: list[str] = []
    for m in data or []:
        mid = m.get("id") if isinstance(m, dict) else None
        if isinstance(mid, str) and mid and mid not in out:
            out.append(mid)
    return out


# ══ 互動模式的閘門：python 端 ═══════════════════════════════════════════════
#   extension 經 `python -m vacant_network.vrun.piext gate <snapshot|begin|judge>` 呼叫，
#   stdin 一份 JSON、stdout 最後一行一份 JSON。設計與 G1–G10 見模組 docstring。
#   ⚠ 這一段**不自己發明**判準與收據：套件解析＝`gateshim.resolve_suite`、凍結＝
#     `launcher._freeze`、驗收＝`acceptance.run_suite(suite="visible")`、級別＝`attest.attest`、
#     收據＝`receipts.append_attempt／append_verdict`、驗章＝`verify_receipts`（一個字都沒改）。

def gate_run_root() -> pathlib.Path:
    """收據的根目錄：與 shim／`vacant run` 同一個慣例（`~/.vacant-run/`），**刻意不在工作區裡**。"""
    return pathlib.Path.home() / ".vacant-run"


def _safe_id(s: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(s or ""))[:64] or "norunid"


def gate_session_dir(run_id: Any, session_seq: Any) -> pathlib.Path:
    """一個 pi session 的收據目錄：`~/.vacant-run/pi_<run_id>_s<k>/`。

    `run_id` ＝ extension 每次載入時的隨機 UUID（＝掛鉤日誌檔名裡那一個）；`k` ＝ 這個
    行程裡第幾個 session（`/new`、`/resume` 會讓 `session_start` 再燒一次）。
    """
    return gate_run_root() / f"pi_{_safe_id(run_id)}_s{int(session_seq or 1)}"


def _inside(child: pathlib.Path, parent: pathlib.Path) -> bool:
    c, p = pathlib.Path(child).resolve(), pathlib.Path(parent).resolve()
    return c == p or p in c.parents


def _env_float(name: str, dflt: float) -> float:
    try:
        v = float(os.environ.get(name, "") or dflt)
    except ValueError:
        return dflt
    return v if v >= 0 else dflt


def _journal_lines(journal: Any) -> list[str]:
    """常駐 proxyd journal 的行。切法與 `attest.read_relay_calls` **逐字相同**
    （`splitlines()`）⇒ 這裡數出來的行數可以直接當它的 `relay_since`。不存在 ⇒ `[]`。"""
    if not journal:
        return []
    p = pathlib.Path(journal)
    if not p.is_file():
        return []
    try:
        return p.read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _is_probe(rec: dict) -> bool:
    """任何帶 `vacant_canary` 的請求（hookcli 的 canary、extension 的 refresh／status、
    裝機探測）——**不管是哪個 session 打的都不算模型呼叫**（G4）。"""
    from .attest import CANARY_QUERY_KEY
    return CANARY_QUERY_KEY in str(rec.get("path") or "")


def _wire_window(*, journal: Any, offset: int, hook_log: Any, run_id: str,
                 since_ts: float, wait_s: float) -> dict:
    """這一輪窗內的 journal（`offset` 之後）。**只數模型呼叫，不數任何 canary。**

    ⚠ proxyd 是在**回應送完之後**才寫索引（`wireproxy._finish`）⇒ 剛收手就讀可能少一通。
      等待目標是**本 session 掛鉤日誌**窗內的 `before_provider_request` 筆數——那是敘述不是
      證據，只拿來決定「要不要再等一下」；等到上限還對不上 ⇒ `quiesced=False`
      ＝ `lower_bound`（`launcher` 的同一個 fail-closed 語意）。
    """
    from .attest import read_hook_events
    deadline = time.time() + max(0.0, wait_s)
    while True:
        lines = _journal_lines(journal)
        recs: list[dict] = []
        for line in lines[offset:]:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                r = {"_unparsable": line[:200]}
            recs.append(r if isinstance(r, dict) else {"_unparsable": str(r)[:200]})
        model = [r for r in recs if not _is_probe(r)]
        ev = read_hook_events(hook_log, run_id=run_id, since_ts=since_ts) or []
        want = sum(1 for e in ev if e.get("event") == "before_provider_request")
        if len(model) >= want or time.time() >= deadline:
            break
        time.sleep(0.1)
    # 摘要演算法與 `wireproxy.WireProxy.wire_digest` 相同（依序的 (req sha, resp sha)），
    # 但來源是**共用 journal 的一個窗**，所以收據上的 kind 另外標（不可與 shim 的互相替代）。
    pairs = [[r.get("request_sha256"), r.get("response_sha256")] for r in model]
    return {
        "requests_seen": len(model),
        "probe_calls_excluded": len(recs) - len(model),
        "hook_provider_requests": want,
        "quiesced": len(model) >= want,
        "journal_offset_begin": offset,
        "journal_lines_at_read": len(lines),
        "journal_truncated": len(lines) < offset,
        "digest": hashlib.sha256(json.dumps(pairs, separators=(",", ":"))
                                 .encode("utf-8")).hexdigest(),
    }


def render_settle_feedback(block: str, *, gate_round: int, max_rounds: int) -> str:
    """回饋續跑那一則訊息的全文。`block` **只准是** `acceptance.render_failures(<visible 的結果>)`。

    呼叫端（`gate_judge`）負責只餵可見驗收——互動路徑本來就沒有隱藏驗收，但這條紅線
    （R534／`retry` 的 V/GT）照樣寫明、照樣有 canary 負控制（`tests/test_vrun_piext_gate.py`）。
    """
    text = (SETTLE_FEEDBACK_HEADER.format(round=gate_round, max_rounds=max_rounds)
            + "\n\n" + SETTLE_FEEDBACK_BODY.format(block=block))
    return assert_ks1_clean(text)


def gate_snapshot(req: dict) -> dict:
    """session 開頭拍驗收快照（G3）。**找不到驗收時一個檔都不寫。**

    規則逐字重用 `gateshim.resolve_suite`（`VACANT_SUITE` → `.vacant/suite`／
    `tests_visible`／`.vacant.toml`）。回傳的 `suite_sha256` 由 extension 釘在 pi 行程的
    記憶體裡；之後每一輪驗收前都拿它比對快照，對不上 ⇒ `infra_void`。
    """
    from . import gateshim, wshash
    ws = pathlib.Path(req.get("cwd") or os.getcwd()).resolve()
    sdir = gate_session_dir(req.get("run_id"), req.get("session_seq") or 1)
    out: dict[str, Any] = {
        "ok": True, "op": "snapshot", "cwd": str(ws), "session_dir": str(sdir),
        "suite_source": "none", "suite_src": None, "snapshot_dir": None,
        "suite_sha256": None, "suite_src_sha256": None, "suite_has_tests": None,
        "disabled": None, "snapshot_when": req.get("when") or "session_start",
        "snapshot_at": time.time(),
    }
    if _inside(sdir, ws):
        out["disabled"] = (
            f"收據目錄 {sdir} 在工作區 {ws} 底下：凍結工作區會把收據自己也複製進去"
            "（launcher 的同一條擋門）⇒ 這個 session 不跑閘門。在專案目錄裡開 pi，不要在 $HOME。")
        return out
    suite, source = gateshim.resolve_suite(ws)
    out["suite_source"] = source
    if suite is None:
        return out
    snap = sdir / "suite"
    if snap.exists():
        shutil.rmtree(snap)
    snap.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(suite, snap)
    out.update(suite_src=str(pathlib.Path(suite).resolve()), snapshot_dir=str(snap),
               suite_sha256=wshash.tree_hash(snap),
               suite_src_sha256=wshash.tree_hash(suite),
               suite_has_tests=any(snap.glob("test_*.py")))
    return out


def gate_begin(req: dict) -> dict:
    """使用者送出 prompt：記這一輪的起點。**時間先取、journal 後數**（窗只會多含不會漏）。"""
    from . import wshash
    ts = time.time()
    out: dict[str, Any] = {"ok": True, "op": "begin", "ts": ts,
                           "journal_offset": len(_journal_lines(req.get("journal"))),
                           "ws_start_sha256": None}
    if req.get("suite_present"):
        # 沒有驗收就不算樹雜湊：互動 session 常在大目錄裡開，沒有東西要綁的時候不付這個成本
        out["ws_start_sha256"] = wshash.tree_hash(
            pathlib.Path(req.get("cwd") or os.getcwd()).resolve())
    return out


#: 互動閘門的 stop_reason 封閉集合＝launcher 那一組＋三個只有這條路會有的 infra 原因。
GATE_EXTRA_STOP_REASONS = frozenset({"suite_snapshot_changed", "gate_window_unknown",
                                     "gate_sandbox_error"})


def _gate_notify(*, sv: str, stop: str | None, rs: int, failures: str,
                 result: dict | None, continue_req: bool, rnd: int, max_rounds: int,
                 suite_drift: bool | None, attestation: dict | None,
                 infra: str | None, run_dir: pathlib.Path, wire: dict) -> dict:
    """給使用者看的那幾行（TUI notify／print 模式 stderr）。**失敗原文只來自可見驗收。**"""
    score = (f"{result.get('passed')}/{result.get('total')}" if result else "－")
    head = {
        "pass": f"Vacant 閘門：✓ 可見驗收全過（{score}）",
        "fail": (f"Vacant 閘門：✗ 拒交裁決（{stop}，可見驗收 {score}）"
                 "——互動模式不擋檔案：工作區裡的東西還在，這是標記不是攔截"),
        "ungated": ("Vacant 閘門：沒有驗收可跑 ⇒ accepted=null（**不是通過**）；"
                    "之後每一輪同樣落收據、不再逐輪通知（/vacant status 看最後一輪）"),
        "no_mediation": ("Vacant 閘門：⚠ 這一輪 wire 0 通——沒有任何模型呼叫經過常駐 proxyd "
                         f"⇒ 裁決**不可歸因**（stop_reason={stop}；shim 那條的 23）"),
        "infra_void": f"Vacant 閘門：⚠ infra_void（{stop}）：{infra} ⇒ 這一輪**沒有裁決**",
    }[sv]
    lines = [head]
    if sv == "fail" and stop == "no_suite":
        lines.append("  找到驗收目錄但裡面沒有 test_*.py ⇒ 拒交（fail-closed，同 launcher）")
    if failures and sv in ("fail", "no_mediation"):
        blk = failures if len(failures) <= 1200 else failures[:1200] + "…"
        lines.append("  " + blk.replace("\n", "\n  "))
    if continue_req:
        lines.append(f"  ↻ 已把**可見驗收**的失敗回饋給 agent，要求續跑一次（第 {rnd + 1}/{max_rounds} 輪）")
    if suite_drift:
        lines.append("  ⚠ 驗收來源在 session 開頭之後被改過——這一輪照樣用開頭的快照判（suite_drift=true）")
    if not wire.get("quiesced"):
        lines.append("  ⚠ wire 計數是下界：proxyd 的 journal 還沒對上本 session 掛鉤的呼叫筆數")
    if attestation and attestation.get("tier") is not None and not attestation.get("attested"):
        lines.append(f"  未認證（級別 {attestation.get('tier')}）：{attestation.get('tier_sentence')}")
    if sv != "infra_void" or (run_dir / f"receipts_{GATE_ARM}.ndjson").exists():
        lines.append(f"  wire {rs} 通　收據 {run_dir}")
    level = {"pass": "info", "fail": "warning", "ungated": "warning",
             "no_mediation": "warning", "infra_void": "error"}[sv]
    return {"text": "\n".join(lines), "level": level}


def gate_judge(req: dict) -> dict:
    """一次 `agent_before_settle` 評估 ⇒ 一個 run 目錄、一筆 `ws_attempt`＋一筆 `ws_verdict`。

    回給 extension：`settle_verdict`、要不要續跑（`continue`）與回饋全文、給人看的通知、
    這一次的終點（下一次評估的起點）。**要不要續跑由這裡決定並簽進收據**，extension 照做。
    """
    from . import acceptance, gateshim, launcher, receipts, wshash
    from . import attest as attestmod
    from .sandbox import SandboxInfraError, make_sandbox
    from ..crypto import pub_to_hex
    from ..identity import Identity
    from ..logbook import Logbook
    from ..memory import KS1Violation

    ws = pathlib.Path(req.get("cwd") or os.getcwd()).resolve()
    run_id = str(req.get("run_id") or "norunid")
    sseq = int(req.get("session_seq") or 1)
    pseq = int(req.get("prompt_seq") or 1)
    rnd = int(req.get("gate_round") or 1)
    feedback = req.get("feedback") if req.get("feedback") in GATE_FEEDBACK_MODES else "off"
    max_rounds = max(1, int(req.get("max_rounds") or 1)) if feedback == "revise" else 1
    sdir = pathlib.Path(req.get("session_dir") or gate_session_dir(run_id, sseq))
    task_id = f"pi_{_safe_id(run_id)}_s{sseq}_p{pseq:03d}_r{rnd}"
    run_dir = sdir / f"p{pseq:03d}_r{rnd}"
    if run_dir.exists():                 # 同一個 (prompt, round) 評估兩次：各留各的，不疊進同一份 rows
        run_dir = run_dir.with_name(f"{run_dir.name}_{int(time.time() * 1000)}")
    arm = GATE_ARM
    _suite_in, _begin_in = req.get("suite"), req.get("begin")
    suite: dict | None = _suite_in if isinstance(_suite_in, dict) else None
    sd: dict = suite or {}
    begin: dict = _begin_in if isinstance(_begin_in, dict) else {}
    outcome = req.get("outcome")
    hook_log, journal = req.get("hook_log"), req.get("journal")
    if _inside(run_dir, ws):
        return {"ok": False, "op": "judge",
                "error": f"收據目錄 {run_dir} 在工作區 {ws} 底下（G9）"}
    run_dir.mkdir(parents=True, exist_ok=True)

    infra: str | None = None
    stop: str | None = None
    offset = begin.get("journal_offset")
    since_ts = begin.get("ts")
    if (not isinstance(offset, int) or isinstance(offset, bool)
            or not isinstance(since_ts, (int, float)) or isinstance(since_ts, bool)):
        infra, stop = "這一輪沒有可用的起點（journal 行數／時間）⇒ 窗定不出來", "gate_window_unknown"
        offset, since_ts = 0, time.time()
    wire = _wire_window(journal=journal, offset=int(offset), hook_log=hook_log,
                        run_id=run_id, since_ts=float(since_ts),
                        wait_s=_env_float("VACANT_PI_GATE_WIRE_WAIT_S", GATE_WIRE_WAIT_S))
    rs = int(wire["requests_seen"])

    # ── 驗收快照：雜湊要對得上 session 開頭釘在 pi 記憶體裡的那一個（G3）────────
    snap = pathlib.Path(sd["snapshot_dir"]) if sd.get("snapshot_dir") else None
    suite_now: str | None = None
    suite_drift: bool | None = None
    if snap is not None:
        suite_now = wshash.tree_hash(snap) if snap.is_dir() else None
        src = sd.get("src")
        if src and pathlib.Path(src).is_dir():
            suite_drift = wshash.tree_hash(pathlib.Path(src)) != sd.get("src_sha256")
        elif src:
            suite_drift = True           # 來源整個不見了也是漂移
        if infra is None and suite_now != sd.get("sha256"):
            infra = (f"驗收快照的樹雜湊對不上 session 開頭釘在 pi 記憶體裡的那一個"
                     f"（{str(sd.get('sha256'))[:12]}… → {str(suite_now)[:12]}…）"
                     "⇒ 快照被動過")
            stop = "suite_snapshot_changed"

    # ── 凍結 → 驗收（有驗收才凍結：沒有東西要綁的時候不付複製整個 cwd 的成本）───────
    ws_start = begin.get("ws_start_sha256")
    ws_end: str | None = None
    result: dict | None = None
    accepted: bool | None = None
    failures = ""
    frozen_dir: pathlib.Path | None = None
    if infra is None and snap is not None:
        frozen_dir = run_dir / f"_frozen_{arm}"
        frozen, live_after = launcher._freeze(ws, frozen_dir)
        ws_end = frozen
        if frozen != live_after:
            infra, stop = f"frozen={frozen} live={live_after}", "ws_moved_during_freeze"
    if infra is None:
        if snap is None:
            stop, accepted = "ungated", None
        elif not any(snap.glob("test_*.py")):
            stop, accepted = "no_suite", False
        else:
            try:
                sb, _meta = make_sandbox("none", workdir=run_dir)   # 同 shim（sandbox_name="none"）
                result = acceptance.run_suite(
                    sb, frozen_dir, snap, suite="visible", task_id=task_id,  # type: ignore[arg-type]
                    verify_root=run_dir / "_verify",
                    timeout_s=_env_float("VACANT_TEST_TIMEOUT", 30.0))
            except SandboxInfraError as exc:
                infra, stop = repr(exc), "gate_sandbox_error"
            else:
                (run_dir / f"visible_{arm}.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                accepted = bool(result.get("all_pass"))
                failures = "" if accepted else acceptance.render_failures(result)
                stop = ("visible_pass" if accepted else
                        "attempts_exhausted" if (max_rounds > 1 and rnd >= max_rounds)
                        else "visible_fail")
    # 凍結副本預設刪掉：互動 session 一輪一份，留著就是 O(輪數×工作區) 的磁碟（樹雜湊已經綁進收據）
    keep_frozen = os.environ.get("VACANT_PI_GATE_KEEP_FROZEN", "") in ("1", "true", "yes")
    if frozen_dir is not None and frozen_dir.exists() and not keep_frozen:
        shutil.rmtree(frozen_dir, ignore_errors=True)

    # ── 要不要續跑（**這裡決定、簽進收據**；extension 照做）─────────────────────
    can_cont = req.get("can_continue") is True
    why_not: list[str] = []
    if feedback != "revise":
        why_not.append("feedback_off")
    if infra is not None:
        why_not.append("infra_void")
    if stop != "visible_fail":
        why_not.append(f"stop_reason={stop}")
    if rnd >= max_rounds:
        why_not.append("max_rounds")
    if outcome != "completed":
        why_not.append(f"outcome={outcome}")        # 文件：error／aborted 是 hard exit
    if not can_cont:
        why_not.append("can_continue=false")
    if rs == 0:
        why_not.append("requests_seen=0")           # 不可歸因的裁決不拿來驅動 agent
    continue_req = not why_not
    feedback_text: str | None = None
    if continue_req:
        try:
            feedback_text = render_settle_feedback(failures, gate_round=rnd,
                                                   max_rounds=max_rounds)
        except KS1Violation as exc:
            # 鐵律 1：違反＝run 作廢（責任修辭可能是從客戶測試的訊息帶進來的）
            infra, stop, continue_req = repr(exc), "ks1_violation", False
            why_not.append("ks1_violation")

    # ── 互動裁決（不是退出碼）。`no_mediation` 蓋 pass／fail／ungated，唯獨不蓋 infra_void ──
    if infra is not None:
        sv = "infra_void"
    elif rs == 0:
        sv = "no_mediation"
    elif stop == "ungated":
        sv = "ungated"
    elif accepted is True:
        sv = "pass"
    else:
        sv = "fail"
    assert sv in SETTLE_VERDICTS
    assert stop in (launcher.STOP_REASONS | GATE_EXTRA_STOP_REASONS), stop

    # ── 級別：由探針決定（與 launcher 同一支 `attest.attest`）；只影響級別欄位，不蓋 sv ──
    a_mode = gateshim.attest_mode()
    attestation: dict | None = None
    if a_mode != "off":
        try:
            attestation = attestmod.attest(
                agent="pi", run_id=run_id, hook_log=hook_log,
                # 呼叫本函式的就是那支 extension ⇒ 掛鉤「裝過」；燒沒燒照樣只讀日誌（§三-1）
                install_attempted=True,
                relay_index=journal, relay_since=int(offset), hook_since_ts=float(since_ts))
        except Exception as e:                                   # noqa: BLE001
            attestation = {"error": f"{type(e).__name__}: {e}", "tier": None,
                           "attested": None}
    tier = (attestation or {}).get("tier")

    session = {"run_id": run_id, "session_seq": sseq, "prompt_seq": pseq,
               "gate_round": rnd, "max_rounds": max_rounds,
               "prev_receipt_head": req.get("prev_receipt_head")}
    count_sem = "shared_window" if wire["quiesced"] else "lower_bound"
    summary: dict[str, Any] = {
        # ── 與 launcher summary 同名同義的欄位（`verify_receipts` 與人都照同一份讀法）──
        "task_id": task_id, "arm": arm, "vacant": 1, "argv": None,
        "workspace": str(ws), "proxy_url": req.get("proxy"), "env": None,
        "ws_start_sha256": ws_start, "ws_end_sha256": ws_end,
        "agent_rc": None, "agent_timed_out": None,       # 沒有行程結束這回事 ⇒ 沒量到
        "requests_seen": rs, "wire_by_protocol": None,
        "accepted": None if infra else accepted,
        "refused": (None if infra else
                    (stop == "no_suite") if stop in ("no_suite", "ungated")
                    else (not accepted)),
        "stop_reason": stop, "infra_void": infra,
        "visible_passed": result.get("passed") if result else None,
        "visible_total": result.get("total") if result else None,
        "verdict_sha256": result.get("result_sha256") if result else None,
        "verdict_hash": None,
        "retry": "revise" if feedback == "revise" else "none",
        "max_attempts": max_rounds, "attempts_used": rnd, "attempts": [],
        "feedback_into": "pi_custom_message" if feedback == "revise" else None,
        "failures": failures,
        "model_wire": {
            "requests_indexed": rs, "count_semantics": count_sem,
            "wire_quiesced": wire["quiesced"],
            "probe_calls_excluded": wire["probe_calls_excluded"],
            "hook_provider_requests": wire["hook_provider_requests"],
            "journal": journal, "journal_offset_begin": wire["journal_offset_begin"],
            "journal_lines_at_read": wire["journal_lines_at_read"],
            "journal_truncated": wire["journal_truncated"],
            "note": ("常駐 proxyd 的 journal 是整台機器共用的 ⇒ 這是這一輪時間窗內的非 canary "
                     "通數，同機器別的 session／agent 同時打會算進來（上偏）；`lower_bound` ⇒ "
                     "journal 還沒對上本 session 掛鉤的呼叫筆數（下偏）。任何 canary 都不算。"),
        },
        "attestation": attestation,
        # ── 互動閘門專屬 ─────────────────────────────────────────────────
        "run": GATE_RUN_TAG, "trigger": SETTLE_TRIGGER, "settle_outcome": outcome,
        "settle_verdict": sv, "blocks_delivery": False,
        "session": session,
        "suite": {"source": sd.get("source") or "none",
                  "src": sd.get("src"),
                  "snapshot_dir": sd.get("snapshot_dir"),
                  "sha256_pinned": sd.get("sha256"),
                  "sha256_now": suite_now, "drift": suite_drift},
        "continuation": {"requested": continue_req, "why_not": why_not,
                         "feedback_sha256": (hashlib.sha256(feedback_text.encode("utf-8"))
                                             .hexdigest() if feedback_text else None),
                         "feedback_text": feedback_text},
        "frozen_kept": bool(keep_frozen and frozen_dir is not None),
    }

    # ── 落盤：rows ＋ run_<ARM>.json ＋（不是 infra_void 才有的）簽章鏈 ─────────────
    row = {k: summary[k] for k in
           ("task_id", "arm", "vacant", "ws_start_sha256", "ws_end_sha256",
            "agent_rc", "requests_seen", "accepted", "refused", "stop_reason")}
    row.update(infra_void=infra, retry=summary["retry"], attempts_used=rnd,
               max_attempts=max_rounds, feedback_into=summary["feedback_into"],
               run=GATE_RUN_TAG, settle_verdict=sv)
    with (run_dir / "rows.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    if infra is None:
        # 一把一次性金鑰、簽完即丟（私鑰不落盤，RECORD_SPEC §7；G8）
        ident, book = Identity.generate(), Logbook()
        common = dict(run=GATE_RUN_TAG, trigger=SETTLE_TRIGGER,
                      conversation_digest_kind="wire_bytes_shared_journal_window",
                      requests_seen=rs, retry=summary["retry"], max_attempts=max_rounds,
                      agent_rc=None, session_run_id=run_id, session_seq=sseq,
                      prompt_seq=pseq, settle_outcome=outcome)
        # `type: ignore[arg-type]`（三處）：沒有驗收的那一輪**不凍結、不算樹雜湊**（G9）⇒
        # `ws_*` 是 `None`＝沒量到（鐵律 3 的三態），不是空字串。`receipts` 的註記只寫了
        # `str`，但它只檢查欄位**存在**；把 None 換成假雜湊才是說謊。
        receipts.append_attempt(
            book, ident, task_id=task_id, arm=arm, attempt=rnd, gate_round=rnd,
            ws_sha256=ws_end,  # type: ignore[arg-type]
            verdict_sha256=summary["verdict_sha256"],
            conversation_sha256=wire["digest"], accepted=accepted,
            ws_start_sha256=ws_start, stop_reason=stop, argv_sha256=None,
            feedback_delivery=summary["feedback_into"], **common)
        att = attestation or {}
        entry = receipts.append_verdict(
            book, ident, task_id=task_id, arm=arm, accepted=bool(accepted),
            ws_start_sha256=ws_start,  # type: ignore[arg-type]
            ws_end_sha256=ws_end,  # type: ignore[arg-type]
            verdict_sha256=summary["verdict_sha256"],
            conversation_sha256=wire["digest"], stop_reason=stop,
            # `accepted` 被 `bool()` 壓成 False ⇒ 「沒量」要另一欄說（同 launcher）
            accepted_is_null=(accepted is None), attempts_used=rnd, gate_round=rnd,
            tier=att.get("tier"), attested=att.get("attested"),
            enclosure_applied=(att.get("enclosure") or {}).get("applied"),
            canary_fired=(att.get("framework_hook") or {}).get("canary_fired"),
            unexplained=(att.get("reconciled") or {}).get("unexplained"),
            attestation_sha256=launcher._attestation_digest(attestation),
            wire_count_semantics=count_sem, wire_quiesced=wire["quiesced"],
            settle_verdict=sv, blocks_delivery=False,
            final_for_prompt=not continue_req, continuation_requested=continue_req,
            feedback_sha256=summary["continuation"]["feedback_sha256"],
            suite_source=summary["suite"]["source"],
            suite_sha256=summary["suite"]["sha256_pinned"], suite_drift=suite_drift,
            prev_receipt_head=req.get("prev_receipt_head"), **common)
        summary["verdict_hash"] = entry.hash()
        book.save(run_dir / f"receipts_{arm}.ndjson")
        (run_dir / f"receipts_{arm}.pub.json").write_text(json.dumps(
            {"vacant_id": ident.vacant_id, "pub_hex": pub_to_hex(ident.pub)},
            ensure_ascii=False), encoding="utf-8")
    (run_dir / f"run_{arm}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── possess.json（與 shim 同名同形；互動專屬的欄位另外加）／C 級拒發收據 ──────────
    extra = {
        "possess_agent": "pi", "path": "extension", "trigger": SETTLE_TRIGGER,
        "suite_source": summary["suite"]["source"], "suite_dir": summary["suite"]["src"],
        "gate": "ran" if snap is not None else "skipped",
        "requests_seen": rs, "stop_reason": stop, "accepted": summary["accepted"],
        # ⚠ 沒有退出碼（NOTE §3.3-2）：互動裁決在 `settle_verdict`，不可以讀成 shim 的碼
        "shim_exit": None, "settle_verdict": sv, "blocks_delivery": False,
        "argv": None, "real_binary": None, "cwd": str(ws),
        "cfg_sweep": None, "cfg_cleanup": None,
        "agent_posture": {"layer": "extension（使用者常駐的 pi 設定）",
                          "sandbox_mode": None, "approval_policy": None, "flags": [],
                          "note": "互動 pi 的沙箱／approval 姿態這條路讀不出來 ⇒ 沒量到（不是「沒有」）"},
        "attestation": attestation, "attest_mode": a_mode, "tier": tier,
        "attested": (attestation or {}).get("attested"),
        "session": session, "receipt_head": summary["verdict_hash"],
    }
    if a_mode == "fail" and attestation is not None and tier == attestmod.TIER_C:
        (run_dir / "NOT_CERTIFIED.json").write_text(json.dumps({
            "not_a_receipt": True,
            "why": "C 級＝既沒有圍牆也沒有掛鉤 ⇒ 這一輪的紀錄不足以究責（照 shim：裁決 §三-2）。",
            "tier": tier, "tier_reasons": (attestation or {}).get("tier_reasons"),
            "attestation": attestation, "possess_json_written": False,
            "diagnostics": {k: extra[k] for k in ("possess_agent", "suite_source",
                                                  "requests_seen", "stop_reason",
                                                  "settle_verdict", "cwd")},
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        (run_dir / "possess.json").write_text(
            json.dumps(extra, ensure_ascii=False, indent=2), encoding="utf-8")

    note = _gate_notify(sv=sv, stop=stop, rs=rs, failures=failures, result=result,
                        continue_req=continue_req, rnd=rnd, max_rounds=max_rounds,
                        suite_drift=suite_drift, attestation=attestation, infra=infra,
                        run_dir=run_dir, wire=wire)
    return {
        "ok": True, "op": "judge", "task_id": task_id, "run_dir": str(run_dir),
        "settle_verdict": sv, "stop_reason": stop, "accepted": summary["accepted"],
        "requests_seen": rs, "tier": tier,
        "attested": (attestation or {}).get("attested"),
        "receipt_head": summary["verdict_hash"],
        "continue": continue_req, "feedback_text": feedback_text if continue_req else None,
        "visible_passed": summary["visible_passed"],
        "visible_total": summary["visible_total"], "suite_drift": suite_drift,
        "notify": note,
        # 下一次評估的起點：**這一刻**再數一次 journal（驗收那幾十秒裡別人打的不算進任何一輪）
        "end": {"ts": time.time(), "journal_offset": len(_journal_lines(journal)),
                "ws_start_sha256": ws_end},
    }


_GATE_OPS = {"snapshot": gate_snapshot, "begin": gate_begin, "judge": gate_judge}


def gate_main(argv: list[str]) -> int:
    """`python -m vacant_network.vrun.piext gate <op>`：stdin 一份 JSON，stdout 最後一行一份 JSON。

    **永遠回 0、永遠印一行 JSON**（壞掉就是 `{"ok": false, "error": …}`）：extension 端
    用它分辨「閘門判了」與「閘門壞了」，兩者都不可以弄死 agent（hookcli 誠實邊界 3 的同一條）。
    stdout 在工作期間導到 stderr ⇒ 任何一行雜訊都不會蓋掉那一行 JSON。
    """
    op = argv[0] if argv else ""
    try:
        raw = sys.stdin.read()
        req = json.loads(raw) if raw.strip() else {}
        if not isinstance(req, dict):
            req = {}
    except (OSError, ValueError):
        req = {}
    fn = _GATE_OPS.get(op)
    out: dict[str, Any]
    if fn is None:
        out = {"ok": False, "op": op, "error": f"不認得的 op {op!r}（{sorted(_GATE_OPS)}）"}
    else:
        try:
            with contextlib.redirect_stdout(sys.stderr):
                out = fn(req)
        except BaseException as e:                               # noqa: BLE001
            out = {"ok": False, "op": op, "error": f"{type(e).__name__}: {e}"}
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if a[:1] == ["gate"]:
        return gate_main(a[1:])
    print("用法：python -m vacant_network.vrun.piext gate <snapshot|begin|judge> < req.json"
          "（由 pi extension 呼叫）", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
