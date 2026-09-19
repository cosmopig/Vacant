# DECISION 2026-09-19｜`vacant install`：從「每次要打的包裝器」到「裝一次就預設在」

> **一句話（做到什麼、做不到什麼）**
> **通道層做到了「裝一次就在，除非你刪掉」**：五個 agent 的 base url 寫進它們**自己的
> 常駐設定檔**，關終端機、開新視窗、**打完整路徑**都照樣經過 proxy；三個 agent
> （codex／opencode／Claude Code）在 macOS 上用真模型量到 `requests_seen > 0`，
> 命令列上**零個 vacant**。
> **閘門層只做到「預設會跑」**：靠 `PATH` shim，**打完整路徑就跳過**。
> **2026-09-20 補上 Linux**：`systemd --user` ＋ `loginctl enable-linger` 在
> vacant-dev（Ubuntu 24.04）上**真跑過**，四個退出碼、通道層兩個 agent、
> 兩次完整 install→uninstall 循環都量到（§六.4）。
> ⚠ **本檔不出現「不會被繞過」。** 那是做不到的宣稱
> （[`DECISION_20260919_BYPASS_STRESS.md`](DECISION_20260919_BYPASS_STRESS.md) 已經
> 逐條量過為什麼）。

**第一輪（macOS）**

- 量測日期：**2026-09-19 深夜 → 09-20 凌晨**（CST）
- 執行端：**人類的 macOS 15（Darwin 24.6.0）**；上游 **1003**
  `http://100.119.113.56:1234`，`gemma-4-12b-it-qat`
- 版本：codex-cli **0.153.2**、opencode **1.18.31**、Claude Code **2.1.278**
  （⚠ 跟 `docs/AGENT_COMPAT.md` §10 的 codex **0.147.0** 不是同一個；
  **同一格兩個版本號不可以混寫成一個**）
- 判斷層：`vacant_network/vrun/{possess,proxyd,gateshim}.py`（本輪新增）
- 逐格落盤：[`ops/vacantrun/possess_20260919/`](../ops/vacantrun/possess_20260919/)
  （⚠ 只有摘要與索引，原始 bytes 在會被清掉的 scratchpad 裡）
- 證據等級：**L-real**（真 agent、真模型、真流量）——但只有 **3/5** 個 agent；
  pi 與 hermes 在那台機器上**沒有可執行檔**，只有設定目錄 ⇒ 接線碼跑過，
  **`requests_seen` 一通都沒有** ⇒ 那兩格是 **L-none**。

**第二輪（Linux，2026-09-20）** —— 補 §七-5 那一格，詳見 **§六.4**

- 執行端：**vacant-dev**（Ubuntu 24.04.4、systemd **255.4-1ubuntu8.17**、
  Python 3.12.3）；上游 **1004** `http://100.86.226.21:1234`，`gemma-4-12b-it-qat`
- 版本：codex-cli **0.147.0**、Claude Code **2.1.259**
  （⚠ **跟第一輪不是同一組版本號**，兩輪的數字不可以混寫成一張表）
- 逐格落盤：[`ops/vacantrun/possess_linux_20260920/`](../ops/vacantrun/possess_linux_20260920/)
- 證據等級：**L-real**（真 agent、真模型、真流量），**2/5** 個 agent
  （codex、Claude Code）；opencode／pi／hermes 在那台機器上**連可執行檔都沒有**
  （只有設定目錄）⇒ **L-none**，不是失敗。
- ⚠ 那台機器上有人類的兩個長壽 session（17 天／29 天）在跑 Claude Code，
  所以**第二輪刻意沒有動真的 `~/.claude/settings.json`**；claude 那一格是用
  `possess.wire_claude()` 寫進一個**隔離 HOME** 量的（同一支函式、同一個檔名、
  同一支常駐 proxy，只是 HOME 根不同）。**這件事在讀那一格時要一起讀。**

---

## 〇、為什麼要做這件事（人類 2026-09-19 的糾正）

> 不對不對我發現你產生巨大偏差，我們要的不是用指令去喚醒 AGENT 而是**安裝之後我 PI
> 打開就默認有 VACANT**，而不是要用指令一筆筆的去加入。

> 對我要**裝一次就能直接使用除非我刪掉**。

舊形狀 `vacant run --suite <目錄> -- pi -p "…"` 最大的洞**不是** unix socket，
**是使用者忘記打那一串**——忘了就完全沒有 Vacant，**而且零痕跡**。

裝了之後，那個洞的形狀變了：忘記（或刻意）跳過 shim ⇒ **閘門沒跑**，
但模型呼叫**仍然經過常駐 proxy 並且進 journal** ⇒ 從「零痕跡」變成
「**有痕跡、沒有裁決**」。⚠ 這是一個**可究責性**的改善，不是一道防護。

---

## 一、兩層，能保證的東西不一樣（⚠ 不可以混講成一句「附身成功」）

| 層 | 機制 | 能說的話 | 實測 |
|---|---|---|---|
| **通道** | 寫進 agent **自己的常駐設定檔** | 關終端機／重開機／開新視窗／**打完整路徑**都照樣指向 proxy。**只有把那幾行刪掉才會失效。** | **3/5 L-real** |
| **閘門** | `PATH` shim（`~/.vacant/possess/bin/`） | **預設會跑，打完整路徑就跳過。** | codex L-real（4 格） |

逐個 agent 的常駐設定檔（`vacant_network/vrun/possess.py::AGENTS`）：

| agent | 檔案 | 寫什麼 | 本輪證據 |
|---|---|---|---|
| Claude Code | `~/.claude/settings.json` | `env.ANTHROPIC_BASE_URL` | ✅ `POST /v1/messages?beta=true -> 200`，模型回 `OK` |
| Codex | `~/.codex/config.toml` | `model_provider` ＋ `[model_providers.vacant]`（`wire_api="responses"`） | ✅ 5 通（4×200，1×400 後自行重試） |
| OpenCode | `~/.config/opencode/opencode.json` | **既有每一個 provider 的 `options.baseURL` 全部改道** ＋ 新增 `vacant` provider | ✅ 2 通，模型回 `OK` |
| pi | `~/.pi/agent/models.json` | `providers.vacant.baseUrl`（＋既有 provider 改道） | ⚠ **沒量**（那台沒有 pi 可執行檔） |
| Hermes | `~/.hermes/config.yaml` | `model.provider: custom` ＋ `model.base_url`（**兩行一組**） | ⚠ **沒量**（那台沒有 hermes） |

⚠ **Claude Code／OpenCode 原本被我們寫成「只吃環境變數 ⇒ 只能靠 shell profile
或 shim」。那是錯的**，兩家都有設定檔可以寫。這一條是 2026-09-19 深度調查推翻的。

⚠ **pi 那一格有一個沒解決的問題**：`~/.pi/agent/` 底下同時有 `models.json`
與 `models-store.json`，**哪一份才是 pi 0.85.1 真正讀的那一份沒有量過**。
我們寫的是 `models.json`（＝`ops/vacantrun/wrap_agent.sh` 量到的那個名字，
但那是 relocate 那條路，不保證常駐這條路同名）。**寫了不等於有效**，
`vacant install-status` 會把它標成未證實。

---

## 二、第一題：沒有 `--suite` 的時候，驗收從哪來？

### 2.1 解析順序（`gateshim.resolve_suite()`，由近而遠，第一個命中就停）

1. `$VACANT_SUITE`（明講）→ `suite_source = "env:VACANT_SUITE"`
2. 從 cwd 往上走：`.vacant/suite/`（含 `test_*.py`）→ `"dir:.vacant/suite"`
3. 從 cwd 往上走：`.vacant.toml` 的 `suite = "…"` → `"toml:.vacant.toml"`
4. 從 cwd 往上走：`tests_visible/`（本 repo R530／R535 題庫慣例）→ `"dir:tests_visible"`
5. 走到 `.git` 就停（**不准爬到 `$HOME`**）；都沒有 → `"none"`

