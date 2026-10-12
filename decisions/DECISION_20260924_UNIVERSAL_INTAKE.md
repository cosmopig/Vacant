# DECISION 2026-09-24：通用收件口——判準搬到契約與收件端，模型通道降為選配

**觸發**：人類 2026-09-24，附 22 頁外部質疑報告（`VACANT_critical_report_20260924.pdf`）：

> 以下的問題我要你正視且解決，並且我們必須要做出一個真正的 vacant 產品。現在的 vacant 有很多問題，
> 主要就是他太針對特定的狀態了……如果無法把它放在真實的 agent 平台上我們再有用也沒用，
> 所以或許也是時候要做取捨……做出可以真正意義上適配絕大多數的 agent 平台的 vacant，
> 至少 pi、Claude Code、opencode、codex 這四種最好都要可以適配，我們一定有找出共通的地方去解決。

**一句話**：Vacant 的通用性放在**任務契約 → 隔離區 → 逐項取證 → 裁決 → 批准 → 收件端放行 → 讀回 → 帳本**
這條路上；四個 agent 的共通面是**行程＋工作區、shell、技能、生命週期掛鉤**，不是模型通道。
模型中介保留為**選配觀測**，從此不再決定收件。

本檔**部分取代** `DECISION_20260920_COMPLETE_MEDIATION.md`（見 §六），其餘既有裁決不動。

---

## 一、報告的問題 → 這次做了什麼

| 報告 | 問題 | 處理 | 位置 |
|---|---|---|---|
| §03 P0 | 部分結果被算全過（分母＝回報筆數） | **修掉**：父行程先用 AST 定宣告清單、driver 印結束標記、對帳（缺 → `incomplete`、重複／清單外 → `protocol`、rc≠0 或無結束標記 → 檔案層級失敗）；`all_pass` 另外要求每檔 `complete`；整份套件先讀進記憶體並雜湊，**每個測試檔各拿一份新拷貝**（前一檔的候選碼改不到後一檔）；`return False`／coroutine 不再算過 | `vrun/acceptance.py`、`tests/test_acceptance_completeness.py`（報告附錄 B 五列全數搬進 repo，走真的 `run_suite`） |
| §03 | 惡意候選碼與 driver 同直譯器、nonce 在 argv | **不宣稱修掉**：這層防意外，不防惡意；兩種層級不混成一個修補（docstring 明寫），惡意那層在 `suitespec.py` 的資料化規約 | 同上 |
| §04 | 判了拒交 ≠ 阻止交付 | 新增**收件端**：只有經過 `vacant release` 的版本進目的端，而且收件端自己重驗簽章、契約雜湊、隔離區雜湊、批准綁定、nonce、撤回狀態，寫入後**讀回** | `intake/recipients.py` |
| §05 | 模型流量完整、簽章有效、評判可信混在一起；自我認證簽章；infra_void 不上鏈 | 收件口完全不看模型流量；簽章者必須在**收件端自己的**簽章者清單上；每個事件（含 `infra_void`）都上帳本，終態報表的分母＝開過的任務 | `intake/keys.py`、`intake/ledger.py` |
| §06 | world-cloud 相信回傳者給的 verdict、`false‖null`、dev-token 預設 | 同形狀的正確版本：HTTP 收件口，提交者只能提交（`verdict/accepted/matched/status` 一律忽略並回報），四態保留，**沒有 token 不啟動**，公開路徑只讀已放行版本 | `intake/server.py`、`tests/test_intake_server_cli.py`（world-cloud 本身不在本 repo，見 §十） |
| §05／R9 | 包覆後 agent 已不是原本那個（MCP 消失、工作區錯） | **不再搬家使用者設定**；每一跑用各家加法式入口（`--settings`、`-e`、`OPENCODE_CONFIG_CONTENT` 併入 `plugin`、`-c`）；常駐安裝鍵層級可逆；工作區 `PWD` 修正（OpenCode 寫錯目錄的真因） | `adapters/`、`vrun/launcher.py` |
| §08 | 誰說了算 | 主張帶 `authority`：requirement／fact／quality／approval；**事實主張只收獨立證據**（agent 自己交的資料 ⇒ PASS 降 UNKNOWN）；`suitespec` 的 2+2=5 改寫為「規約權威≠事實權威」 | `intake/policy.py`、`suitespec.py` |
| §10 | 自主驗證 ≠ 自主批准 | 驗證器只產生逐項結果；批准是另一把金鑰簽的、綁定內容與目的端的文件 | `intake/approval.py` |
| §11 | 閉源不是一種情況 | 四種接法由強到弱：行程＋工作區／shell／技能／掛鉤；完全閉源的成果走 HTTP 收件口 | `adapters/`、`intake/server.py` |
| §12 | 批准綁定、防重播、冪等 | 批准綁 task／contract／artifact／destination／action／expiry／nonce；同一版本已在目的端 ⇒ 只讀回不重做 | `intake/approval.py`、`intake/recipients.py` |
| §15 | 驗證者被成果裡的指示騙 | 內建驗證器全是確定性程式，不讀指示；測試裡放了注入字串 | `tests/test_intake_core.py` |
| §16 | 必須能推翻自己的測試 | 換版、重播、過期、撤回後重送、契約改版、隔離區被改、不受信任簽章、驗證器崩潰、必要主張缺結果、事實證據不獨立——**每一條都有一個會紅的測試** | `tests/test_intake_core.py` |

