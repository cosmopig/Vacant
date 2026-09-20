# DECISION 2026-09-20 — **`pi -p` 不是「另一種用法」，是 pi 自己的預設落點**

> **狀態：實測完成，結論寫死。** 本份回答的是人類 2026-09-20 的質疑：
> 「我要你去幫我做確認你的 pi 是使用這種輸入框嗎？還是適用 `pi -p prompt`
> 我不要這種去測」。
> 🔴 **不准**與 R535／R530／R534／G 實驗／pbgate 任何一批的數字合併或相減。
> 🔴 本份的任何數字**綁死在 pi 0.85.1 × `gemma-4-12b-it-qat` × b1003 上**。

- 執行端：vacant-dev `user1@100.124.254.83`（Ubuntu 24.04、Python 3.12.3）
- 工作根：`/var/tmp/vacant_tty_20260920`，repo 子集自 `integrate/20260919` @ `a500f9bb`
- agent：**pi 0.85.1**（`/home/user1/.local/opt/node-v22.23.2-linux-x64/bin/pi`）
- 後端：**b1003**（`100.119.113.56:1234`，LM Studio 0.4.24，thinking）**一台**
  （b1004 的 4 串當時被 abpi 那批佔著，本批刻意不碰）
- 證據等級：**L-real**（真模型）

---

## 〇、一句話

**`-p` 不是「一種沒人用的呼叫方式」。它是 pi 在「stdin 或 stdout 任一不是 tty」
時自己會落進去的模式**——而沒有自己配一張 pty 的 harness（cron、systemd、CI、
以及 `vacant run` 的預設）全都滿足那個條件。

真的把 pi 放進互動輸入框之後，Vacant 的**中介與閘門都還在**，而且
**送給模型的第一通請求與 `-p` 逐位元相同**。

⇒ **600 格不作廢。要加的但書不是「模式不真實」，是「單輪」。**

---

## 一、pi 0.85.1 到底有哪些呼叫形態（讀碼，不是猜）

`dist/main.js` 的 `resolveAppMode()` **逐字**：

```js
function resolveAppMode(parsed, stdinIsTTY, stdoutIsTTY) {
    if (parsed.mode === "rpc")  return "rpc";
    if (parsed.mode === "json") return "json";
    if (parsed.print || !stdinIsTTY || !stdoutIsTTY) return "print";
    return "interactive";
}
```

四種模式，三支實作：

| 模式 | 怎麼進 | 實作 | 誰在餵輸入 |
|---|---|---|---|
| `interactive` | `pi [prompt...]`，**且 stdin 與 stdout 都是 tty** | `modes/interactive/interactive-mode.js` | 人（TUI 輸入框） |
| `print` | `-p`／`--print`，**或** stdin 非 tty，**或** stdout 非 tty | `modes/print-mode.js` | argv／管道，一次性 |
| `json` | `--mode json` | 同上（`runPrintMode(mode="json")`） | 同上，輸出改成 JSON 事件流 |
| `rpc` | `--mode rpc` | `modes/rpc/rpc-mode.js` | **JSON-RPC over stdin/stdout**（`prompt`／`steer`／`follow_up`／`abort`…） |

**三件事必須分清楚：**

1. **`-p` 只是三個充分條件之一。** 拿掉 `-p` 不會讓 pi 變成互動——
   `< /dev/null`（launcher 預設）或把 stdout 導進檔案（`vacant run --json`
   做的正是這件事）**任一個**都會把它推回 `print`。
2. **管道輸入也會降級**：`main.js` 讀到 piped stdin 時，
   `if (stdinContent !== undefined && appMode === "interactive") appMode = "print";`
3. **`--mode rpc` 是第四條路**，而且它才是「程式化驅動、但走完整 agent 迴圈」
   的官方做法。**本批沒有量它**（見 §七）。

### 互動模式：怎麼進、怎麼餵、怎麼結束