找到的套件會被**複製到工作區外**（`<run_dir>/suite/`）才交給 launcher——
launcher 有一道擋門：`--suite` 在工作區底下 ⇒ 拒絕啟動
（「agent 改得到的驗收不是驗收」）。權威的是複製出來的那一份。

### 2.2 都沒有 ⇒ **只中介不跑閘門**，不是拒絕啟動

理由：使用者在一個沒有測試的目錄裡打 `pi -p "這段在做什麼"` 是正常的。
拒絕啟動會讓人把 Vacant 解除安裝，**而解除安裝之後是零個 Vacant，比只有通道層更糟**。

### 2.3 ⚠ 但它必須在收據與退出碼上分得出來（人類點名的那一條）

人類給的反例（今天量到三次）：
`rs=0`／`wire={}`／`agent_rc=0`／`stop_reason=visible_fail`／exit 20／`chain_ok=true`
—— **除了 `requests_seen`，每個欄位都跟一個合法的拒交格一模一樣。**

⇒ shim 層的退出碼表（`vacant_network/vrun/gateshim.py`）：

| 碼 | 意思 | 本輪實測 |
|---|---|---|
| `0` | **驗收真的跑了而且過了** | ✅ `deliver` 格 |
| `20` | 驗收跑了沒過 ⇒ 拒交 | ✅ `refuse` 格 |
| **`21`** | **沒有驗收可跑：只中介，沒閘門**（`stop_reason="ungated"`、`accepted=null`、`suite_source="none"`） | ✅ `nosuite` 格 |
| `22` | `infra_void` | （既有） |
| **`23`** | **`requests_seen == 0`：這一跑沒有任何模型呼叫經過 proxy** | ✅ 負控制（`/bin/echo` 放在 agent 位置） |

`21` 的必要性：`launcher.exit_code()` 把 `ungated` 判成 **0**（因為 `refused` 是
False）。**不改 launcher**（會動到已歸檔資料的可比性與 `docs/AGENT_COMPAT.md`
的既有結論），改在 shim 這一層分出來。

`23` 的必要性：沒有中介的證據時，那一格的裁決**不可歸因**——不是拒交也不是通過。
它蓋過 `0`／`20`／`21`（`22` 除外）。`VACANT_POSSESS_RS0=warn` 可降級成只印警告。

每一跑另外落一份 `<run_dir>/possess.json`，含 `suite_source`、
`gate: "ran"|"skipped"`、`requests_seen`、`shim_exit`、原始 `argv`、`real_binary`。

---

## 三、第二題：proxy 常駐還是隨跑隨起？⇒ **常駐，而且 fail-closed**

### 3.1 為什麼是常駐

設定檔寫死一個端點 ⇒ **那個端點必須隨時在**，否則 agent 直接連不上（比沒裝還糟）。
shim 每次起一個不行：shim 只在「有人經過 shim」時才存在，而那正是繞得過的那一層。

實作＝**由 OS 監督**：

| 後端 | 機制 | 撐得過重開機？ |
|---|---|---|
| macOS `launchd` | `RunAtLoad` ＋ `KeepAlive` | ✅（⚠ **沒有真的重開機驗過**，§七-6） |
| Linux `systemd --user` | `Restart=always` ＋ `loginctl enable-linger` | ✅（linger 成功時；失敗會記在 state）⚠ **2026-09-20 量到的是「零 session 之下還在」，不是「重開機之後還在」**（§六.4-C） |
| `bare`（都沒有，例如容器） | 自己 fork | ❌ **`install-status` 標 `supervised: no`，不准說成「常駐」** |

### 3.2 為什麼是 fail-closed（proxy 沒起來 ⇒ agent 連不上而報錯）

a. **回退直連＝安靜地失去中介**，那正是本輪要修掉的那個洞
   （`envmap` 誠實邊界 2：漏掉的那條路要**連不上**，不是**偷偷連上**）。
b. **本 repo 每一處都是這條紀律**：`SINK_UPSTREAM`（沒人指定上游 ⇒ 開連線之前就
   502、不組 header、不解 DNS、不送任何 bytes，回一段講得出「要設哪個變數」的
   JSON，逃生口 `--allow-public-upstream` 必須明講）、`no_suite` ⇒ 拒交、
   R440G 的 `--decision` 檔不存在 ⇒ 拒絕啟動。這裡破例會讓那幾條的口徑一起鬆掉。
   **本輪直接沿用那個形狀**：`install` 沒推得出上游時就把該條 wire 指到
   `SINK_UPSTREAM`，常駐 proxy 照樣起得來、照樣回 502，**但一個 byte 都不出網**。
c. 失敗是**看得見而且定位得到**的：agent 印 connection refused、
   `install-status` 直接說「在聽：**否**」、`uninstall` 一行復原。
d. **技術上也沒有誠實的 fail-open**：要回退直連，就得在失敗當下把使用者的設定檔
   改回去——也就是這個工具要會**安靜地把自己解除安裝**。

### 3.3 ⚠ 代價，寫在前面

proxy 起不來（埠被佔、python 壞掉、公司政策擋 launchd）⇒
**這台機器上五個 agent 全部不能用**，直到 `vacant uninstall`。三道緩解：

1. **preflight**：`install` 先把 proxy 起起來、真的打一通 round-trip，
   **過了才寫第一個設定檔**。本輪兩次實際擋下來過（下一節），
   兩次都是**一個設定檔都沒動**。
2. `uninstall` 是純檔案還原，**proxy 死著也跑得完**。
3. `install-status` 一眼看得出是哪一層壞了（端點在不在聽、監督後端、心跳）。

### 3.4 常駐 proxy 與 `vacant run` 那支的三個差別（⚠ 不可混講）

1. **不換鑰**：`sentinel=""` ⇒ `wireproxy` 的換鑰那一段整段不執行，
   `Authorization`／`x-api-key` **原樣轉送**。理由是憑證紅線：常駐行程不該
   持有使用者的真鑰。代價是「拿掉金鑰」那個弱保證在常駐這條路上不成立
   （它本來也不是安全邊界，`envmap` 誠實邊界 3）。
   **header 不落盤**（`wireproxy` 只寫 body）⇒ 金鑰不上碟。
2. **不跑驗收、不簽裁決收據**：那是閘門層的事。
3. **落盤的是 journal 不是收據**：`<state>/proxyd/wire/index.jsonl`。

### 3.5 ⚠ 本輪最貴的一個發現：macOS TCC 會讓 launchd job **卡死而不是報錯**

`.venv` 在 `~/Documents/GitHub/Vacant` ⇒ launchd job `state = running`、`pid` 有值、
**埠沒有人在聽、`out.log`／`err.log` 兩個都是 0 byte**。
`sample <pid>` 抓到堆疊卡在
`Py_InitializeFromConfig → _PyConfig_InitPathConfig → getpath_readlines →
_Py_wfopen → open$NOCANCEL` —— **python 直譯器在啟動階段的 `open()` 就不回來了**，
因為 launchd agent 沒有 `~/Documents` 的 TCC 授權，而它**不能跳權限對話框**。

同一支 daemon 換成 `/Library/Frameworks/…/python3` ＋ 套件複製到 `/private/tmp`
⇒ **一秒內起來、`curl` 回 200**。