---

## 二、任務契約（`intake/contract.py`）

版本固定、以 canonical JSON 的 sha256 識別；**未知欄位一律拒絕**（vacant_hm `GATE_MUST_EXIST_R146`：
拼錯一個門檻鍵，檢查就安靜消失）。`inputs` 以 sha256 釘住委託者的原始資料與驗收套件
（`vacant contract lock`），驗證時重算，對不上 ⇒ 該項 UNKNOWN。

驗證原語（`intake/verifiers.py`）：`exists`、`forbid_paths`、`sha256_pin`、`text`、`json_schema`、
`csv_total`（數值重算）、`citations_resolve`（引用對應＋引文在快照中逐字出現）、`python_checks`
（既有驗收，含 P0 修正）、`command`（委託者自己的命令：0/1/3/其他 ⇒ PASS/FAIL/CONFLICT/UNKNOWN）、
`review`（簽過的人工審查，綁成果雜湊與契約雜湊，分歧 ⇒ CONFLICT；本機金鑰簽的標 `same_account`）。
**內建驗證器壞掉（例外、參數錯）一律 UNKNOWN。** 例外：`command` 只看退出碼——委託者的 python 腳本
自己崩潰也是 exit 1，會被記成 FAIL；腳本要把內部錯誤轉成 1／3 以外的碼（docstring 與 summary 都寫了）。

## 三、一條流程（`intake/flow.py`）

裁決規則（`intake/policy.py`，寫死、可重算）：必要主張有 FAIL ⇒ reject；否則有 CONFLICT ⇒ escalate；
否則有 UNKNOWN ⇒ hold；全 PASS ⇒ accept。品質分數不能抵銷硬條件（沒有加權平均）。
缺結果的必要主張補 UNKNOWN（分母是契約）。`coverage` 報「可判定的必要主張／全部必要主張」。

指令：`vacant contract init|lock|validate|show`、`check`（只驗不收）、`submit`、`review`、`reverify`、
`approve`、`release`、`withdraw`、`task status|verify|report`、`keys`、`intake serve`。
退出碼另開 40–45（`vacant run`／gateshim 的 20–26 語意不動）。

## 四、四個 agent 的共通面（本輪實測，`adapters/`）

| 共通面 | pi 0.87.1 | Claude Code 2.1.281 | OpenCode 1.18.32 | Codex 0.156.1 |
|---|---|---|---|---|
| headless | `pi -p --mode json` | `claude -p --output-format json` | `opencode run --format json --dir <絕對路徑>` | `codex exec --json -s workspace-write -c projects={<ws>={trust_level="trusted"}}`（不帶的話 Codex 每一跑在使用者 `config.toml` 附加一條專案信任） |
| 每一跑加掛鉤、不動使用者設定 | `-e <ext>` | `--settings`（只認最後一個；`disableAllHooks:false`） | `OPENCODE_CONFIG_CONTENT` 併入 `plugin:["file://…"]`（深合併；**不用** `OPENCODE_CONFIG_DIR`——它讓全域 `AGENTS.md` 消失） | `-c hooks.*`＋`-c hooks.state`（信任雜湊自算） |
| 工具前否決 | `tool_call` → `{block}` | `PreToolUse` → `permissionDecision:deny` | `tool.execute.before` → throw | `PreToolUse` → exit 2＋stderr |
| 交件前回饋 | `agent_before_settle` → `{entries, continue}` | `Stop` → `decision:block`（上限 8 次） | **只有互動 TUI**（`session.idle`＋SDK prompt）；`opencode run` 在第一個 idle 就結束 | `Stop` → `decision:block` |
| 工作階段結束 | `session_shutdown` | `SessionEnd`（預設 1.5 秒） | 外掛的 `dispose()`（**會被 await**；`event` 在 `run` 裡是 fire-and-forget）＋一次性旗標；子 agent 的 idle 略過 | `SessionEnd`（1–3 秒） |
| 常駐安裝 | `~/.pi/agent/extensions/vacant.ts` | `$CLAUDE_CONFIG_DIR`（預設 `~/.claude`）`/settings.json` 附加 | `~/.config/opencode/plugin/vacant.js` | `~/.codex/config.toml` 尾端區塊（掛鉤＋Codex 的 hook trust 雜湊，兩種路徑拼法） |
| 技能（放置位置 [DOC]；有沒有列給模型見證據的 skill 欄） | `~/.pi/agent/skills/vacant/` | `…/skills/vacant/` | `~/.config/opencode/skill/vacant/` | `~/.codex/skills/vacant/` |