- **進**：`pi "prompt"`（沒有 `-p`）。`prompt` 會變成 `initialMessage`，
  在 TUI 起來之後**自動送出**（`interactive-mode.js`：
  `if (initialMessage) { await this.session.prompt(initialMessage, …) }`）。
- **餵**：`while (true) { const userInput = await this.getUserInput(); await this.session.prompt(userInput); }`
  ⇒ **第一回合結束之後它不會結束，會停在輸入框等人。**
- **結束**：`Ctrl-D`（輸入框是空的時）／`Ctrl-C` 連按兩下（500 ms 內）／
  `/quit`／`SIGTERM`、`SIGHUP`。四條路最後都走 `shutdown()` → `process.exit(0)`。
  互動離開時會多印一行 `To resume this session: pi --session <uuid>`
  ——**那一行只有互動模式印得出來**，本批拿它當模式的指紋。

### 不會擋路的兩件事（讀碼確認，本批也沒踩到）

- **首次設定精靈不會跳**：`shouldRunFirstTimeSetup()` 第三條就是
  `if (process.env[ENV_AGENT_DIR]) return false;`——Vacant 一定會設
  `PI_CODING_AGENT_DIR`，所以那條路走不到。
- **專案信任不會問**：`resolveProjectTrusted()` 第二條
  `if (!hasTrustRequiringProjectResources(cwd)) return true;`——
  R534 的工作區只有 `goal.md`／`contract.md`／`run_tests.sh`／`tests_visible/`，
  沒有 `AGENTS.md`／`CLAUDE.md`／`.pi/`，所以直接回 true。

### 模式量具（**先證明量得動**）

判準取自 pi 自己的碼，零機時：

```js
if (startupBenchmark && appMode !== "interactive") {
    console.error(chalk.red("Error: PI_STARTUP_BENCHMARK only supports interactive mode"));
    process.exit(1);
}
```

`ops/vacantrun/pi_tty_20260920/mode_oracle.sh` 把它做成可重跑的四格：

| 格 | stdin | stdout | `-p` | 退出碼 | 那句錯誤 | ⇒ 模式 |
|---|---|---|---|---|---|---|
| **A** | pty | pty | 無 | **0** | 無（畫出 TUI） | **interactive** |
| **B** | `/dev/null` | pipe | 無 | 1 | 有 | print |
| **C** | pty | pty | **有** | 1 | 有 | print |
| **D** | pty | **檔案** | 無 | 1 | 有 | print |

**B 與 D 就是這一份最重要的負控制**：B 證明「拿掉 `-p` 但沒有 tty」仍是 print，
D 證明「有 pty 但 stdout 進檔案」也是 print。
⚠ D 格的 `ORACLE mode=… stdout_tty=1` 那一行是**殼層自己的** stdout，
重導只加在 `pi` 那一條命令上——不是矛盾。

---

## 二、互動模式下 Vacant 還中介得到嗎——**得到**

### 為什麼結構上必然（讀碼）

`main.js` 的順序是：**先**建 runtime（第 676 行 `createAgentSessionRuntime`，
它就是讀 `$PI_CODING_AGENT_DIR/models.json` 的那一步），**才**分派模式
（第 751/756/790 行）。三條路 `runRpcMode(runtime)`／
`new InteractiveMode(runtime, …)`／`runPrintMode(runtime, …)` 拿的是
**同一個 runtime 物件**，而且三者都走 `session.prompt(...)`。

⇒ **`PI_CODING_AGENT_DIR` ＋ `models.json` 那條接線與模式無關。**

### 實測（本批 L-real）

見 §五的表。互動臂每一格的 `requests_seen` 都 > 0、`wire_by_protocol`
都是 `{"openai": N}`、wire index 逐條都是
`POST /v1/chat/completions -> 200`，upstream 是 b1003。
TUI 的狀態列上也直接寫著 `(vacantproxy) gemma-4-12b-it-qat`。

### `--stdin inherit` 是為什麼存在的

