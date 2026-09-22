# NOTE 2026-09-22 — 「裝一次、打開 pi、`/vacant on`」怎麼用最少的件數做到

> **狀態：研究＋施工計畫，等人類裁決，還沒有動任何產品碼。**
> 本份的 pi 事實**全部從 pi 0.87.0 的原始碼與隨附文件讀出來**
> （`npm install @earendil-works/pi-coding-agent@0.87.0` 到 scratchpad 讀的），
> vacant-dev 上跑的是 **0.85.1**——兩個版本的差異本份沒有量，引用時要連版本一起講。
> OpenCode 的事實來自 `@opencode-ai/plugin` 1.18.32 的型別檔與 opencode.ai/docs。
> **一格都沒有真跑**；本份的證據等級是「讀碼」，不是 L-real。

---

## 〇、人類 2026-09-22 要的東西（原話拆成兩個形狀）

> 我需要最後安裝達到的是至少 pi & opencode 可以被應用到，像是這樣安裝：
> Pi 安裝（或是使用者本來就有）→ 安裝 vacant → 啟動 pi → 聊天介面 `/vacant on`。
> 或是 Vacant 打開就可以引導綁定本機 cli agent，所以我第一次被引導綁定之後，
> 以後打開 Vacant 就可以是應用 pi 的 vacant pi 了。

| 形狀 | 使用者做什麼 | 承接它的既有件 |
|---|---|---|
| **A：在 agent 裡面** | `pip install vacant-network` → `vacant install` → 照舊打 `pi` → 在輸入框打 `/vacant on` | `possess.py`（通道＋常駐 proxyd）＋ **一支 pi extension（現在沒有產品版）** |
| **B：從 Vacant 這邊進** | 打 `vacant` → 第一次選 pi 並記住 → 以後打 `vacant` 就直接是 Vacant 底下的 pi | `vacant on`（`cli._on_shim` ＋ `agentwrap.py`，2026-09-22 剛進）——**缺「記住」** |

兩個形狀不互斥，而且**共用同一支 extension**（見 §三）。

---

## 一、現況（讀碼，2026-09-22）

### 1.1 形狀 A 今天走到哪

- `vacant install --agent pi`（`possess.wire_pi`）做的是：改寫 `~/.pi/agent/models.json`
  裡**每一個** provider 的 `baseUrl` 指到常駐 proxyd，再加一個 `vacant` provider，
  模型寫死 `VACANT_AGENT_MODEL`（預設 `gemma-4-12b-it-qat`）；PATH shim 負責閘門。
- **這一格從來沒有被 `requests_seen` 證實過**（`CHANNEL_MEASURED["pi"] == ""`），
  `install-status` 標 `unverified`。原因是兩台機器上都沒有 pi 可執行檔。
- docstring 自己記著一個沒解的問題：`models.json` vs `models-store.json` 哪一份是真相。
  **§二-1 用原始碼回答了。**
- **掛鉤一個都沒裝**：`vacant-hook/1` 契約（`hookcli.py`）與 pi 的 extension
  只活在證據目錄 `ops/vacantrun/enclosure_20260920/evidence_agent_attest/vacant_pi_extension.ts`
  與凍結腳本 `wrap_agent.sh` 的 pi 段；`possess.py` 不寫它（`goal.md` §〇 第 3 點）。
- 互動 TUI **預設不 gate**（`gateshim.py:290`，`VACANT_POSSESS_GATE_TTY=1` 才開）
  ⇒ 使用者「打開 pi 聊天」這一幕，今天只有通道，沒有裁決收據。
- 沒有任何「`/vacant …`」——pi 裡面看不到 Vacant，除了狀態列的 provider 名字。

### 1.2 形狀 B 今天走到哪