⇒ `possess.tcc_risky()` 在**動任何東西之前**擋下 `~/Documents`／`~/Desktop`／
`~/Downloads`／`~/Library/Mobile Documents`，並給三條路
（裝到不受保護的位置／`--service bare`／`--allow-protected-path`）。
⚠ **這不是「偶爾會失敗」，是開發者 checkout 底下一定會失敗**；
一般 `pip install` 進 venv 不在這幾個目錄裡，所以正常安裝碰不到。

---

## 四、第三題：改人家的設定檔，怎麼可逆

三件事一起做，缺一不可：

1. **先備份**：原始 bytes 整個複製到 `<state>/backups/<名字>.<sha256前12>.bak`，
   複製完**立刻驗 sha256**，對不上就 raise（不是印個警告繼續）。
2. **`vacant install-status` 講得出改了什麼**：逐檔列出 `action`、改了哪個欄位、
   `before_sha256` → `after_sha256` → **現在的 sha256**（裝好之後又被改過會標
   ⚠）、備份在哪、**「還原會做什麼」一句話**。
3. **`vacant uninstall` 逐位元還原，而且自己驗**：`create` ⇒ 刪掉並確認不存在；
   `modify` ⇒ 用備份覆寫並確認 `sha256 == before_sha256`。任何一格 `ok=False`
   就整份報告 `ok=False`，`state.json` **不刪**（留著讓人重跑），
   報告落成 `<state>/uninstall_report.json`。

**憑證紅線**（`possess.NEVER_TOUCH`，會 raise 的擋門不是註解）：
`~/.codex/auth.json`、`~/.pi/agent/auth.json`、`~/.claude/.credentials.json`、
`~/.config/opencode/auth.json`、`~/.hermes/auth.json`、
`~/.local/share/opencode/auth.json` —— **本輪一次都沒有讀過這些檔**。

### 4.1 實測：完整循環

在一個**內容逐位元複製自人類真實設定檔**的隔離 HOME 上跑
（`~/.codex/config.toml` 379 行含 100+ 個 `[projects.*]`、
`~/.config/opencode/opencode.json` 含 3 個自訂 provider、
`~/.claude/settings.json` 含 21 個頂層 key）：

```
install → 6 個檔被改（5 個 agent 設定 ＋ .zshrc）＋ 1 個 plist 被建立
        → 端點 http://127.0.0.1:8790 在聽、launchd 監督、開機自起
uninstall → ok = True，port_still_open = False
        → 六個檔全部逐位元相同（diff 零輸出）
        → 殘留 "vacant possess" / "127.0.0.1:8790" 字樣：**零**
        → launchd job：Could not find service（已移除）
        → plist 檔：已刪除
```

⚠ 過程中發現並修掉一個**會讓報告說謊**的量錯：`launchctl bootout` 回來的時候
行程還沒退完，`port_still_open` 當場量會量到 `True`（其實一秒後就關了）。
現在改成等最多 6 秒再量。**量錯的方向是「說沒停掉其實停了」，不是相反**，
但報告說謊就是報告說謊。

---

## 五、繞得過的每一條路（⚠ 這一節是本檔的重點）

| # | 路徑 | 通道還在嗎 | 閘門跑嗎 | 留痕跡嗎 |
|---|---|---|---|---|
| 1 | **打完整路徑**（`/usr/local/bin/codex …`） | ✅ 在（常駐設定檔） | ❌ **跳過** | ✅ 常駐 journal 有 |
| 2 | **把設定檔那幾行刪掉**（或 `vacant uninstall`） | ❌ | ❌ | ❌ |
| 3 | **passthrough 名單**（`--version`／`--help`／`mcp`／`login`…） | ✅ | ❌ **刻意不 gate** | ✅ journal |
| 4 | **互動 TUI**（stdin 是終端機，預設不 gate） | ✅ | ❌ | ✅ journal |
| 5 | **不在名單上的 agent**（aider、cline、自己寫的腳本、`curl`） | ❌ | ❌ | ❌ |
| 6 | **Codex `codex login`（ChatGPT 帳號）** | ❌ **設定搬不動**（寫死 `wss://chatgpt.com/…`） | ❌ | ❌ |
| 7 | **OpenCode 用一個我們沒改道的 provider** | ❌ | ❌ | ❌ |
| 8 | **環境變數蓋過設定檔**（使用者自己 `export OPENAI_BASE_URL=…`） | ❌ | ❌ | ❌ |
| 9 | unix domain socket／`LD_PRELOAD`／自己 patch binary | ❌ | ❌ | ❌（[BYPASS_STRESS](DECISION_20260919_BYPASS_STRESS.md) 量過：uds 這條路上刻度是瞎的） |
| **10** | **Linux 專屬：非登入非互動 shell**（`ssh 主機 '指令'`、`bash -c`、cron、systemd unit、CI runner） | ✅ 在 | ❌ **跳過** | ✅ journal |

第 10 條是 2026-09-20 在 vacant-dev 上**量出來的**，不是推論
（`ops/vacantrun/possess_linux_20260920/`）。Ubuntu 的 stock `~/.bashrc` 第 6 行
是 `case $- in *i*) ;; *) return;; esac` —— **非互動就直接 return**，而
`install_path_block()` 是把 `PATH` 區塊**附加在檔尾**，所以那一段在非互動 shell 裡
根本不會被執行到。實測四種 shell：

| 怎麼起的 | shim 在 PATH 上嗎 |
|---|---|
| `bash -lic`（登入互動，＝人類開終端機） | ✅（⚠ `.profile` 與 `.bashrc` 兩邊都加 ⇒ **PATH 上出現兩次**） |
| `bash -lc`（登入非互動） | ✅（靠 `.profile`） |
| `ssh 主機 '指令'` | ❌ |
| `bash -c`（非登入非互動） | ❌ |

⇒ **「裝一次就在」在 Linux 上對「人類開終端機打指令」成立，對「腳本／排程／
CI 呼叫 agent」不成立。** 展場那種無人值守迴圈多半是後者 ⇒ **展件如果要閘門，
不能靠 `PATH` 區塊**，要嘛明講完整 shim 路徑、要嘛把 shim 目錄寫進那個 unit 的
`Environment=PATH=`。通道層不受影響（那寫在 agent 自己的設定檔裡）。

3 與 4 是**刻意的**：把 `codex --version` 或一個互動 session 包起來跑驗收只會壞掉
使用者的日常操作，然後 Vacant 被解除安裝。寫成測試
（`test_passthrough_lets_version_and_help_through`）是為了它**數得出來、不是意外**。
4 可以用 `VACANT_POSSESS_GATE_TTY=1` 打開。

---

## 六、本輪的實測落盤

### 6.1 通道層（命令列上**零個 vacant**，用完整路徑打真 binary）

| agent | 命令 | journal 通數 | 結果 |
|---|---|---|---|
| codex 0.153.2 | `codex exec --skip-git-repo-check -m gemma-4-12b-it-qat "Read TASK.md…"` | **5**（`POST /v1/responses` 4×200＋1×400） | 寫出正確的 `solution.py` |
| opencode 1.18.31 | `opencode run -m vacant/gemma-4-12b-it-qat "Reply with the single word OK."` | **2** | 回 `OK` |
| Claude Code 2.1.278 | `claude -p "Reply with the single word OK." --dangerously-skip-permissions` | **2**（`POST /v1/messages?beta=true -> 200` ＋ `HEAD /api/hello`） | 回 `OK` |

⚠ Claude Code 的 `HEAD /api/hello` 被 `wireproxy.route()` 判成 **openai** wire
（既有行為，`envmap` 已記）。本輪它留在本機是因為 openai 那條也釘到了 1003。

### 6.2 閘門層（`PATH` 前面放 shim，命令列上仍然**零個 vacant**）