因為工作階段結束的時限都很短，掛鉤**不同步交件**，而是起一個分離的背景行程。

**端到端量出來、改了設計的三件事**（都是「會讓人以為成立、其實不成立」的那種）：
1. 掛鉤先寫帳本時建了 verifier 金鑰卻沒登記信任 ⇒ 收件端**正確地**拒絕放行。修：`keys.ensure_local` 加鎖。
2. `vacant do` 的隔離工作區放在 `$VACANT_HOME` 底下 ⇒ pi 的全域 extension **正確地**擋下寫入。修：`~/.vacant-work`。
3. Codex 常駐安裝原本用 `profile = "vacant"` ⇒ 0.156.1 視為遺留鍵、**Codex 拒絕啟動**。修：改在 `config.toml` 尾端附加掛鉤＋信任。
   一個會讓 agent 起不來的安裝比沒裝更糟——這一格如果只做單元測試是抓不到的。

讀原始碼＋探針量出來、改了設計的另外兩件（agent 對照表，`[RUN]` 格）：
4. OpenCode 原本用 `OPENCODE_CONFIG_DIR` 當每一跑的加法層——它**同時**改掉全域 `AGENTS.md` 的讀取
   位置，使用者的全域規則會安靜地從提示裡消失（報告 §05「包覆後已不是原本那個 agent」的同一型）。
   改為把外掛併進 `OPENCODE_CONFIG_CONTENT`（使用者的值解析不了就**不注入**，不覆寫）；
   交件移到 `dispose()`（`event` 掛鉤在 `opencode run` 裡約 40 ms 後就被行程結束截斷）。
5. 常駐安裝還在時 `vacant do` 又注入一份 ⇒ pi／OpenCode／Codex 的掛鉤都是加法的，**同一事件跑兩次**。
   改為先看常駐那份在不在（`agents.persistent_hook_file`）。⚠ 對抗審查另外指出：OpenCode 在
   **只有常駐外掛**時，一次 `opencode run` 也記到兩次停止檢查（同一個 session 的 `session.idle`
   觸發不只一次）——所以輪數重複**不只**來自雙重注入。修：`opencode run` 裡不跑停止檢查
   （回饋本來就送不到），互動模式每個 session 同時只跑一個。

## 五、權威拆分與 `suitespec` 的 2+2=5

`suitespec.py` 紅線 2 改寫：`expected` 的權威是**規約權威**（純函式驗收裡 `f(2,2)==5` 是合法規約），
**不是事實權威**；不准推廣到描述外部事實的驗收。事實主張在契約裡寫 `authority="fact"`，
證據必須來自 `inputs` 釘住的獨立來源。

## 六、取代與保留

**取代**（`DECISION_20260920_COMPLETE_MEDIATION.md` 的一部分）：在新的產品路徑（`vacant do`、
`vacant install`、`vacant check/submit/release`、HTTP 收件口）裡，模型中介**不是**收件的前提；
`requests_seen == 0`、tier B/B′/C 都不影響裁決與放行。