- `vacant`（裸）＝選單；`vacant on pi`＝`vacant run --stdin inherit -- python -m …agentwrap pi`
  ⇒ 這一跑自己的 `PI_CODING_AGENT_DIR`＋`models.json`，`exec pi --provider vacantproxy --model m`。
  互動三條件在 cli 端釘死兩條（stdin inherit、不給 `--json`）。
- 走的是 relocate 那條**量過**的路（600 格 abpi ＋ pi_tty 兩批），與形狀 A 的常駐路不同，
  **證據等級不同、不可互相背書**（`agentwrap.py` 誠實邊界 3）。
- **缺**：不記得上次選誰，每次都出選單；一次性提示句 `--model m` 讓狀態列顯示 `(vacantproxy) m`。
- 閘門觸發點在行程結束（`launcher`），互動 session 關掉那一刻才驗收——
  對「聊天」這種沒有固定交付物的用法，收據多半是 `21`（沒有驗收可跑）。

---

## 二、從 pi 0.87.0 讀出來、會改變設計的四件事

### 1. `models-store.json` 是**目錄快取**，不是設定；`models.json` 才是使用者設定

`dist/core/model-runtime.js:80`：`new FileModelsStore(options.modelsStorePath ?? join(dirname(modelsPath), "models-store.json"))`；
`docs/providers.md:3`：「configured providers may refresh newer catalogs and **cache** them in
`~/.pi/agent/models-store.json` for offline use」。
⇒ `possess.wire_pi` 的那條「哪一份才是真相」可以關掉：**寫 `models.json` 是對的檔**。
⚠ 這是 0.87.0 的碼；0.85.1 要在 vacant-dev 上 `grep -rn models-store dist/` 一次確認。

### 2. extension 一支就能做完「通道＋開關＋掛鉤」，而且**不必碰 `models.json`**

`docs/extensions.md` 逐字列出的 API（§1453 起）：

| 需要什麼 | pi 給什麼 | 註 |
|---|---|---|
| 把模型通道指到 proxyd | `pi.registerProvider("vacant", {baseUrl, api:"openai-completions", apiKey, models 或 refreshModels})` | 在 factory 裡呼叫會排隊到 runner 起來；在 command handler 裡呼叫**立即生效、不用 `/reload`** |
| 模型清單 | `refreshModels({signal})` 去打 `${proxy}/v1/models` | **這一通同時就是 canary**（`hookcli` 的 `/v1/models?vacant_canary=`）；模型名不再寫死 `gemma-…` |
| `/vacant on` | `pi.registerCommand("vacant", {handler, getArgumentCompletions})` | 參數 `on`／`off`／`status` 自動補全 |
| 切到 Vacant 的模型 | `pi.setModel(ctx.modelRegistry.find("vacant", id))` | 記進 session、**不改 `defaultProvider`**；provider 沒有 auth 會回 `false` |
| 關掉 | `pi.unregisterProvider("vacant")` ＋ `setModel(原來的)` | 立即生效 |
| 掛鉤契約 | `session_start`／`before_agent_start`／`tool_call`／`tool_result`／`before_provider_request`／`agent_end`／`session_shutdown` | 與 2026-09-20 A 級那一跑用的**同一組事件** |
| 在回合結束時做事 | `agent_before_settle`：「the final actionable boundary: it can append session entries and request one continuation」 | 這就是**互動模式下的閘門觸發點**（§三-3） |
| 自動載入 | `~/.pi/agent/extensions/*.ts`、`~/.pi/agent/extensions/*/index.ts`，或 `settings.json` 的 `extensions: [路徑]`（**不複製**），或 `pi install <路徑|git:|npm:>` | jiti 載入，TypeScript 不用編譯 |
| 測試 | `pi -e ./vacant.ts` | 一次性，不動任何設定 |

### 3. 首次設定精靈與專案信任不會擋路

`shouldRunFirstTimeSetup()` 看到 `PI_CODING_AGENT_DIR` 就跳過（2026-09-20 讀碼）；
`~/.pi/agent/extensions/` 是全域 scope，**不需要專案信任就載入**——
這既是「裝一次就有」的成立條件，也是 `AGENT_HOOKS_MEASURED` §三 說的「agent 寫得到那個目錄就能關掉」。