| 格 | 退出碼 | `stop_reason` | `suite_source` | `rs` | 收據 |
|---|---|---|---|---|---|
| `refuse`（TASK 只要 `add`，套件要 `add`＋`mul`） | **20** | `visible_fail` | `dir:tests_visible` | 3 | `chain_ok`、`mediated=有` |
| `deliver`（TASK 兩個都要） | **0** | `visible_pass` | `dir:tests_visible` | 3 | `chain_ok`、`mediated=有` |
| `nosuite`（工作區沒有任何套件） | **21** | `ungated`（`accepted=null`） | `none` | 4 | — |
| `rs0` 負控制（`/bin/echo` 放在 agent 位置） | **23** | — | `dir:tests_visible` | **0** | — |

收據驗章器發射前 `--selftest: PASS`；兩條裁決鏈 `entries 2 / 驗過 2 / 失敗 0 /
chain_ok OK / mediated 有`。

### 6.3 preflight 擋下來的兩格（**一個設定檔都沒動**）

1. `.venv` 在 `~/Documents` ⇒ TCC 卡死 ⇒ `25s 內 127.0.0.1:8790 沒有人在聽`
2. 同一件事在加了 `tcc_risky()` 擋門之後，**提早到寫檔之前**就拒絕，並印出三條路

### 6.4 Linux 那一輪（2026-09-20，vacant-dev）

落盤：[`ops/vacantrun/possess_linux_20260920/`](../ops/vacantrun/possess_linux_20260920/)

#### A. 先證明連得到**對的**那一條 user bus（不然底下每一格都是假的）

`systemctl --user` 在 ssh 非互動 session 底下最容易的失敗方式是**假成功**。
所以先量三件事，而不是「`systemctl --user` 沒報錯就算數」：

```
XDG_RUNTIME_DIR=/run/user/1000                       ← sshd/pam_systemd 已經給了
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
busctl --user status  → BusAddress=unix:path=/run/user/1000/bus
                        BusScope=user   PID=1559   OwnerUID=1000
systemctl show user@1000.service -p MainPID  → 1559   ← **跟 bus 的 PID 同一個**
systemd-run --user --unit=vacant-bus-probe … 真的跑起來，落在
  0::/user.slice/user-1000.slice/user@1000.service/app.slice/vacant-bus-probe.service
```

⇒ 判準是**那個 manager 真的替我起了一個 unit**，不是「指令回 0」。

#### B. install 本身

```
service = {backend: "systemd", supervised: true, boot_persistent: true,
           linger_rc: 0, rc: 0,
           unit_file: ~/.config/systemd/user/vacant-proxyd.service,
           stderr: "Created symlink …/default.target.wants/vacant-proxyd.service → …"}
preflight = {listening: true, roundtrip: 200, detail: "上游回應了"}
systemctl --user is-enabled / is-active  →  enabled / active
proxy 的 cgroup: /user.slice/user-1000.slice/user@1000.service/app.slice/vacant-proxyd.service
```

**`loginctl enable-linger` 以一般使用者身分、在 ssh session 裡、沒有 polkit 對話框
就成功了**（`linger_rc: 0`；`Linger=no` → `yes`，`/var/lib/systemd/linger/user1`
被建出來）。⚠ 這一條**不保證可移植**：它取決於那台的 polkit 把 ssh session 算成
`active`。別的發行版拒絕的話 `linger_rc != 0`、`boot_persistent` 會是 `false`，
**state 記得下來**，但 `install` 仍然會成功並回報一個不 persistent 的安裝。

⚠ 不給 `--upstream` 的時候，兩條 wire **都落到 `SINK_UPSTREAM`**
（`http://unspecified-upstream.vacant.invalid`）——fail-closed 在 Linux 上照舊。

#### C. linger：**零 session 之下還在**（這一格是核心）

「ssh 斷線還活著」在 user1 上是**弱的**，因為那台永遠有別人的 session 撐著
`user@1000.service`。所以分兩層量：

**C-1 弱的那一層（ssh 斷線）**——session 12105 裡記下 proxy 身分，斷線，
新 session 12106 回去看：

```
session 12105：Scope=session-12105.scope   proxy MainPID=3931207
               proxy cgroup = user@1000.service/app.slice/vacant-proxyd.service
               （⚠ 跟我自己的 session-12105.scope 是**兩個不同的 cgroup**）
斷線後 12106：loginctl list-sessions 裡 **12105 不見了**
               proxy MainPID=3931207（同一個）  ActiveEnterTimestamp 沒變
               curl 127.0.0.1:8787/v1/models → HTTP 200
```

**C-2 決定性的那一層（零 session）**——人類的 session 不能動，所以開一個
**拋棄式使用者** `vlingerx`（uid 1001），它**從頭到尾沒有登入過一次**：

```
[1] 沒 linger、沒登入過：/run/user/1001 不存在；user@1001.service = inactive
[2] loginctl enable-linger vlingerx →  Linger=yes
[3] loginctl show-user vlingerx → State=lingering   Sessions=（空）
    list-sessions 裡 vlingerx 的筆數 = 0
[4] user@1001.service = active；/run/user/1001/bus 出現
[5] 以 vlingerx 身分跑 vacant install（port 8830）→ rc=0、preflight 200
[6] **零 session 之下**：systemctl --user is-active → active
    LISTEN 127.0.0.1:8830 ；curl → HTTP 200
    cgroup = /user.slice/user-1001.slice/user@1001.service/app.slice/vacant-proxyd.service
[7] 反面對照：loginctl disable-linger vlingerx
    → t=+1s  user@1001.service = inactive；8830 沒人在聽；curl HTTP 000；
      /run/user/1001 消失
[8] userdel -r vlingerx，/var/lib/systemd/linger/ 回到只剩 user1
```

⇒ **「沒有任何人登入的時候 proxy 還在」是量到的，而且反面對照證明撐著它的
就是 linger。** 這正是展場無人值守要的那一條。

⚠ **但這不等於「重開機之後還在」。** 沒有重開機（那台有人類的兩個長壽
session），所以 §七-6 對 Linux 也仍然成立——`enable-linger` 的語意是開機時
起 `user@<uid>.service`，**語意成立不等於量到**。

#### D. `Restart=always`

`kill -9` 兩次，兩次都回來：

```
第 1 次：MainPID 3930936 → 3931081，NRestarts 0 → 1，+2s 內 is-active=active
第 2 次：MainPID 3931081 → 3931207，NRestarts 1 → 2
        **埠恢復到能回 HTTP 200 的時間 = t0 + 2.55s**（RestartSec=2）
journal: Main process exited, code=killed, status=9/KILL
         → Scheduled restart job, restart counter is at N → Started
```

⚠ 第一次量的時候我在 `MainPID` 一變就 `curl`，拿到 `HTTP 000` ——**那不是
「量到 0」，是「還沒量到」**（新行程已 fork、socket 還沒 bind）。重量一次改成
輪詢到埠回話為止，才有上面那個 2.55s。原始的 `000` 留在紀錄裡。

#### E. 通道層（命令列上零個 `vacant`，用完整路徑打真 binary）

| agent | 命令 | journal 通數 | 結果 |
|---|---|---|---|
| codex 0.147.0 | `/home/user1/.local/bin/codex exec --skip-git-repo-check -m gemma-4-12b-it-qat "Reply with the single word OK."` | **0** | ❌ **`ERROR: Missing environment variable: OPENAI_API_KEY`**，一個 byte 都沒出門 |
| codex 0.147.0 | 同上，但 `OPENAI_API_KEY=sk-vacant-possess` | **3**（`GET /v1/models` ×2 → 200、`POST /v1/responses` 254340B→100023B → 200） | 模型回 `OK` |
| Claude Code 2.1.259 | `HOME=<隔離> /home/user1/.local/bin/claude -p "Reply with the single word OK." --dangerously-skip-permissions` | **3**（`HEAD /api/hello` → 200、`POST /v1/messages?beta=true` ×2 → 200） | 模型回 `OK` |