`launcher.py` 預設 `stdin=subprocess.DEVNULL`，註解逐字寫著
「`pi -p` 不給 `< /dev/null` 會永久卡住」。`--stdin inherit` 就是
**給互動式 agent 用的那個例外**，而且它自己也記了代價：

```python
#   **`--stdin inherit` 例外**：分家會讓子行程失去控制終端，
#   互動式 agent 讀 tty 會直接 EIO。那一格我們就量不到孤兒，
#   `orphans_killed` 落 `None`（＝沒量），不是 `False`（＝沒有）。
```

⇒ 互動那一格 `start_new_session=False`，**孤兒回收沒有量**。這是真的代價，
不是漏寫。

🔴 **但 `--stdin inherit` 一個人不夠**：它只處理 stdin。stdout 還得是 tty
（⇒ **不可以給 `--json`**），而且要有人真的配一張 pty。三個條件缺一，
pi 就安靜地落回 print，**而且不會報錯**。

---

## 三、互動模式下閘門還成不成立——**成立，但那句招牌話要改寫**

閘門跑在 `proc.wait()` 回來之後——**agent 行程結束的那一刻**，這一點與模式無關。
差別在「那一刻是誰造成的」：

| | `-p` | 互動 TUI |
|---|---|---|
| 誰結束了行程 | **agent 自己**（跑完 → `runPrintMode` return → exit） | **人**（Ctrl-D／`/quit`／關視窗） |
| 閘門何時跑 | 行程結束那一刻 | 行程結束那一刻（**同一行程式碼**） |
| 招牌話 | 「agent 自己宣告完成、退出碼 0 走人，閘門仍在行程結束那一刻擋下來」 | ❌ 這句**不適用** |

✅ 互動模式的對應說法（本批可支撐）：
**「人以為做完了、關掉終端機走人，閘門在那一刻跑驗收，該擋的照擋。」**

為了證明「照擋」不是靠運氣，本批專門設了 `INTQ` 臂：
**人在 agent 還沒寫完就按 Ctrl-D**。結果見 §五。

---

## 四、`-p` 與互動會不會給模型不同的東西——**第一通逐位元相同**

`ops/vacantrun/pi_tty_20260920/pi_tty_wirediff.py` 直接讀**中介自己落下的
請求原文**（`wire_RUN-ON/<call_id>.req.bin`），比 `PTP`（pty × `pi -p`）與
`INT`（pty × 互動 TUI）**同題同 rep 的第一通** `POST /v1/chat/completions`。

比的欄位：system 訊息、全部 messages、`tools[*].name`、取樣與上限參數、
其餘 top-level key。

⚠ **第一版量出「system prompt 不同」是假陽性**，必須記下來：兩邊
`system_chars` 都是 2778、`raw_bytes` 都是 5983，只有雜湊不同——
差的是 system prompt 裡那行 `Current working directory: …/ws_<task>_<ARM>_r<n>`，
而 `PTP` 與 `INT` 剛好等長。**那三個字母是我們自己的目錄名，不是模式的差。**
抵銷掉之後（`_norm()`）兩邊逐位元相同。

量具負控制（零機時）：把一格的第一通請求 body 裡的 system 加一行字，
比對器必須抓到 —— 抓到了（`identical=False`，`system_unified_diff` 指出那一行）。

---

## 五、小型實驗：五臂、五題、40 格

### 設計（發射前寫死）

| 臂 | 外層 | launcher | wrapper | pi 實際模式 | 這一臂回答什麼 |
|---|---|---|---|---|---|
| `PRT` | 直跑 | `--json`、stdin devnull | `wrap_agent.sh`（**凍結**） | print | 600 格那批的參考形狀 |
| `PTP` | 真 pty（`--no-quit`） | `--stdin inherit`、無 `--json` | `wrap_agent.sh`（**凍結**） | print | **同一張 pty、只差 `-p`** |
| `INT` | 真 pty | `--stdin inherit`、無 `--json` | `wrap_agent_tty.sh` | **interactive** | 互動模式的主處理 |
| `INT2` | 真 pty | 同上 | `wrap_agent_tty.sh` | interactive | **多一輪人類輸入** |
| `INTQ` | 真 pty | 同上 | `wrap_agent_tty.sh` | interactive | **人提早關掉終端機** |