### 4. `-p` 也燒同一組事件

`DECISION_20260920_AGENT_HOOKS_MEASURED.md` §二：pi 的 `session_shutdown` 等「`-p` 也跑」。
⇒ 同一支 extension 對互動與 print 兩種模式都成立，**不必分兩份**。

---

## 三、建議的最終形狀（件數最少的那一種）

### 3.1 `vacant install --agent pi` 改做三件事，少做一件

| | 現在 | 建議 |
|---|---|---|
| 常駐 proxyd（launchd／systemd --user） | ✅ 有 | 不動 |
| 寫 `~/.pi/agent/models.json` | ✅ 改寫每個 provider 的 baseUrl ＋ 加 `vacant` | **不再寫**——provider 由 extension 在 runtime 註冊；使用者自己的 provider **一個都不改道**（使用者關掉 Vacant 時他的東西要原封不動，這也讓 uninstall 少一個要逐位元還原的檔） |
| PATH shim（閘門） | ✅ 有 | 保留給 `pi -p` 那條；互動那條的閘門改由 extension 承接（§3.3） |
| **寫一支 extension** | ❌ 沒有 | `~/.pi/agent/extensions/vacant/index.ts`（`write_tracked`，可逐位元還原）；內容隨 wheel 出貨（`vacant_network/vrun/agents/pi/vacant.ts`，要進 `pyproject` 的 package-data） |

⚠ **改道使用者既有 provider 這件事要不要保留，是一個裁決點**：保留＝「即使他選自己的
provider 也經過 proxyd」（通道更完整，但沒有 `/vacant off` 的語意）；拿掉＝「`/vacant on`
才經過」（語意乾淨，但 off 的時候零痕跡）。**建議拿掉但把 off 事件寫進掛鉤日誌**（§3.4-3）。

### 3.2 extension 的行為（形狀 A 與 B 共用同一支）

```
factory(pi):
  state = 讀 ~/.vacant/possess/state.json（port、enabled_agents、model 偏好）
  pi.registerProvider("vacant", { baseUrl: http://127.0.0.1:<port>/v1,
      api: "openai-completions", apiKey: "sk-vacant-possess",
      refreshModels: 打 ${proxy}/v1/models?vacant_canary=<run_id> })
  pi.registerCommand("vacant", { on | off | status })
  掛鉤：與 evidence_agent_attest/vacant_pi_extension.ts 逐字相同的那七個事件 → hookcli
  pi.on("session_start"): 若 state 說 pi 預設開 ⇒ pi.setModel(vacant/<model>)
```

- `/vacant on`：`setModel` 到 `vacant` provider，記住原來的 (provider, model)，狀態列變 `(vacant) <model>`。
- `/vacant off`：`setModel` 回原來的，**寫一筆 `vacant_off` 進掛鉤日誌**（有痕跡、沒有裁決）。
- `/vacant status`：proxyd 有沒有在聽、這個 session 的 `requests_seen`（讀 proxyd journal 或打 `/v1/models`）、掛鉤日誌路徑。
- **fail-closed 不用另外寫**：模型一旦指到 `vacant` provider，proxyd 沒起來就是 connection refused，
  pi **不會**自己換 provider（`pi.setModel` 是 session 層的選擇）。但要在 `session_start` 探一次並 `ctx.ui.notify`，
  讓使用者知道是 Vacant 那一層壞了不是模型壞了（`possess.py` 三個緩解的第 (iii) 條）。

### 3.3 互動模式的閘門：`agent_before_settle`（**這一條要獨立裁決**）

