# DECISION 2026-09-19｜`vacant install`：從「每次要打的包裝器」到「裝一次就預設在」

> **一句話（做到什麼、做不到什麼）**
> **通道層做到了「裝一次就在，除非你刪掉」**：五個 agent 的 base url 寫進它們**自己的
> 常駐設定檔**，關終端機、開新視窗、**打完整路徑**都照樣經過 proxy；三個 agent
> （codex／opencode／Claude Code）在 macOS 上用真模型量到 `requests_seen > 0`，
> 命令列上**零個 vacant**。
> **閘門層只做到「預設會跑」**：靠 `PATH` shim，**打完整路徑就跳過**。
> ⚠ **本檔不出現「不會被繞過」。** 那是做不到的宣稱
> （[`DECISION_20260919_BYPASS_STRESS.md`](DECISION_20260919_BYPASS_STRESS.md) 已經
> 逐條量過為什麼）。

- 量測日期：**2026-09-19 深夜 → 09-20 凌晨**（CST）
- 執行端：**人類的 macOS 15（Darwin 24.6.0）**；上游 **1003**
  `http://100.119.113.56:1234`，`gemma-4-12b-it-qat`
- 版本：codex-cli **0.153.2**、opencode **1.18.31**、Claude Code **2.1.278**
  （⚠ 跟 `docs/AGENT_COMPAT.md` §10 的 codex **0.147.0** 不是同一個；
  **同一格兩個版本號不可以混寫成一個**）
- 判斷層：`vacant_network/vrun/{possess,proxyd,gateshim}.py`（本輪新增）
- 證據等級：**L-real**（真 agent、真模型、真流量）——但只有 **3/5** 個 agent；
  pi 與 hermes 在那台機器上**沒有可執行檔**，只有設定目錄 ⇒ 接線碼跑過，
  **`requests_seen` 一通都沒有** ⇒ 那兩格是 **L-none**。

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
| macOS `launchd` | `RunAtLoad` ＋ `KeepAlive` | ✅ |
| Linux `systemd --user` | `Restart=always` ＋ `loginctl enable-linger` | ✅（linger 成功時；失敗會記在 state） |
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

---

## 七、**還不能說的話**

1. **不能說「不會被繞過」。** 第五節有九條路。閘門層連「預設會跑」都有兩個
   刻意的例外（passthrough、互動 TUI）。
2. **不能說五個 agent 都接通了。** 通道層 **3/5 是 L-real，2/5（pi、hermes）
   是 L-none**——那台機器上沒有它們的可執行檔，接線碼跑過但**一通都沒量到**。
   pi 還多一個未解問題（`models.json` vs `models-store.json`）。
3. **不能說閘門在五個 agent 上都有牙齒。** 閘門層本輪只量了 **codex**（4 格）。
   其餘四個沒量。
4. **不能說這是一張同條件矩陣。** 只有一台機器（macOS）、一個模型、一題、
   每格 n=1。`docs/AGENT_COMPAT.md` §13 那種五 agent × 兩格 × 兩次的複製
   **本輪沒做**。
5. **不能說 Linux 那邊也成立。** `systemd --user` ＋ `enable-linger` 那條路
   **一次都沒跑過**——程式碼寫了，**沒有任何機器上的證據**。
   展場機器是 Linux VM ⇒ **這是展件可用之前必須補的一格**。
6. **不能說重開機之後還在。** `RunAtLoad` 寫了、`launchctl print` 顯示
   `properties = keepalive | runatload`，但**本輪沒有真的重開機驗**。
7. **不能說常駐 proxy 撐得住併發。** 多個 agent 同時打同一個埠沒有壓測過；
   `ThreadingHTTPServer` 的行為在高併發下沒量。
8. **journal 分不出是誰打的。** 常駐 proxy 沒有 per-agent 標記 ⇒
   `install-status` 的 `resident_journal` 只能回答「通道層活著而且有流量」，
   **不能回答「這個 agent 被中介了」**。後者要 `channel[*].proven`，
   而那一欄只有走過閘門的那一跑才點得亮。
9. **`0.4 G`／磁碟／機時**：本輪全部在 macOS 的 scratchpad，vacant-dev 一個
   byte 都沒佔。

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

**已知的既有破損（不是本輪造成的）**：
`tests/test_r449c_launcher_prereg.py` 兩支失敗——改名那條線
（`fb7f4bfb`）把測試改成期待 `vacant_network/codebench.py`，
但它讀的那份 DECISION 檔內文還寫著舊名。