⚠ **第一列是本輪最有用的一格，而且它是壞消息。** `wire_codex()` 寫的是
`env_key = "OPENAI_API_KEY"`，而 vacant-dev 的登入環境**沒有這個變數**
⇒ codex 在**開任何連線之前**就拒絕啟動。也就是說：**設定檔寫好了、proxy 活著、
`install-status` 會說「✓ 已寫入」，而那個 agent 其實完全用不了。**
macOS 那一輪沒看到這一格，是因為人類的 shell 裡本來就有 `OPENAI_API_KEY`。
⇒ **「裝一次就在」在一台乾淨的 Linux 上對 codex 目前是不成立的**，
`install` 要嘛自己在設定裡塞一個假鑰（`wire_api` 那一段旁邊多一行），
要嘛 `install-status` 要把「env_key 指到的變數不存在」標成紅的。**兩件都還沒做。**

⚠ Claude Code 那一格的三個保留：(i) 隔離 HOME（理由見開頭）；
(ii) `wire_claude()` **只寫 `ANTHROPIC_BASE_URL`**，`ANTHROPIC_API_KEY` 與
`ANTHROPIC_MODEL` 是我為了測試**另外補上去的鷹架**，不是 `install` 做的
（憑證紅線：`wire_claude` 刻意不碰任何金鑰欄位）——所以 **codex 那個
「沒有鑰就啟動不了」的問題，claude 這條路上同樣存在，只是被鷹架蓋住了**；
(iii) `HEAD /api/hello` 一樣被 `wireproxy.route()` 判成 **openai** wire（既有行為）。

`status` 的 `proven` 欄位在 Linux 上也正常翻牌：跑之前
`{"codex": {"wired": true, "proven": false}}`，經過一次閘門（`requests_seen=5`）
之後 `{"proven": true, "note": "requests_seen=5 @ 2026-09-19T17:18:02+0000"}`。
⚠ 同一列的 `measured` 欄仍然印著 **macOS** 那個日期字串
（`CHANNEL_MEASURED` 已於本輪補上 Linux 那一段）。

#### F. 閘門層：四個退出碼**全部重現**

| 格 | 退出碼 | `stop_reason` | `suite_source` | `rs` |
|---|---|---|---|---|
| `refuse`（TASK 只要 `add`，套件要 `add`＋`mul`） | **20** | `visible_fail` | `dir:tests_visible` | 6 |
| `deliver`（TASK 兩個都要） | **0** | `visible_pass` | `dir:tests_visible` | 5 |
| `nosuite` | **21** | `ungated`（`accepted=null`） | `none` | 5 |
| `rs0` 負控制（`/bin/echo` 放在 agent 位置） | **23** | `visible_fail` | `dir:tests_visible` | **0** |

`refuse` 是**真的拒交**——agent 只寫了 `add`，回饋是
`test_ops.py::check_mul — exception: AttributeError: module 'solution' has no
attribute 'mul'`，不是 macOS 那一輪 `d1e80b` 的 `driver_error` 假拒交。

`rs0` 逐字重現了那個病理：`refused=true`／`stop_reason=visible_fail`／
`agent_rc=0`／`visible_total=2`／`wire_by_protocol={}`——**除了 `requests_seen`，
每個欄位都跟一個合法的拒交格一模一樣**。23 蓋過 20 是必要的。

#### G. 完整循環可逆（跑了**兩次**）

第一次（4 個 agent ＋ shell rc ＋ service，7 個檔）、第二次（只 codex、`--no-path`，
2 個檔），兩次 `uninstall` 都 `ok = True`、`port_still_open = False`，每一格都
自驗 `sha256 == before_sha256`。收工比對：

```
五個使用者設定檔 vs 我自己另外存的獨立安全網備份 → diff 全部零輸出
  .codex/config.toml  .pi/agent/models.json  .bashrc  .profile
  .claude/settings.json（控制組，全程沒被動過，sha256 一路沒變）
建立出來的檔：opencode.json / .hermes/config.yaml /
  ~/.config/systemd/user/vacant-proxyd.service / state.json / possess/bin  → 全部已刪
殘留字樣 "vacant possess"／"127.0.0.1:8787"：**零**
systemctl --user is-enabled vacant-proxyd.service → not-found；8787 已釋放
vacant-exhibit.service 全程 active，8420／8899 沒被動過
```

**⚠ 兩件 `uninstall` 沒有還原的東西**（兩件都是本輪新發現，不是已知）：

1. **`loginctl enable-linger` 不會被關回去。** `install` 會開 linger，
   `stop_service()` 只做 `systemctl --user disable --now`，**`Linger` 留在 `yes`**。
   在一台原本 `Linger=no` 的機器上，`uninstall` 之後那個使用者的 user manager
   會**永久變成開機自起**——這是一個沒被記錄、沒被還原的機器狀態改動。
   本輪手動補 `loginctl disable-linger user1` 回到 `no`。
   ⇒ 要修：`install` 應該把「linger 原本是什麼」記進 state，`uninstall` 照著還原
   （⚠ 而且只能在**原本是 no** 的時候關掉，不然會關掉別人要的 linger）。
2. **`gateshim.exec_inner()` 的 per-run `CODEX_HOME` 從來沒人刪。**
   每一次經過閘門的 codex 呼叫都會在 `$TMPDIR` 留下一個
   `vacant-possess-<uuid8>/`，而 codex 會把它的 plugins git repo 整個 clone 進去
   ⇒ **每跑一格 ~100 MB**。本輪 5 格 ＝ **400 MB**，是那台 2.5 G 餘裕的 16%。
   `uninstall` 不碰它（它不在 `state["files"]` 裡），本輪手動刪掉才把磁碟還回去。
   ⇒ **展場無人值守迴圈照這樣跑會把磁碟吃光。** 要修：`run_gate` 結束時清掉，
   或改用 `run_dir` 底下（那樣至少跟收據一起被管理）。

#### H. 偵測與憑證紅線

- **偵測不靠 PATH 在 Linux 上也成立**：`~/.local/bin` **不在**非互動 ssh 的 PATH 上，
  但 `--no-shell-probe` 那一趟仍然靠 `bin_hints` 掃到 claude 與 codex
  （`binary_via: "hint"`）；加上 `bash -lic` 那一趟則是 `login_shell`。兩趟結論相同：
  **5/5 `present: true`，2 個有可執行檔，3 個（opencode／pi／hermes）只有設定目錄**。
- **`NEVER_TOUCH` 在 Linux 上生效**：對六個路徑逐一呼叫 `write_tracked()`，
  六個全部丟 `PermissionError: 紅線：… 是憑證，本模組不讀不寫`，
  三個實際存在的檔（`.codex/auth.json`、`.pi/agent/auth.json`、
  `.claude/.credentials.json`）**內容 sha256 沒變**。
  ⚠ 分清楚：本輪之後 `~/.codex/auth.json` 的 mtime／大小**變了**
  （3921 → 3932 bytes）——那是 **codex 自己**在跑的時候換 token，不是 possess。
- ⚠ **vacant-dev 上沒有 pytest**（`No module named pytest`），所以
  `tests/test_vrun_possess.py` 那 30 個測試**在 Linux 上一次都沒跑過**，
  只在 macOS 上跑過。

---

## 七、**還不能說的話**

1. **不能說「不會被繞過」。** 第五節有**十**條路（第 10 條是 Linux 專屬、
   2026-09-20 量出來的）。閘門層連「預設會跑」都有兩個刻意的例外
   （passthrough、互動 TUI），在 Linux 上還要再加一個（非登入非互動 shell）。