今天的教條是「觸發點在行程結束」（`launcher.py` docstring）。互動 session 沒有那個時刻
（或者說那個時刻在使用者關掉 pi 時，交付物早就被拿走了）。pi 提供的 `agent_before_settle`
正是「這一回合 agent 不會再自己動了」的邊界，而且**可以 append entry ＋ 要求一次繼續**——
那就是 V1 `--retry revise` 的迴圈，只是回饋不經檔案、直接進對話：

```
agent_before_settle:
  若工作區有驗收（resolve_suite 的同一套判準）⇒ pi.exec(python -m vacant_network.vrun.acceptance …)
  沒過 ⇒ append 一筆回饋 entry（模板逐字用 retry.py 的），request continuation（上限 N）
  每一次都由 python 端簽 ws_attempt（同 launcher 的對帳規則 attempt ≥ verdict）
```

⚠ 兩條不可淡化：
1. **這是掛鉤層＝「是什麼」，不是「有沒有」**（`COMPLETE_MEDIATION` §二）。agent 刪掉 extension
   下一回合就沒有——級別由探針決定，收據上會寫 `canary_fired=false`。
2. 它改變「觸發點」的教條，而 `21`／`23` 的既有語意不可以動 ⇒ 互動閘門的裁決要**另開退出碼或欄位**，不能重用 `0`／`20`。

### 3.4 三條誠實邊界（改碼要保留）

1. 「裝了 extension」≠「被中介」——唯一證據仍是 proxyd journal 的 `requests_seen`；
   `install-status` 的 `wired`／`proven` 兩欄不變。
2. 「A 級」是**那一跑**的屬性；extension 存在只證明這一次燒了 canary。
3. `/vacant off` 是使用者的選擇，不是 Vacant 的失效；但那一段要留痕（掛鉤日誌），
   收據不會替它說謊——`requests_seen` 在 off 的那段就是 0。

---

## 四、形狀 B：`vacant` 記住綁定（小改，一支檔）

`cli._on_shim`：
- 新增 `~/.vacant/possess/bound.json`：`{"agent": "pi", "binary": "...", "version": "...", "at": ...}`。
- 裸 `vacant`：有 `bound.json` ⇒ 直接 `vacant on <agent>`；沒有 ⇒ 現在的選單，選完問一次「記住？」（非 tty 不問、不記）。
- `vacant bind <agent>`／`vacant unbind`／`vacant on --pick`（強制出選單）。
- 順手把 `agentwrap.wire_pi` 的 `--model m` 換成真模型 id（狀態列可讀）。

⚠ B 路走的是 per-run 暫存設定＝這一跑自己的 ephemeral proxy，**與常駐 proxyd 是兩個端點**；
綁定記的是「開哪個 agent」，不是「用哪條通道」。兩條路的收據 wire log 各自對得起來，不混。

---

## 五、OpenCode（第二優先，但結構上到不了 A 級）

| 需要什麼 | OpenCode 給什麼（`@opencode-ai/plugin` 1.18.32 型別檔／docs） | 判斷 |
|---|---|---|
| 自動載入 | `~/.config/opencode/plugins/*.js`、`.opencode/plugins/`、config `plugin: []`（npm） | ✅ 與 pi 同型：`vacant install` 寫一支檔 |
| 通道指到 proxyd | plugin 的 `config?: (input: Config) => Promise<void>` 拿到整份 Config（含 `provider`、`model`） | ⚠ **能不能就地改、改了算不算數沒量**；量到之前照用 `possess.wire_opencode`（2026-09-19 macOS 2 通，L-real） |
| `/vacant on` | **沒有** plugin 註冊 slash command 的 API；`command` 是 config 裡的 **prompt 模板**（送給 LLM），`command.execute.before` 只能攔到「某個模板命令要送出」 | ❌ 做不出一個真的開關；能做的是 `/vacant-status` 模板＋ `` !`vacant possess status` `` 把狀態注入 prompt（誠實：那是給模型看的字，不是開關） |
| 掛鉤 | `tool.execute.before`／`after`、`event`（`session.idle` 等）、`chat.params`／`chat.headers` | ✅ 攔得到工具；❌ **沒有回合開端事件** ⇒ `unexplained ≥ 1`，到不了 A 級（`FIRST_TIER_A_RECEIPT` 已裁） |
| 模型切換 | plugin API 沒有 `setModel`；`client`（SDK）有 session／tui 端點，**沒查到切模型的** | ⚠ 「on/off」在 OpenCode 只能是**重開**（config 層），不是輸入框裡切 |