- 題目：`ops/gain/r534/templates` 的 `lcb_3522`／`lcb_3584`／`lcb_3649`／
  `lcb_3715`／`lcb_3789`（含人類點名的 `lcb_3649`）。
- `PRT`／`PTP`／`INT` 各 2 rep；`INT2`／`INTQ` 各 1 rep。共 **40 格**。
- 其餘對齊 abpi：prompt 逐字相同、工作區純度 fail-closed 擋門、
  agent 逾時 900s、外包 1200s、`--test-timeout 120`、`--retry none`、
  `--sandbox none`、模型 `gemma-4-12b-it-qat`、3 條 lane（1003 的 4 串留 1 串）。
- **與 abpi 的刻意差異（判讀時要記住）**：本批**三臂都設 `VACANT_HOOK_LOG`**
  （互動臂需要 `agent_end` 當確定性的「做完了」訊號）⇒ 每格多一通 canary
  ⇒ **`requests_seen` 不可與 600 格直接並排**，要看 `wire_model_calls`。

### 負控制（不過就整欄不可引用）

- **量具自檢**：`tty_drive.py --self-check` 正控制（pty ⇒ `isatty` True/True）
  ＋負控制（無 pty ⇒ False/False），本機與 vacant-dev 都 `usable=true`。
- **模式量具**：§一那張 A/B/C/D 四格，B/C/D 三格都要吐那句錯誤。
- **隱藏尺**：五題的 `test_hidden.py` 都要擋得住退化樁
  （`def <entry>(*a,**k): return None`）——**5/5 全擋，0/26–28**。
- **比對器**：注入一行字要抓得到——抓到了。

### 結果（40/40 收完，2026-09-20 14:10–15:43 UTC）

**A. 模式（這一批自己帶的負控制）**

| 臂 | `mode_evidence.tui` 有 TUI 字樣 | 判讀 |
|---|---|---|
| `INT`／`INT2`／`INTQ` | **20/20** | interactive |
| `PTP`（同一張 pty，只多一個 `-p`） | **0/10** | print |
| `PRT`（沒有 pty） | 沒有轉錄 ⇒ 落 `null` | print（由 §一 B 格支撐） |

⇒ **同一張 pty、同一組 launcher 旗標，只把 `-p` 拿掉，TUI 就出現／消失。**
指紋是 `(vacantproxy)` 狀態列、`Working` spinner、`ctrl+c/ctrl+d` 提示列。
⚠ `To resume this session:` 在 `INTQ`（8 秒就離開）**5 格裡有 4 格沒印**
——session 還沒存就走了。所以模式判讀以 TUI 字樣為準，那一行只是加分。

**B. 中介（§二的實測）**

| 臂 | n | `requests_seen == 0` 的格數 | canary 打到中繼 | 模型呼叫 min/中位/max |
|---|---:|---:|---:|---|
| `PRT` | 10 | **0** | 10/10 | 4 / 7 / 11 |
| `PTP` | 10 | **0** | 10/10 | 3 / 7 / 12 |
| `INT` | 10 | **0** | 10/10 | 4 / 7 / 9 |
| `INT2` | 5 | **0** | 5/5 | 7 / 8 / 9 |
| `INTQ` | 5 | **0** | 5/5 | 1 / 1 / 4 |

**40 格沒有一格是 `requests_seen == 0`。** 連只活 8 秒的 `INTQ` 都至少有
一通模型呼叫走過中繼。wire index 逐條都是 `POST /v1/chat/completions -> 200`，
upstream 是 b1003。

**C. 閘門**