2. **不能說五個 agent 都接通了。** 通道層兩輪加起來：
   **codex／opencode／Claude Code 是 L-real**（codex 與 Claude Code 在
   macOS 與 Linux **兩台**都量到，opencode 只有 macOS）；
   **pi 與 hermes 兩台都是 L-none**——兩台機器上都沒有它們的可執行檔，
   接線碼跑過但**一通都沒量到**。pi 還多一個未解問題
   （`models.json` vs `models-store.json`）。
   ⚠ Linux 的 Claude Code 那一格是**隔離 HOME**（§六.4 開頭），不是人類那份設定檔。
3. **不能說閘門在五個 agent 上都有牙齒。** 閘門層**兩輪都只量了 codex**
   （macOS 4 格、Linux 4 格）。其餘四個沒量。
4. **不能說這是一張同條件矩陣。** 兩台機器**用的是不同的 codex 版本
   （0.153.2 vs 0.147.0）、不同的上游（1003 vs 1004）、不同的模型服務實例**，
   一題、每格 n=1。`docs/AGENT_COMPAT.md` §13 那種五 agent × 兩格 × 兩次的複製
   **兩輪都沒做**。⚠ 兩輪的數字**不可以合併成一張表**。
5. ~~**不能說 Linux 那邊也成立。**~~ **2026-09-20 已經補上，改成下面這樣：**
   - **可以說**：`systemd --user` 那條路在 Ubuntu 24.04 上**真跑過**——
     unit 建得起來、`enable --now` 成功、`Restart=always` 在 `kill -9` 之後
     **2.55 秒**把埠帶回來、四個退出碼（20／0／21／23）全部重現、
     兩次完整 install→uninstall 循環逐位元還原。
   - **可以說**：`loginctl enable-linger` 之後，**在一個從未登入過、
     `Sessions=` 為空的使用者身上**，proxy 照樣 `active` 並回 HTTP 200；
     把 linger 關掉 **1 秒內**整個 user manager 連同 proxy 一起消失
     （反面對照，§六.4-C-2）。**這是展場無人值守要的那一條。**
   - **不能說「重開機之後還在」**（見第 6 條），也**不能說 linger 一定開得起來**：
     本輪 `linger_rc = 0` 是在那台的 polkit 把 ssh session 算成 active 的前提下拿到的。
   - **不能說 Linux 上「裝一次就能用」對 codex 成立**：乾淨的 Linux 登入環境
     **沒有 `OPENAI_API_KEY`**，codex 在開連線之前就 `ERROR: Missing environment
     variable` ⇒ **journal 零通**。設定寫了、proxy 活著、`install-status` 卻說
     「✓ 已寫入」——**這一格現在是會騙人的**（§六.4-E）。
   - **不能說 Linux 上的閘門對腳本／排程有效**：Ubuntu 的 stock `.bashrc`
     非互動就 `return`，`PATH` 區塊在 `ssh 主機 '指令'`／`bash -c`／cron／
     systemd unit 底下**根本不會被 source**（§五第 10 條）。
   - **不能說那 30 個單元測試在 Linux 上過了**：vacant-dev **沒有 pytest**，
     一次都沒跑過。
6. **不能說重開機之後還在。** macOS：`RunAtLoad` 寫了、`launchctl print` 顯示
   `properties = keepalive | runatload`。Linux：`enable` 建了
   `default.target.wants` 的 symlink、linger 也開了。**兩台都沒有真的重開機驗**
   （vacant-dev 上有人類的兩個長壽 session，不准重開）。
   ⚠ **「零 session 之下還在」≠「重開機之後還在」**，不要把 §六.4-C-2 讀成後者。
7. **不能說常駐 proxy 撐得住併發。** 多個 agent 同時打同一個埠沒有壓測過；
   `ThreadingHTTPServer` 的行為在高併發下沒量。兩輪都沒量。
8. **journal 分不出是誰打的。** 常駐 proxy 沒有 per-agent 標記 ⇒
   `install-status` 的 `resident_journal` 只能回答「通道層活著而且有流量」，
   **不能回答「這個 agent 被中介了」**。後者要 `channel[*].proven`，
   而那一欄只有走過閘門的那一跑才點得亮（Linux 上也驗過會翻牌）。
9. **`uninstall` 不是「零殘留」，是「六個使用者設定檔逐位元還原」。**
   兩件東西留在機器上（§六.4-G）：**`Linger` 不會被關回去**、
   **`gateshim` 每跑一格在 `$TMPDIR` 留 ~100 MB 的 per-run `CODEX_HOME` 永遠沒人刪**
   （本輪 5 格 ＝ 400 MB）。另外 `<state>/proxyd/` 的 journal 與
   `uninstall_report.json` 也刻意留著。**這三件在展場無人值守迴圈上都是會累積的。**
10. **磁碟／機時**：第一輪全部在 macOS 的 scratchpad，vacant-dev 一個 byte 都沒佔。
    第二輪在 vacant-dev 上跑，尖峰佔 400 MB（就是上一條那個洩漏），
    **收工已全部歸還，`df` 回到 2.5 G 可用**；模型機時只用了 1004 的 7 次短呼叫。

---

## 八、落盤與程式碼

**新增（本輪，不動任何既有檔）**

- `vacant_network/vrun/possess.py` — 偵測／接線／備份／還原／狀態／service
- `vacant_network/vrun/proxyd.py` — 常駐反向代理（不換鑰、不簽收據、只 journal）
- `vacant_network/vrun/gateshim.py` — `PATH` shim 的兩階段（找 binary／找套件／
  退出碼映射／per-run relocate 設定）
- `tests/test_vrun_possess.py` — 30 個測試，全過

**要改既有檔（**本輪刻意沒改，等人類排順序**）**

1. `vacant_network/cli.py` — 註冊 `install` / `uninstall` / `install-status`
   三個子命令（`status` 這個名字已經被 eco 子命令佔走）。
   ⚠ 這個檔正被改名那條線改著（staged rename ＋ 9 行 unstaged），所以沒動。
   現在的入口是 `python -m vacant_network.vrun.possess {install,uninstall,status,detect}`。
2. `vacant_network/vrun/launcher.py` — **建議**（不是必須）把 `exit_code()` 的
   `ungated` 分出一個碼。**本輪刻意沒改**：會動到 `docs/AGENT_COMPAT.md`
   與已歸檔 run 的可比性。現在由 shim 層補。
3. `docs/AGENT_COMPAT.md` — 加一節「常駐設定檔路線」，跟既有的
   「`vacant run` relocate 路線」**分開記**（兩條路的失效方式不同）。
4. `README*.md` / `docs/VACANT_RUN.md` — 新的入口。

**Linux 那一輪（2026-09-20）點出來的四件**（按展場優先序，理由見 §六.4）
—— **已於同日第三輪修掉，逐格量測見 §九**

5. **`gateshim.exec_inner()` 的 per-run `CODEX_HOME` 要清掉**（每格 ~100 MB，
   無人值守會吃光磁碟）。⚠ **這一條排第一**：它是唯一會讓展件自己壞掉的。
   → **已修**（§九.1）
6. **codex 的 `env_key` 要有人管**：乾淨 Linux 沒有 `OPENAI_API_KEY` ⇒ 設定寫了
   也啟動不了，而 `install-status` 現在會說「✓ 已寫入」。至少要讓 status 標紅。
   → **已修**（§九.2：新增 `startable` 欄，真跑一次但不打模型）
7. **`uninstall` 要還原 `Linger`**：`install` 記下原值，`uninstall` 只在原本是
   `no` 的時候關回去。→ **已修**（§九.4）