⇒ OpenCode 的誠實形狀是「**裝一次就預設在**」（config 層，已有實測），**不做 `/vacant on`**；
文案要寫「OpenCode 沒有輸入框開關，關掉的方式是 `vacant uninstall --agent opencode`」。

---

## 六、施工順序（按「觀眾／使用者看得到差別」排）

| # | 做什麼 | 動哪裡 | 完成判準 | 大小 |
|---|---|---|---|---|
| **P0** | pi extension 產品版：provider 註冊＋`/vacant on|off|status`＋掛鉤七事件；`possess.wire_pi` 改成裝 extension、不寫 `models.json` | `vacant_network/vrun/agents/pi/vacant.ts`（新）、`possess.py`、`pyproject.toml` package-data、`tests/test_vrun_possess.py` | pytest 綠（tmp HOME、`--no-service`）；`node --check` 那支 .ts 的可執行檢查照 `multiparty_viewer_node_check.mjs` 的先例（沒 node 就 skip 並印理由） | 1 支 PR |
| **P1** | 在 vacant-dev 量 pi：`pi -p` 拒交／交付兩格 ＋ 互動兩格（`ops/vacantrun/tty_drive.py`），常駐 proxyd 那條 | `ops/vacantrun/possess_pi_2026XXXX/`、`CHANNEL_MEASURED["pi"]`、`docs/AGENT_COMPAT.md` | `requests_seen > 0`、`--selftest` 先過再驗、負控制（proxyd 關著 ⇒ pi 報 connection refused、**沒有**落到 api.openai.com） | 機時，不搶 R535 |
| **P2** | 形狀 B 的「記住」 | `cli.py::_on_shim`、`agentwrap.py` | 裸 `vacant` 直接開；非 tty 不記不問 | 半支 PR |
| **P3** | OpenCode plugin（掛鉤＋`config` hook 探一次改不改得動） | `vacant_network/vrun/agents/opencode/vacant.js`、`possess.wire_opencode` | 量到 `config` hook 的結果之後才決定要不要換掉寫 opencode.json | 1 支 PR ＋ 機時 |
| **P4** | 互動閘門 `agent_before_settle`（§3.3） | 新裁決檔、`retry.py`、extension | **先寫裁決再動碼**；不動 `0`／`20`／`21`／`23` | 裁決＋1 支 PR |

**P0 不需要任何機器上的 pi**：extension 是文字檔，安裝／還原／idempotent 全在 tmp HOME 測得到。
**P1 之前不准把 pi 那格寫成「裝好就有」**——今天那句話對 pi 仍然為假。

---

## 七、順手抓到的三件小事（不在主線，記著）

1. `agentwrap.wire_pi` 的模型名寫 `"m"`，狀態列顯示 `(vacantproxy) m`——展場肉眼那一行要可讀。
2. `possess.wire_pi` 把**所有** provider 的 `baseUrl` 一律換成 `/v1` 形（`_base_for("openai", …)`），
   包含 `api: "anthropic-messages"` 的 provider；proxyd 按 path 路由所以形狀上可能通，**沒量**。
   §3.1 的建議（不改道既有 provider）會讓這條消失。
3. `cli.py` 的 `_POSSESS_TOP` 只攔 `install`／`uninstall`，`vacant possess status` 才是附身狀態
   ——README 目前沒有任何一行寫 `vacant install`，外人照 README 找不到這條路（「功能在但構不到」＝附身失敗，`goal.md` §三-2）。