| 臂 | n | `accepted=true` | `accepted=false`（拒交） | 無判決 |
|---|---:|---:|---:|---:|
| `PRT` | 10 | 6 | 4 | 0 |
| `PTP` | 10 | 5 | 5 | 0 |
| `INT` | 10 | 6 | 4 | 0 |
| `INT2` | 5 | 3 | 2 | 0 |
| `INTQ` | 5 | **0** | **5** | 0 |

- **`INTQ` 5/5 全拒交**：人在第 8 秒按 Ctrl-D、agent 還沒寫出 `solution.py`，
  閘門在行程結束那一刻跑驗收、`visible_fail`、拒交。
  **這就是「互動模式下閘門會動」的直接證據**，不是靠 `INT` 全過推論出來的。
- 三個單輪臂的 accepted 數（6／5／6）**不可以相減當效果量**（n=2/題）。
  能講的只有：**互動與 `-p` 在這 5 題上都出現了過與不過，沒有哪一邊全垮。**

**D. 模型看到的東西（§四）**

| 比對 | 題數 | 第一通 `POST /v1/chat/completions` 逐位元相同 |
|---|---:|---:|
| `PTP` ∶ `INT`（rep 1） | 5 | **5/5** |
| `PTP` ∶ `INT`（rep 2） | 5 | **5/5** |
| `PRT` ∶ `INT`（rep 1） | 5 | **5/5** |

相同的欄位：system 訊息、全部 messages、`tools` ＝
`['bash','edit','read','write']`、`max_completion_tokens=16384`、`stream=true`、
`store`／`stream_options`、`model`。raw body 都是 5983 bytes。

**E. 一個活體標本：交出去、閘門放行、隱藏測資跑不完**

`lcb_3649_PTP_r1`：`accepted=true`、可見驗收 **2/2 過**，
而 `postaudit_hidden_status=**timeout**`（60 秒不終止；同一份隱藏檔對退化樁
是秒回 ⇒ **是交出來的解本身不終止**）。
⇒ 人類 2026-09-20 提到的 `lcb_3649` 現象**在本批重現了一格**。

🔴 **這一格要講對**：它是**可見驗收覆蓋不足**，不是模式差異。
`-p` 與互動在這一點上沒有分別——本批的互動臂也沒有人去跑大輸入。
「互動模式下人會看到它卡住」這句話**本批沒有量到**（`INT2` 的第二句是寫死的，
不是人看畫面之後的反應）。

---

## 六、600 格要不要加但書、或作廢

**不作廢。** 要加的但書有兩條，而且**第二條才是人類真正指到的那件事**：

1. **（小）`-p` 這個字本身沒有製造不真實。** 它與「把 pi 放進真的輸入框」
   在第一通請求上逐位元相同，中介與閘門都照常。而且**只要 harness 沒有自己
   配一張 pty，pi 本來就會落進 print**——不寫 `-p` 也一樣（§一的 B 格）。
2. **（大）那 600 格量的是「單輪委派」，不是「人在旁邊來回」。**
   `-p` 與本批的 `INT` 臂**都是單輪**。真實使用裡人會看著畫面、
   會在 agent 卡住時打斷、會追問——那條路本 repo 到現在**完全沒有量過**，
   `INT2` 只是它的一個最小標本。

⇒ 建議在 abpi 的裁決檔 §六「沒量到的」補一條：
**「只量單輪委派。互動式多回合沒有量。」**

---

## 七、沒量到的（先寫，免得回來補成好看的）

- **`--mode rpc` 完全沒有量。** 它是第四種呼叫形態，而且是官方給人做
  程式化多回合驅動的那一條。讀碼上它與另外兩條共用同一個 runtime，
  所以中介**應該**成立——但那是推論不是量測，不可以寫成事實。
- **只有 pi 0.85.1、只有 b1003、只有 5 題。** 不跨 agent、不跨後端。
  `vacant-gate-numbers-are-framework-bound` 已經立過逐格判決不跨框架。