8. **Linux 的閘門不能只靠 shell rc 的 `PATH` 區塊**（非互動 shell 收不到）。
   展件如果要閘門，走完整 shim 路徑或寫進 unit 的 `Environment=PATH=`。
   → **修了一半、另一半明講**（§九.3）

⚠ 第二輪（Linux 量測）**一行既有程式碼都沒改**，只補了
`possess.CHANNEL_MEASURED` 裡 codex／claude 兩格的量測字串（純紀錄欄，
不改任何行為）。**改碼是第三輪的事，見 §九。**

**已知的既有破損（不是本輪造成的）**：
`tests/test_r449c_launcher_prereg.py` 兩支失敗——改名那條線
（`fb7f4bfb`）把測試改成期待 `vacant_network/codebench.py`，
但它讀的那份 DECISION 檔內文還寫著舊名。

---

## 九、第三輪（2026-09-20）：把 Linux 那四個洞修掉，逐洞附負控制

- 執行端：**vacant-dev**（Ubuntu 24.04.4、systemd 255.4-1ubuntu8.17、Python 3.12.3）
- 單元測試在 **Mac** 上跑（那台沒有 pytest，§六.4-H）：
  `tests/test_vrun_possess.py` **30 → 62 passed**
- 派工前後 `df -h /` 都是 **2.5 G 可用**（尖峰 +101 MB，是負控制自己造的，已歸還）
- ⚠ **模型機時：零。** 本輪一通模型呼叫都沒有——`startable` 探測打的是一個
  只回 503 的本機 listener，洩漏的負控制用的是寫 20 MB 的假 agent。
- ⚠ 全程**沒有動人類的 `~/.claude/settings.json`**（那台有 17 天／29 天的長壽
  session），只動 codex 那一格；`vacant-exhibit.service` 全程沒被碰過。
- ⚠ 每一洞都是**先證明問題在、再證明修掉了**：負控制跑的是
  `git show HEAD:` 出來的**修改前那一份程式碼**，不是回憶。

### 9.1 洞 4：per-run 設定目錄的洩漏（第一順位）

**收尾契約寫進 `gateshim` 的 docstring**——誰刪、什麼時候刪、刪不掉怎麼辦：

| 層 | 誰刪 | 什麼時候 | 撐得過什麼 |
|---|---|---|---|
| 1 | `run_gate` 的 `finally` | `launcher.run()` 回來之後 | 一般失敗、agent 崩掉、Python 例外 |
| 2 | `SIGTERM`／`SIGHUP` handler ⇒ `SystemExit` ⇒ 仍然走 `finally` | systemd `stop`／`kill` | 溫和的終止 |
| 3 | **下一跑開場的掃地機** `sweep_cfg_dirs()` | 每次 `run_gate` 一開始 | **`SIGKILL`／斷電** |

**逐格實測**（假 agent 每格寫 20 MB 進 `CODEX_HOME`，`$TMPDIR` 隔離）：

| 格 | 修之前（`HEAD` 的 gateshim） | 修之後 |
|---|---|---|
| 1 | 21 MB（1 個目錄） | 1 MB（0 個） |
| 2 | 41 MB（2 個） | 1 MB（0 個） |
| 3 | 61 MB（3 個） | 1 MB（0 個） |
| 4 | 81 MB（4 個） | 1 MB（0 個） |
| 5 | **101 MB（5 個）** | **1 MB（0 個）** |

⇒ **用量不隨 N 成長**（O(1) 不是 O(N)）。

**`SIGKILL` 那一格**（`kill -9` 整個 process group）：

```
kill -9 之後        MB=21，殘留 1 份（run-codex-fd9d85a2）   ← ⚠ 會留，這是誠實的部分
再跑一格正常的      MB=1，殘留 0 份                          ← 下一跑的開場掃地機收掉
```

⚠ **能說的是「不累積」，不是「當下不留」。** 被 `kill -9` 的那一份**會**留到
**下一次有人經過閘門**（或 `--sweep`）。**如果迴圈從此再也不跑，那一份就一直在**
——那種情況下迴圈本來就停了，但這句話要說出來。

⚠ **不刪不是自己建的東西**，四道門：只掃專屬父目錄 `$TMPDIR/vacant-possess/`
（不掃 `$TMPDIR` 本身）；只刪有 `.vacant-possess-owner.json` 標記的；擁有者
`alive` 不刪；擁有者 **`unknown`（問不出來）也不刪**，退回 6 小時歲數門檻。
「pid 不在」與「pid 在但**行程啟動時刻對不上**（被重用）」才算 `dead`，當場收
——**那一格就是 `kill -9` 的垃圾能在下一跑收掉、而不是躺 6 小時的原因**。
刪不掉 ⇒ 不 raise、不靜默：印到 stderr、寫進 `possess.json` 的 `cfg_cleanup`、
把 owner 標記改寫成 `pid: 0` 交給下一次掃地機，**退出碼不變**
（磁碟沒清乾淨不是裁決，不可以污染 0／20／21／23）。

### 9.2 洞 1：`install-status` 會騙人 ⇒ 通道層改成**三欄**

| 欄 | 問的問題 | 證據 |
|---|---|---|
| `wired` | 設定檔寫了嗎 | 檔案 sha256 |
| **`startable`**（本輪新增） | **那個 agent 真的起得來嗎** | `probe_startable()` **真跑一次** |
| `proven` | 通道真的被中介了嗎 | `requests_seen > 0`（語意一個字沒動） |

**`startable` 怎麼做到「真跑一次」又「不打模型」**：開一個只收連線、
回 503 的本機 listener（127.0.0.1 隨機埠），用**跟 `install` 寫出來的同一支
wirer** 把設定寫進一個暫時 HOME、base url 指向那個 listener，relocate 過去，
跑一次 `probe_argv`，**判準＝listener 有沒有收到連線**，**第一條連線一到就
收工**。零 token、零費用、零外網。

**逐格實測（真 codex 0.147.0）**：

| 格 | `startable` | 耗時 | 證據 |
|---|---|---|---|
| **負控制**：乾淨登入環境（沒有 `OPENAI_API_KEY`） | **false** | 0.25–0.30 s | 連線 0 條，`env_key_present: false`，stderr 就是 codex 自己的啟動失敗 |
| 同一支探測，只多了 `OPENAI_API_KEY` | **true** | 0.31 s | 連線 1 條，`probe_saw: "POST /v1/responses HTTP/1.1"` |

五個 agent 全掃（乾淨登入環境）：**claude `true`**（`probe_saw:
"HEAD /api/hello"`，⚠ 它**沒有** `ANTHROPIC_API_KEY` 也起得來——Claude Code
走 OAuth 憑證那條，而那是紅線我們不讀，所以 `env_key_present: false` 對 claude
**不是判決**）、**codex `false`**、opencode／pi／hermes **`null`＝L-none**
（那台沒有可執行檔）——**`null` 不是 `false`**（鐵律 3）。

⚠ **這個探測量不到什麼**（寫在 docstring 裡）：量不到「跑得完一題」（它停在
第一個 byte 出門）；量不到使用者那份常駐設定檔本身有沒有被改壞（那看
`files[*].changed_since_install`）；量不到通道有沒有真的被中介（那是 `proven`）。

### 9.3 洞 2：Linux 的閘門對腳本／排程無效 ⇒ **修一半，另一半明講**

⚠ **這張表第一次量出來是全綠的，而且是假的。** 兩個陷阱，兩個都當場踩到：
(i) **PATH 繼承**——量表的那支 python 自己就跑在 source 過 rc 的 ssh session 裡，
子行程只是繼承；(ii) **stdin 是不是 socket**——bash 非互動時若判斷自己被遠端
shell daemon 叫起來就**會**讀 `~/.bashrc`，所以同一行 `bash -c` 在 ssh 裡是 ✅、
在 cron／systemd 裡是 ❌。`probe_gate_reach()` 現在每格都先消毒 PATH、
一律 `stdin=DEVNULL`。**不修這兩條，它會回報一個比事實樂觀的結果——
那正是本輪在修的那種病。**