人類 2026-09-20 的原話「vacant 的意義就是在每個處理都可以經過究責」**保留，但錨點換了**：
- `vacant release` 寫進目的端的每一個版本都經過收件端的重驗——**只有在 agent 寫不到那個目的端時**（另一個帳號、ACL、git 分支保護），才能說成「那個目的端只有這一條寫入路徑」。`dir:` 目的端在同一個帳號下是一個普通目錄（`vacant contract init` 的預設 `dir:.vacant/published` 只受工具層掛鉤保護）；
- **掛鉤有觸發工作階段結束事件**的工作階段，都在帳本上留下一個裁決（`submit_on_end`），含失敗與作廢；沒有觸發（`--bare`、pi 在 print 模式被 SIGINT、agent 拆掉掛鉤）就沒有紀錄——`vacant do` 那一條不依賴掛鉤；
- 模型呼叫層級的中介（enclosure、proxy、tier A）仍然可以開，作為觀測。

**保留不動**（CLAUDE.md 明令或實驗可比性）：`gateshim` 的 21／23 語意、`verify_receipts` 對 vrun 收據鏈的
VOID 語意、`wrap_agent.sh`、所有歸檔 run。舊的常駐模型通道安裝仍在：`vacant possess install`
或 `vacant install --observe-model`。

**文字更正**：`AGENTS.md`／README×3 的 `"tamper_proof": true` ⇒ `false`＋`tamper_evident: true`
（簽章金鑰是同一帳號下的明文檔；參考監視器三性質出自 Anderson 1972，不是 Saltzer & Schroeder 1975）。

## 七、證據

單元測試（全部離線、零模型；數字是 `pytest --collect-only` 數出來的，參數化的各算一個）：
`tests/test_acceptance_completeness.py`（P0，16）、`tests/test_intake_core.py`（30）、
`tests/test_intake_server_cli.py`（8）、`tests/test_adapters_core.py`（17）、
`tests/test_adapters_agents.py`（14）；對抗審查的回歸（§十一）：
`tests/test_intake_gate_hardening.py`（19）、`tests/test_intake_verifier_hardening.py`（30）、
`tests/test_adapters_hardening.py`（43）。合計 177。

端到端（**L-fake**：真 agent binary＋照劇本回答的假模型 `ops/intake/mock_model.py`；
Vacant 不碰模型流量）：`ops/intake/e2e_four_agents.py`，結果見
`ops/intake/evidence_20260924/SUMMARY.md` 與 `results.json`——**§十一修正之後**的程式碼跑的：
四個 agent 都是「錯的版本沒被寫進目的端、對的版本放行且讀回一致、契約禁止的 `git push` 在工具層被擋、
效果沒發生（常駐安裝與每一跑注入兩條路都量）、解除安裝後使用者設定逐位元還原、每一跑注入之後使用者設定
也沒被寫」；交件前回饋送到模型手上：pi／Claude Code／Codex 是，OpenCode 否；Vacant 技能的描述出現在
模型收到的請求裡：四個都是。

## 八、口徑

✅ 可以講：
- 「pi、Claude Code、OpenCode、Codex 四個都接得上：在**我們的離線量測**（真 agent＋假模型）裡，
  不合格的版本沒有出現在收件端的目的地，合格的版本出現了，而且目的端讀回一致。」
- 「收件口不需要看模型流量。」
- 「裝了 Vacant 之後使用者原本的設定還在；解除安裝後逐位元還原（使用者沒改過的情況）。」

❌ 不可以講：
- 「agent 不能作惡／不會被繞過」——掛鉤 agent 拆得掉、shell 能繞過字串規則；保證只在收件端。
- 「Vacant 讓 agent 做得更好」——本輪的回饋效果是**劇本**寫的（假模型看到回饋就改），不是模型能力。
- 「OpenCode 有交件前回饋」——`opencode run` 沒有；只有互動 TUI 有機會（未量）。
  - 補記 2026-09-25：互動 TUI 量過了，**有**（L-fake，`ops/accountability/e2e_tui.py`）；`vacant do` 也有（下一次嘗試）。
    可以講的是「OpenCode 的互動 TUI 與 `vacant do` 有交件前回饋，`opencode run` 沒有」——不帶條件的那句仍然不可以講。
- 「四個 agent 真模型都成立」——本輪是 L-fake。

## 九、文獻落點（專案自己的文獻卡，研究筆記 04–07）

- 收件端簽收：Figuera 2026 *Notarized Agents*（A 級）——由接收方簽、承認「agent 不呼叫就沒有收據」的極限。
- 分權與無繞過旗標：GitHub Agentic Workflows staged permissions ＋ A5 被否證的預設（A 級）。
- 判決不能撤回效果：OpenAI Agents SDK JS guardrails D2（A 級，須引 JS 版）。
- 完整性 fail-closed：SLSA Provenance v0.2 `metadata.completeness`、VSA `dependencyLevels`（A 級）。
- 棄權是一等公民：Jung et al. 2024 *Trust or Escalate*（A 級）。
- 多評審不是獨立證據：Kim et al. 2025、Krumdick et al. 2026（A 級）。
- 事前協定約束優於事後聲譽：Hu, Rong & Van Kleek 2026（A 級）。