- **沒有 enclosure**（`--sandbox none`）⇒ `tier` 預期是 B′ 不是 A。
  本批量的是**閘門與中介**，不是附身級別。
- **孤兒回收在互動臂沒有量**（`--stdin inherit` ⇒ `start_new_session=False`
  ⇒ `orphans_killed` 落 `None`）。**`None` 不是 `False`。**
- **模擬的人不是人。** `tty_drive.py` 只會「離開」與「打一句預先寫死的話」，
  不會看畫面、不會判斷、不會在對的時機打斷。
- **這張 pty 關掉了 `ISIG`**（否則量具自己會殺掉驗收，見 §八），
  所以它與真人的終端機在「Ctrl-C 會不會變成 SIGINT」這一點上不同。
- **`lcb_3649` 的不終止解**：本批沒有設計成去修它，也沒有量「人看到卡住之後
  會不會救回來」。`INT2` 的第二句話是**寫死的**，不是人看畫面之後的反應。
- **`INT2` 只有 5 格、而且第二句是同一句**。它證明的是「多回合在機制上跑得動」
  （兩筆 `agent_end`、模型呼叫從 7 升到 8–9、閘門照跑），**不是**
  「多回合會讓結果變好」——5 格裡 3 過 2 不過，與單輪同題的結果一致。
- **兩個臂之間的 accepted 差（6／5／6）不是效果量**，每題只有 2 rep。
- **沒有量 `-p` 與互動在 *第二通以後* 的差**。第二通的內容取決於模型上一通
  回了什麼，而模型是隨機的 ⇒ 之後的差不可歸因於呼叫形態。
- **n 很小、無檢定、非預註冊。**

---

## 八、**兩個**量具說謊的標本（作廢 8 格 ＋ 再作廢 8 格）

兩次的症狀**一模一樣**：某一格的 `run_RUN-ON.json` **根本不存在**。
如果只看那一欄，兩次都會被讀成「互動／pty 底下中介不成立」。
兩次的真因都是**量具自己把受測物殺掉**。

### 8-1 pty 的 `Ctrl-C` 在 pi 退出之後會變成 `SIGINT`（修在 `9ced8997`）

`tty_drive.py` 的離開階梯在 Ctrl-D 之後會補送 `Ctrl-C ×2`。在**互動的 pi**
底下那是無害的（pi 把終端機設成 raw，`0x03` 只是一個位元組，由
`handleCtrlC()` 讀走）；但 **pi 退出之後**它會把終端機還原成
canonical ＋ `ISIG`，那時候的 `0x03` 由 line discipline 變成送給
**前景行程群組**的 `SIGINT` ⇒ 連**還在跑驗收的 launcher** 一起殺掉。
標本：`lcb_3584_PTP_r1`，`ended_by=ctrl_c_twice`、無 run json。

🔴 **這一型不是本專案特有的。** 任何「用 pty 驅動一個會切 raw mode 的
TUI，然後在它退出後還往同一張 pty 寫控制字元」的 harness 都會中：
`0x03`／`0x1c`（Ctrl-\ ⇒ SIGQUIT）／`0x1a`（Ctrl-Z ⇒ SIGTSTP）
在 canonical 模式下**都是訊號**，而且送給**整個前景行程群組**，不是送給
那個已經不在的 TUI。**值得進專案的量具說謊清單**
（`instruments-lie-before-you-conclude-zero`）。
修法：pty 一開就 `tcsetattr` 關掉 `ISIG`，並在 agent 收攤
（hook log 的 `session_end`）之後凍結階梯。

### 8-2 「輸出靜默」在 print 模式是**常態**，不是「做完了」（修在本次提交）