**逐格實測（同一台、同一個 shim 目錄，負控制＝`git show HEAD:` 的那份碼）**：

| 怎麼起的 | 修之前 | 修之後 | 對應的真實情境 |
|---|---|---|---|
| `bash -lic` | ✅ **PATH 上 2 次** | ✅ **1 次** | 人類開終端機 |
| `bash -lc` | ✅ 1 次 | ✅ 1 次 | 登入非互動 |
| **`ssh 主機 '指令'`（真 ssh，從 Mac 打）** | ❌ 0 次 | **✅ 1 次** | 遠端下指令 |
| `bash -c '. ~/.bashrc'`（上一列的等價物） | ❌ 0 次 | ✅ 1 次 | — |
| **`bash -c`（非登入非互動）** | ❌ 0 次 | **❌ 0 次** | 腳本／cron／`ExecStart=` |
| **`systemd-run --user`** | ❌ 0 次 | **✅ 1 次** | **展場無人值守迴圈** |

三件事：

1. **PATH 出現兩次的 bug 修掉了**：區塊改成 `case ":$PATH:" in … esac` 的冪等
   守衛，`.profile` 與 `.bashrc` 都加也只有一份。
2. **`ssh 主機 '指令'` 通了**：`.bashrc` 的區塊改成插在 Ubuntu stock 那個
   「非互動就 `return`」**之前**（原本附加在檔尾，整段跑不到）。
3. **`systemd --user` 通了**：新增 `~/.config/environment.d/50-vacant-possess.conf`
   ⚠ 那個檔是 user manager **啟動時**才讀的 ⇒ 要立刻生效得加
   `--systemd-path-now`（對**正在跑的** manager 下 `set-environment PATH=`）。
   ⚠ 那個旗標**預設關著**，因為它動的是一台機器上大家共用的 user manager；
   `uninstall` 會把 manager 的 `PATH` 設回原值（原本沒有 ⇒ `unset-environment`）。

⚠ **`bash -c` 那一格沒修掉，也修不掉**：那種 shell **一個 rc 檔都不讀**
（`BASH_ENV` 要先有一個已經生效的環境才設得起來，雞生蛋）。
⇒ **不准安靜地只覆蓋一半**：`install` 收尾直接印警告、`install-status` 長期
印出這張表與一句
「⚠ **閘門只覆蓋了一部分叫起 agent 的方式**，這幾種收不到：`bash -c`」。
⚠ 通道層不受影響：那幾條路的模型呼叫**照樣進 journal**。

### 9.4 洞 3：`uninstall` 不把 `Linger` 關回去

`install` 現在**先問原值再動**（`linger_before`），並記下
`linger_enabled_by_us`；`uninstall` **只在「原值是 `no` 而且真的是我們把它變成
`yes`」時**才 `disable-linger`。

| 情境 | install 之後 | uninstall 之後 | `linger` 報告 |
|---|---|---|---|
| **原本 `Linger=no`** | `yes`（`enabled_by_us: true`） | **`no`** | `action: "restored"` |
| **原本 `Linger=yes`**（反面對照） | `yes`（`enabled_by_us: false`） | **仍然 `yes`** | `action: "skipped"`，理由：原值是 `yes`，不是我們開的 |

⚠ 報告分三種：`restored`／`skipped`／`failed`。全部塞成一個布林會讓
「本來就開著所以沒關」長得像「關失敗」。
⚠ `read_linger()` 問不出來回 `"unknown"`，**不回 `"no"`**，而 `unknown` 一律不動
（鐵律 3）。舊版 state 沒有 `linger_before` 這個欄位 ⇒ 也不動，理由寫在報告裡。

### 9.5 額外一件（Fable 2026-09-20 點名）：`install` 對 agent 自己的防護不再無作為

`vacant install` 以前只碰 `env`／provider 區塊，對沙箱姿態**完全無作為**。
而 codex 的預設沙箱 `workspace-write` **本來就不給 shell 指令網路**——那是廠商
自己實作的、比我們的 `PATH` shim 強的一層，白放著不用。

1. **`install` 把 codex 的 `sandbox_mode` 釘成 `workspace-write`**
   （實測：`sandbox_mode = "workspace-write"   # >>> vacant possess >>> …`，
   原值留在同一行的註解裡肉眼看得到，`uninstall` 逐位元還原、驗過 sha256）。
   逃生口 `VACANT_POSSESS_CODEX_SANDBOX`（`keep` ＝不碰），
   ⚠ **覆寫會留痕**：值進 `state.codex_sandbox_requested`，而且只要不是預設值
   就進 `install` 的 `warnings`。
2. **每個 agent 的姿態寫進收據**：`agent_posture{sandbox_mode, approval_policy,
   flags[]}`，`install` 存一份、`status` **當場重讀一份**（裝好之後被改掉才抓得到）、
   `gateshim` 逐跑寫進 `possess.json`。**讀不出來寫 `null`，不寫空字串。**
   理由：一個 `workspace-write` 下的 `accepted=true` 跟一個 `danger-full-access`
   下的 `accepted=true` 在收據上**長得一模一樣**——那正是 A 類假拒交那四格的病。

⚠ **只做了一半，另一半明講**：**閘門那條路**（`gateshim.exec_inner` 寫的 per-run
設定）**預設仍然是 `danger-full-access` ＋ `approval_policy = "never"`**。
沒改的理由是那正是 §六.4-F 四個退出碼實測時的姿態，改掉會讓那批已歸檔的格子
不可比。代價講明白：**那一跑裡 agent 的 shell 工具拿得到網路，它可以直接
`curl` 模型端點 ⇒ wire 零紀錄而收據照樣 `accepted=true`。**
現在至少**分得出來**（`possess.json` 的 `agent_posture`），而且
`VACANT_POSSESS_CODEX_SANDBOX=workspace-write` 關得起來。
⚠ 實驗 harness `ops/vacantrun/wrap_agent.sh` 那三行**刻意沒碰**（改了既有 run 不可比）。
⚠ **兩條路的預設不一樣，不可以混講成一句。**

### 9.6 本輪之後**仍然不能說的話**

1. **仍然不能說「不會被繞過」。** §五那十條路一條都沒有消失；本輪只是把
   第 10 條（Linux 非互動 shell）從「四種全滅」縮到「`bash -c` 那一種」，
   而且**那一種是明講的**，不是修掉的。
2. **不能說 per-run 目錄「零殘留」。** 能說的是**不隨格數累積**；`SIGKILL`
   的那一份要等下一跑。刪不掉的情況（權限／NFS busy）只保證**會被記下來**。
3. **不能說 `startable: true` ＝ 這個 agent 能交付工作。** 它只量到
   「起得來而且開得了連線」。claude 那一格更要小心：它連上的是
   `HEAD /api/hello`，那是啟動探測不是模型請求。
4. **不能說五個 agent 都量過。** 本輪 `startable` 真正量到的只有
   **codex（true／false 兩格）與 claude（true 一格）**；
   opencode／pi／hermes 在那台是 **L-none**。
5. **不能說重開機之後還在**（§七-6 不變，本輪一樣沒重開機）。
6. **不能說 `workspace-write` 擋得住什麼。** 它是廠商實作的，我們只是不再
   把它拆掉；而閘門那條路上**我們仍然在拆它**（§九.5）。
7. **那 62 個單元測試一樣沒有在 Linux 上跑過**（vacant-dev 沒有 pytest）。