報告的 S1、S5–S8、S10–S13、S16、S19–S21 **不在**專案文獻庫裡——引用前要先落盤。

## 十一、對抗審查（2026-09-24 同日，五個鏡頭 × 各 12 條，逐條重現）

實作完成後跑了一輪對抗審查（workflow `vacant-intake-adversarial-review`）：五個獨立鏡頭——
收件端繞過、驗證器與政策、adapters／掛鉤、帳本與會計、敘述與證據——各自找缺陷並附重現腳本，
再由另一批 agent **對著當下的程式碼**逐條重現或推翻。60 條裡，會讓「不合格的版本進目的端」或
「紀錄說錯話」的，這裡全部修掉並各有一個會紅的測試（`tests/test_intake_gate_hardening.py`、
`tests/test_intake_verifier_hardening.py`、`tests/test_adapters_hardening.py`）。

**會讓不該放的版本放出去的（收件端）**：
- 同一個 task_id 的第二份契約（放行政策較鬆）就能放進委託者的目的端 ⇒ **契約鎖**：`vacant contract lock`
  由 **owner 金鑰**（新角色，需求權威）簽「這個任務＝這個契約雜湊＋這個放行政策」，收件端只依被鎖過的契約放行。
  簽章者清單裡已經設了別的 owner／approver／reviewer（另一個帳號）時，本機金鑰**不再**自動加入。
- 冪等路徑（同一版本已在目的端）跳過裁決與契約檢查 ⇒ 冪等路徑照樣檢查契約鎖與裁決。
- 公開端點跟隨符號連結、送出目的端上任何檔案 ⇒ 不跟連結；只送**簽過的帳本**證明在目前契約下放行、
  讀回成立、之後沒撤回的那一版，逐檔重算雜湊。
- 批准綁目的端字串（相對路徑在另一個目錄解析成另一個地方）⇒ 綁**解析後**的目的端；用過的 nonce 與撤回
  也記在簽過的帳本，刪掉目的端的 `state.json` 救不回來。
- git 目的端只看分支頂端 ⇒ 找這個任務最近一次的收件提交；讀回改用 `ls-tree -z`（非 ASCII 檔名）並比對檔案模式。
- 隔離區清單的路徑沒有重驗（`../` 寫到目的端外面）⇒ 載入與攤開前都驗；HTTP 提交的重複／檔案與目錄同名路徑
  記成 reject（不是 void）。
- 帳本截短可以讓被後來 reject 取代的 accept 復活 ⇒ 收件端記下看過的最後一筆（筆數＋雜湊），之後要看到同一筆。

**會讓裁決錯的（驗證器）**：成果帶的 `.bash_profile`／`usercustomize` 在驗證器之前執行（⇒ 收件口的沙箱
一律 hermetic：`bash --noprofile --norc`、`PYTHONNOUSERSITE`、HOME 不在成果裡；vrun 的舊行為不動）；
`command` 在沙箱裡拿不到文件寫的環境變數；NaN／inf 讓任何總數「相符」、`1,5` 被當成 15、`Subtotal` 被當成
total、預設樣式在惡意文字上是平方時間；只靠成果自己的 sources.json 的引用被標成獨立證據、空白引文、pandoc
多重引用沒檢查；JSON 的 NaN 過得了數值界限、`format` 沒檢查、draft-07 關鍵字被忽略；字串型清單參數被逐字元
迭代、空的禁止清單變 PASS、圍欄程式碼裡的 `#` 算標題；驗證器設定錯記成 FAIL；隱藏主張的細節出現在
`vacant check` 與帳本；人工審查沒綁契約雜湊；巢狀 `.env` 沒被預設禁止項抓到（樣式錨定在根目錄——
與 gitignore 不同，已寫進 docstring）。