第二輪 10 個 `PTP` 格裡 **8 格**是 `done_signal=idle`、`ended_by=sigterm`、
牆鐘全部卡在 244.5–245.0 秒。真因：**`pi -p` 在跑的時候 stdout 一個字都不吐**
（print 模式把整段回答留到最後才寫），所以「120 秒沒有輸出」對它是**正常**，
而 `tty_drive` 把它讀成「做完了」，接著階梯把**還在想的 pi** 一起砍了。

修：
1. **有 `--done-when-hooklog` 就不准用 idle**——idle 只是沒有 hook log 時的
   退路，不是第二個判準（兩者是「擇一」不是「OR」）。
2. 新增 `--no-quit`：`PTP` 那一臂**一個位元組都不送**（`pi -p` 自己會結束）。
3. 階梯砍到只剩 Ctrl-D 一級——實測 20 個互動格 **20/20 都是 Ctrl-D 結束**，
   後面那兩級一次都沒幫上忙，卻砍掉 8 格。逾時交給 `--cap`（唯一硬停）。

作廢的 10 格原樣留在
`ops/vacantrun/pi_tty_20260920/evidence/void_PTP_instrument_lied/`
（`done_signal`／`ended_by`／`wall_s` 都在裡面），**不刪，當標本**。

---

## 八-B、對展場的意義（2026-09-21 補：展場機器就是 1003）

人類已確認：**展場搬去的實體機器就是 1003（Windows），vacant-dev 是跑在
它上面的 VMware 虛擬機**（`systemd-detect-virt` ⇒ `vmware`；VM 打
`192.168.76.1:1234` 與打 Tailscale `100.119.113.56:1234` 逐 byte 相同，
負控制 1004 不同）。三個後果：

1. **enclosure／bwrap 在展場是在的**——它們跑在那台 Linux VM 裡，不是
   跑在 Windows 上。本批 `--sandbox none` 是本批的選擇，不是展場的限制。
2. **展場如果要展「有人坐在終端機前面」那一幕，本批證明那一幕是可跑的**：
   pi 的 TUI 在 Vacant 底下每一通模型呼叫都走中介，離開時閘門照跑。
3. ⚠ **但展場不該真的等模型。** 本批互動格的 agent 牆鐘中位數約 300 秒
   （最長 727 秒）。`CLAUDE.md` 的秒級互動硬需求不因為「互動模式可行」
   而放寬——展件仍然跑 `entrycost` 機制模擬或預跑重放。

---

## 九、怎麼重跑

```sh
# 量具自檢（本機就能跑，零機時）
python3 ops/vacantrun/tty_drive.py --self-check

# 模式四格（需要 pi；零模型呼叫）
python3 ops/vacantrun/tty_drive.py --transcript /tmp/A.pty --idle 8 --cap 120 \
    --min-run 0 -- bash ops/vacantrun/pi_tty_20260920/mode_oracle.sh plain
bash ops/vacantrun/pi_tty_20260920/mode_oracle.sh plain < /dev/null   # ⇒ exit 1

# 隱藏尺負控制（零模型呼叫）
python3 ops/vacantrun/pi_tty_20260920/pi_tty_collect.py \
    --negative-control lcb_3522,lcb_3584,lcb_3649,lcb_3715,lcb_3789

# 整批（要機時）
TTY_ARMS="PRT PTP INT" TTY_REPS=2 TTY_LANES=3 \
    bash ops/vacantrun/pi_tty_20260920/pi_tty_matrix.sh
TTY_ARMS="INT2 INTQ" TTY_REPS=1 TTY_LANES=3 \
    bash ops/vacantrun/pi_tty_20260920/pi_tty_matrix.sh

# 收表與逐位元比對
python3 ops/vacantrun/pi_tty_20260920/pi_tty_collect.py --hidden-timeout 60
python3 ops/vacantrun/pi_tty_20260920/pi_tty_wirediff.py --left PTP --right INT
```

證據包：`ops/vacantrun/pi_tty_20260920/evidence/`
（`bundle_evidence.sh` 收的；**不含** `req.bin`／`resp.bin`，那裡面有 prompt 全文）。