**會讓 agent 或使用者的設定出事的（adapters）**：殼層規則用子字串比對，擋掉 `~/.vacant-work` 裡每一個寫入與
`pytest tests`（⇒ 斷詞＋路徑元件＋只看真正的寫入目標）；Codex／OpenCode 的 apply_patch 真實形狀沒讀到；
`/clear`、resume 也交件；等審查的 hold 被推回給 agent；`CLAUDE_CONFIG_DIR` 被忽略；`~/.codex` 是連結時信任鍵寫錯
路徑（掛鉤被 Codex 安靜略過）；安裝把連結換成普通檔、0600 變 0644；重裝蓋掉備份；撤銷失敗卻被忘記；結尾標記
壞掉就刪到檔尾；OpenCode／pi 的外掛用 `spawnSync` 卡住事件迴圈；session 同時可以做 `vacant review`
（⇒ 工具層拒絕 review／approve／release／withdraw／keys／contract lock）；`vacant uninstall` 不再拆 0.8.0 的
模型通道常駐安裝（⇒ 整體解除安裝時一起拆）。

**會讓帳本說錯話的**：`vacant do` 被中斷留下孤兒 agent、沒有終態；`.git/hooks` 植入不算逃逸；hold 也重試；
`VACANT_HOME` 在專案裡時金鑰被複製進工作區；放行後交一個被退的版本，狀態就變 rejected（⇒ 目的端的狀態
另外追）；從沒放行過的任務被「撤回」後永遠放不出去（⇒ 空操作）；一個壞掉的帳本讓整份報表消失（⇒ 自己算一列
`unreadable`）；放行階段的例外沒進帳本（⇒ `infra_void`，退出碼 43）；`vacant keys init` 與掛鉤同時建鑰匙
（⇒ 同一把鎖）。

**驗證那一批 agent 對著修正後的程式碼再重現**：大多數回報「已修、不再重現」；仍部分重現的三條也修了——
工具層規則漏了 `vacant-network …` 與 `python -m vacant_network.cli …`（README 教被遮蔽時用的名字）；
本機 reviewer 金鑰簽的「人工審查」看不出是同一個帳號（⇒ 證據標 `same_account`、`independent=false`、
細節文字寫明）；契約後來加了批准要求時，「已在目的端」那條路沒檢查批准（⇒ 檢查，不查 nonce）；
原專案 `.git/hooks` 裡有懸空連結時 `vacant do` 的逃逸量具崩潰、那一跑沒有帳本紀錄（⇒ 記下連結本身，跑之前壞掉記 `infra_void`）。
另外 `command` 的退出碼 1 同時代表「成果不合格」與「委託者的 python 腳本崩潰」——寫明在 §二與 summary。

**沒有修、改成明講的**（各自寫在該模組的誠實邊界）：
1. `python_checks` 的受測程式碼與檢查同一個直譯器——**防意外不防惡意**；不可信成果改用 `command`
   接行程外評測器或 `suitespec`。
2. 同一個帳號在收件端第一次看到之前就截短帳本，看不出來（要另一個帳號的收件端或外部見證）。
3. 本機單人模式下 owner／approver／reviewer 金鑰都在同一個帳號：分權要把它們放到另一個帳號。
4. 常駐的 Claude 安裝沒有 `disableAllHooks:false` 守衛；`ConfigChange` 守衛量過擋得住，**這裡沒有實作**。
5. 掛鉤規則仍是工具層的字串判斷；`vacant do` 殺不到自己 `setsid` 出去的子孫行程；工作區不會自動清理。
6. `dir:` 目的端在同一個帳號下是普通目錄：「只有這一條寫入路徑」要靠部署（§六已改寫）。
7. `hidden` 只管不在輸出裡洩漏；契約本身 agent 讀得到——真正的祕密放工作區外的釘住輸入。

## 十、沒做的／下一步／停止條件

1. **vacant-world-cloud 本身沒改**（不在本 session 的倉庫範圍）。`intake/server.py` 是同一件事的正確形狀，
   world-cloud 的 `/api/result` 應改成呼叫它（或照同樣的生命週期重寫）。
2. **真模型沒量**。四個 agent 的 L-real 需要 API key；下一輪用同一支 harness 換掉假模型即可。
3. 報告階段 C（行為層：任務級憑證、意圖→批准→執行→讀回的 Effect Broker）只做到「工具前否決」與
   「受控目的端」兩個點；寄信、付款這類外部效果沒有 broker。
4. 報告階段 D（強基線比較：同預算重試、agent 自評、現成評估＋批准）沒有跑。
5. ACP（Agent Client Protocol）是四家都有轉接器的另一個共通面，本輪沒有接。
6. **停止條件**（報告 §18）：人工覆核或 UNKNOWN 比例長期過高、或現成評估＋批准在同成本下一樣好 ⇒
   縮成特定領域的收件服務，不要宣稱通用平台已成立。
