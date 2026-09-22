---
description: 第一優先目標——Vacant 要能附身在任何 agent 上；查現況、報缺口、說下一步
---

# /goal — 附身任何 agent（2026-09-19 人類定為第一優先）

人類原話：

> **原則三最重要，無論 Vacant 的架構長怎樣，這邊都要改好，因為他就是附身進去的。**

這條**凌駕**其他工作。實驗（R535 等）不停，但**資源衝突時這條先**。

---

## 〇、⚠ 2026-09-19 人類更正了「附身」的定義——先讀這一段

> **不對不對我發現你產生巨大偏差，我們要的不是用指令去喚醒 AGENT 而是
> 安裝之後我 PI 打開就默認有 VACANT，而不是要用指令一筆筆的去加入。**

⇒ **先前的定義（錯的）**：使用者每次打
```
vacant run --suite <目錄> -- pi -p "做這件事"
```
⇒ **正確的定義**：
```
vacant install          裝一次
pi -p "做這件事"         之後照舊，Vacant 已經在裡面
```

**為什麼這個差別是要害**：包裝器最大的繞過洞不是 unix socket，是
**使用者忘記打那一串**——忘了就完全沒有 Vacant，**而且零痕跡**。

⚠ **底下 §一 到 §五 的「兩格都成立」判準仍然有效，但它量的是「閘門會不會動」，
不是「預設在不在」。** 五個 agent 的 L-real 全部是在**打了完整包裝指令之後**量到的
⇒ **那些證據不能拿來宣稱「裝好就有」。**

### 兩層的難度不一樣，不要混講

| 層 | 怎麼做 | 能不能真的「預設」 |
|---|---|---|
| **通道**（模型呼叫經過 Vacant） | 寫進 agent **自己的設定檔** | ✅ **可以真的預設**——連打完整路徑也跑不掉 |
| **閘門**（結束時驗收＋簽收據） | 需要有人接手行程結束 ⇒ **PATH shim** | ⚠ 預設**但打完整路徑就繞過** |

**誠實的宣稱**：通道做得到真正的預設；閘門做得到「預設但可繞」。
**不准把後者寫成「不會被繞過」**——2026-09-19 的 `block_egress` 量測逐條證實
（unix socket、另一個 uid 的中繼、DNS 全部實測通）。

### 🔴 2026-09-20 人類否決了這一段原本的結語，而他是對的

原本寫的是「**做得到而且同樣有力的宣稱是：繞得過，但繞過一定留下痕跡**」。

> 我不太能接受是「抓漏但不保證每一次都經過咎責」，vacant 的意義就是在
> **每個處理都可以經過究責**所以才可以讓人信任啊。
> 我們應該使用任何方法無論是在底層或是 plugin or anything 都可以嘗試。

**那句話不只是不夠，它目前為假**：繞過壓測 C 類 5/5 繞過而**收據一個字都沒變**
（739,851 bytes 流到 openrouter，`wire_*/index.jsonl` 零紀錄，五格 `accepted=true` exit 0）。
unix socket 那格在封鎖之下 0.034 秒 200 OK 而封包計數器 **0**——「留下痕跡」在那條路上沒有發生。

**裁決見 `decisions/DECISION_20260920_COMPLETE_MEDIATION.md`。三句話的版本：**

1. **complete mediation 不是做不到，是做錯層了。** 封鎖規則是列舉式的，封一條多一條。
   正確的招式是**減法**——netns ＋ mount ns 之下**別的路不存在**，不是「被擋住」。
   ⚠ `unshare -n` 單獨不夠（只殺抽象 socket），路徑型 socket 要 mount ns。
   而 `vacant_network/vrun/sandbox.py` 為了**隱藏測資**已經寫過這一招，只是沒用在網路上。
2. **那 21 格是在把每個 agent 自己的防護全關掉之下量的**
   （`wrap_agent.sh:88-89/148/184`），而 Codex 預設的 `workspace-write` 本來就不給 shell 指令網路
   ⇒ **我們自己把別人的圍牆拆了再去量破洞。**
3. **有 hook 的不是三個是六個**，Codex 的最完整（`PreToolUseDecisionWire = allow|deny|ask`），
   而 `possess.py` **一個都沒寫**。

**新口徑**（取代上面那句）：

> **Vacant 不宣稱 agent 不會想繞過。它做的是把別的路拿掉。**
> 「這一次有沒有經過 Vacant」不是抓漏率，是**結構事實**。
> 有效範圍寫在每一張收據上；任一不成立，收據**不會變弱一點**——它寫「未認證」，退出碼不是 0。

### ✅ 2026-09-20 深夜：量完了 —— 口徑可以講了，但**範圍窄到必須逐字照抄**

五份裁決 `decisions/DECISION_20260920_*.md`；證據 `ops/vacantrun/{enclosure,codex_managed}_20260920/`。

| 層 | 量到什麼 |
|---|---|
| **enclosure**（netns＋mountns） | 負控制 **7/7 通** ↔ enclosure **6 擋 1 通**（兩邊 `mismatched=0`）；**五個 agent 全進得去、零硬失敗**；門已是**會終結 HTTP 的 proxyd**（非模型 path 回 403 且**上游收到 0 次**；負控制 `policy=any` 與舊 byte pipe 各收到 **1 次**） |
| **Codex 自己的** | **`codex exec` 零旗標必載 `/etc/codex/requirements.toml`、fail-closed ⇒ 那是「保證」不是「預設值」**。**十條反抗路徑全擋**（含 `--dangerously-bypass-approvals-and-sandbox`、專案層 config、自建同名 profile ⇒ 拒絕啟動）。只有 Vacant 的端點通得了，**連 Vacant 都不能裸連** |
| **收據** | 簽章鏈上帶 `enclosure{ns_id,policy_sha256,applied}`／`framework_hook{canary_fired}`／`reconciled{unexplained}`／`tier`。四組實跑三個負控制：noenc→**C**、enc→**A**、nohook→**B**、rogue→**B**。**C 級拒發收據**（正面驗過 ⇒「拒發」與「沒跑過」分得開） |

**可以講的那一句，逐字**：

> **「A 級的那一跑，每一通模型呼叫都經過 Vacant，而且都對得上一個工具事件。」**

🔴 **不可以講**（每一條都是量出來的，不是保守）：
1. **「不會被繞過」** —— 圍牆**外面**什麼都連得到。
2. **「這個 agent 是 A 級」** —— 級別是**這一跑**的屬性，不是 agent 的。
3. **「掛鉤裝了所以在」** —— 只證明**這一次**燒了。而且 agent **拆得掉**自己的 hook（實測）。
4. **「`unexplained=0` ⇒ 沒人多叫模型」** —— 對帳只管通數與次序，**抓不到「在合法回合視窗裡多塞一通」**。
5. **「閘門擋下 X 格」** —— 那個數字**綁在那一個框架＋那一個後端上**（三家判決方向一致**只有 4/10 題**）。
6. ~~最要緊的一條：今天沒有任何真 agent 跑出過 A 級。~~
   ✅ **2026-09-20 深夜拿到了**：agent ＝ **pi 0.85.1**，**canary 由 pi 自己的 extension 燒**
   （證明不是 grep，是掛鉤日誌本身——10 筆事件橫跨 **8 個不同 pid**，而 inner 腳本只 `exec` 過一次；
   日誌裡有 `pre_tool_use tool=write`／`tool_result`／兩筆 `before_provider_request`
   ⇒ **腳本不可能知道 agent 什麼時候要叫工具，只有 pi 知道**）。
   `applied=True`／`ns_id` ≠ 主機／`canary_fired=True`／`unexplained=0`／`tier="A"`，
   **三個負控制都用真 agent**（noenc→C、nohook→B、rogue→B），22 格判準全綠。
   落盤 `decisions/DECISION_20260920_FIRST_TIER_A_RECEIPT.md` ＋
   `ops/vacantrun/enclosure_20260920/evidence_agent_attest/`。

   🔴 **但那句話要換成三條更小的但書，而且一樣必須一起講**：
   - **那是「那一跑」的級別，不是 pi 的、更不是 Vacant 的。** `canary_fired=true` 只證明**這一次**燒了。
   - **A 級的「語意」那一半建立在 hook 上 ⇒ 不是保證。** 同一輪的 `nohook` 格就是反例：
     **刪一個檔整層消失**。**保證那一半仍然只能靠 kernel（enclosure）。**
   - ⚠ **`unexplained=0` 依賴「一個 `tool_result` 對一通模型呼叫」。**
     pi **平行工具模式**下，一個 assistant 訊息叫兩個工具 ⇒ 兩個 `tool_result` 只有一通後續呼叫
     ⇒ **多出來的額度會吸收掉一通 rogue**。本輪 8 格沒踩到——**那是「沒踩到」不是「不會發生」**。

   🔴 **另一件同一輪量到、會改寫既有規格的**：`vacant_network/vrun/retry.py` 的
   「proxy **不擁有工具執行器**」**在 pi 上不成立**。pi 的 `tool_call` **改得動工具輸入**
   （判準＝落盤的那個檔）：只綁 `write` ⇒ 兩個檔都出現（**agent 發現檔案不在就改用 `bash`**，
   11–12 次工具呼叫裡 8–9 次是 bash）；不限工具 ⇒ **agent 要的那個檔根本沒出現**。
   ⇒ 「只攔一個工具」**不是攔不住也不是攔得住**，而**繞過去的每一步都在掛鉤日誌裡**
   ——「繞得過，但會留下數字」的第二個活體標本。
   ⚠ 但 **pi 文件逐字「No re-validation is performed after your mutation」⇒「改得動」≠「改得對」**，
   而且**那是 pi 的性質**：Claude Code 的 33 個事件、Codex 的 12 個，在模型請求層**一個都沒有**。

⚠ 另外三條範圍限制：擋的是 **agent 的 shell**，**Codex 自己的模型呼叫不走這條**；
上游只看得到 `CONNECT host:port`，**不是內容**；只量過 one-shot 一題
（互動 TTY／MCP／`npx`／長任務／並行多格**都沒量**）。

**跨框架成立、而且最適合對觀眾講的那一句**：

> **agent 自己宣告完成、退出碼 0 走人，閘門仍在行程結束那一刻擋下來。**

（11 個拒交格裡 **9 格**如此——只有 2 格是被逾時砍的——**三個框架同時出現**。）

---

### ✅ 2026-09-20：「裝一次就有」做出來了（macOS，3/5 通道）

`python -m vacant_network.vrun.possess {install,uninstall,status,detect}`
（cli 還沒接；裁決 `decisions/DECISION_20260919_DEFAULT_ON_INSTALL.md`）

**通道層——命令列上零個 `vacant`，用完整路徑打真 binary：**

| agent | proxy journal | 結果 |
|---|---|---|
| codex 0.153.2 | **5 通** `POST /v1/responses` | 寫出正確 `solution.py` |
| opencode 1.18.31 | **2 通** | 回 `OK` |
| Claude Code 2.1.278 | **2 通** `POST /v1/messages?beta=true → 200` | 回 `OK` |
| pi ／ hermes | — | ⚠ **那台沒有可執行檔 ⇒ L-none，不是失敗** |

**閘門層**（PATH 放 shim，命令列仍然零個 `vacant`）＋**兩個新退出碼**：

| 碼 | 意思 |
|---|---|
| `0` | 驗收跑了而且過了 |
| `20` | 跑了沒過 ⇒ 拒交 |
| **`21`** | **沒有驗收可跑：只中介沒閘門**（`ungated`／`accepted=null`／`suite_source="none"`） |
| `22` | infra_void |
| **`23`** | **`requests_seen == 0`：沒量到中介 ⇒ 裁決不可歸因**（蓋過 0／20／21） |

⇒ **`23` 是「假拒交格」的直接解法**——那個「除了 `requests_seen` 每個欄位都跟合法拒交格一樣」的問題。

**設計決定**：常駐（launchd／`systemd --user`／`bare`）＋ **fail-closed**。
決定性的理由：**技術上沒有誠實的 fail-open**——要回退直連，這工具就得在失敗當下
**安靜地把自己解除安裝**。緩解是 **preflight**（先起 proxy、真打一通 round-trip，
**過了才寫第一個設定檔**；實測擋下兩次，兩次都一個檔沒動）。

**可逆**：備份後立刻驗 sha256 → `status` 逐檔列 `before→after→現在` →
`uninstall` 逐位元還原**並自驗**。完整循環實測：改 6 檔 → 還原後六個檔 `diff` 零輸出、零殘留。
⚠ **憑證紅線 `NEVER_TOUCH`**：`auth.json` 那幾支一次都沒讀過。

### 🔴 還不能說的（這幾條是展件與 v1 的擋門）

1. **不能說 Linux 成立**——`systemd --user` ＋ linger **程式碼寫了、一次都沒跑過**。
   ⚠ **展場機器是 Linux VM** ⇒ 展件可用之前必須補。
2. **不能說五個都接通**——通道 **3/5 L-real、2/5 L-none**。
   pi 還多一個沒量的：`~/.pi/agent/` 底下 **`models.json` vs `models-store.json` 哪一份才是真相來源**。
3. **不能說閘門在五個上都有牙齒**——本輪只量 codex（4 格）。
4. **不能說重開機之後還在**——`RunAtLoad` 寫了、`launchctl print` 看得到，**沒有真的重開機驗**。
5. **`status` 的 `wired` 與 `proven` 是兩欄，永遠不把前者說成後者**——
   journal 只能說「通道層活著且有流量」，**不能說「這個 agent 被中介了」**。

### ⚠ macOS 上一個一定會踩的坑

**TCC 讓 launchd job 卡死而不是報錯。** `.venv` 在 `~/Documents/…` ⇒ job `state=running`、
pid 有值、**埠沒人在聽、log 兩個都是 0 byte**；堆疊卡在
`Py_InitializeFromConfig → getpath_readlines → open$NOCANCEL`——
**python 直譯器在啟動階段的 `open()` 就不回來**（launchd agent 沒有 `~/Documents` 的 TCC 授權
而且不能跳對話框）。**這不是偶爾失敗，是開發者 checkout 底下一定失敗**
（正常 `pip install` 碰不到）。`possess.py` 的 `tcc_risky()` 會在動任何東西之前擋下。

---

## 〇-2、🔴 2026-09-22 人類的要求（凌駕本檔其他段落的「下一步」）

人類原話：

> **維持現有的 vacant 的效果，讓他可以在任何的現有 agent 上運作，去執行做好為止，
> 且自行安裝確認。** 優先以 pi；OpenCode 做不到 `/vacant on` 的話先不管。

三句話的版本：

1. **既有效果一個都不准掉**：通道（proxyd）、閘門（PATH shim、退出碼 `0/20/21/22/23/24/25/26`
   語意不動）、收據（`ws_verdict`、四欄認證）、`vacant on`（B 路）、四個 agent 的接線。
2. **pi 的形狀**：`pip install vacant-network` → `vacant`（裸打會引導）或 `vacant install --agent pi`
   → 照舊打 `pi`，狀態列顯示 `(vacant) <model>`，輸入框 `/vacant on|off|status`。
   接法＝**一支 extension**（`vacant_network/vrun/piext.py` 渲染、`possess.wire_pi` 寫進
   `~/.pi/agent/extensions/vacant.ts`），**不再改寫使用者的 `models.json`**。
   研究與施工順序：`decisions/notes/NOTE_20260922_PI_OPENCODE_SLASH_VACANT_PLAN.md`。
3. **做到好的定義**＝自己裝一次、自己驗：`requests_seen > 0`（proxyd journal）、掛鉤日誌有
   canary、`/vacant status` 回得出來、shim 那條 `pi -p` 退出碼照舊。
   ⚠ 沒有真模型的機器只到 **L-fake**（假上游），要明講；L-real 仍要在 vacant-dev 補。
   ✅ 2026-09-22 落地：pi extension（`piext.py`，自裝 **L-fake**，`ops/vacantrun/possess_pi_20260922/`）；
   Claude Code 由 Claude Code 自己在遠端容器裡驗（**L-real**，Haiku 4.5，`ops/vacantrun/possess_claude_20260922/`）
   ——抓到 `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST=1` 會讓 `settings.json` 的 base URL 被忽略，環境變數那條不受影響。

## 一、閘門的可量測定義（仍然有效）

「閘門會動」是**兩格都成立**，而且**用真模型**：

| 格 | 判準 | 為什麼兩格都要 |
|---|---|---|
| **拒交格** | 驗收沒過 ⇒ `accepted=false`、`stop_reason=visible_fail`、**exit 20** | 驗閘門**有牙齒** |
| **交付格** | 驗收過 ⇒ `accepted=true`、`visible_pass`、**exit 0** | 驗閘門**不是永遠說不**（永遠拒交的閘門跟沒有一樣） |

外加三個**不可省**的旁證：

1. **`requests_seen > 0`** —— 唯一能證明中介真的發生了的欄位。
   「我設了環境變數」不是證據（`docs/VACANT_RUN.md` §4.5）。
2. **收據鏈驗得過** —— `verify_run_receipts --selftest` 先 PASS（負控制），再驗該跑。
3. **證據等級要標明** —— 見下。

### 證據等級（**不可混講**）

| 級 | 意思 | 現在有誰（2026-09-19 更新） |
|---|---|---|
| **L-real** | **真模型**真跑，兩格都過 | **pi ／ OpenCode ／ Claude Code ／ Codex (API key) ／ Hermes** |
| **L-fake** | 假上游（`mockup.py`）驗通道與閘門 | —— |
| **L-none** | 沒量 | Codex (ChatGPT 登入) ／ Codex (chat wire) |

**矩陣裡不再有「完全沒量過」的 agent。**
⚠ Hermes **沒有經過 L-fake**（從來沒被假上游量過）⇒ §1–§6 的假上游結論不涵蓋它。

⚠ **「零接線」三個字有陷阱，各家的成立條件不同**：
- **Claude Code**：真模型**零接線成立**，但那**整個建在「LM Studio 有開 `/v1/messages`」
  這一個功能上**。換純 llama.cpp server／vLLM 預設就斷，而那時要補的協定轉換層
  **不在本 repo 裡也沒被量過**。
- **OpenCode**：零接線**只對雲端模型成立**。內建 provider 只吃 models.dev 註冊表裡的
  模型 id，餵本地模型會在**送出任何請求之前**死在模型解析 ⇒ `requests_seen = 0`。
  接本地模型**必經設定路線**。
- **pi**：一直都是設定路線（`PI_CODING_AGENT_DIR` ＋ `models.json`）。
- **Codex (API key)**：設定路線（`CODEX_HOME` ＋ `config.toml` 裡一個**新** provider id，
  內建 `openai` 不准覆寫）。**不吃 `OPENAI_BASE_URL`**。
- **Hermes** 0.19.0（`hermes-agent`，⚠ 不是 `hermes`）：**「一個旗標」，介於零接線與設定路線之間**。
  全新環境只給 `CUSTOM_BASE_URL` 會死在 `No inference provider configured`，
  最小接線＝加一個 `--provider custom`（比寫設定檔輕）。
  **但對已經設好自訂 provider 的使用者是零接線**——`CUSTOM_BASE_URL` 優先序**高過**
  他自己的 `base_url`，不必動 `~/.hermes/config.yaml`。兩句話都要講。

⚠ **L-fake 不能寫成「這個 agent 可以用 Vacant」。** 假上游碰不到 SSE 分塊、
工具呼叫格式、逾時、上下文長度。這條界線在 `docs/AGENT_COMPAT.md` 開頭就寫著，
不准在對外文案裡模糊掉。

---

## 二、優先序（人類指定）

```
OpenCode ＝ pi ＞ Claude Code ＞ Codex(API key) ＞ Hermes
```

- **OpenCode 與 pi 是「絕對一定要」**（人類 2026-09-19 原話）。
- **Codex 的 ChatGPT 登入路徑先放著**——人類說「到時候我跟你一起弄」。
  那不是設定問題：模型通道寫死 `wss://chatgpt.com/backend-api/codex/responses`，
  **HTTP 反向代理在那條路上不存在**。要另想辦法（攔 WebSocket 或換登入方式）。

---

## 三、被這個目標擋下來的已知問題

1. **vacant-dev 上只裝了 pi。** `opencode`、`claude` 都沒有 ⇒ 現有矩陣是在別處跑的，
   而且**沒有一格是真模型**（pi 除外，靠 R535）。
2. **`vacant run --help` 曾經印舊介面**（已修，PR `fix/run-help`）——
   外人照 help 讀找不到收件口，等於沒發。這類「功能在但構不到」要當成附身失敗。
3. **`envmap` 是單一真相**（`vacant_network/vrun/envmap.py`）。新增 agent 一律改那裡，
   不要在別處再開一張表。
4. **零接線 vs 要接線**：Claude Code／OpenCode 吃環境變數（launcher 內建 ⇒ 零接線）；
   Codex／pi 吃設定檔（要寫 `config.toml`／`models.json`）。
   **後者是附身品質較差的一種**，文件要講明白使用者得多做什麼。

---

## 四、你被叫到時要做什麼

1. **先查現況**，不要憑記憶：
   ```bash
   sed -n '1,60p' docs/AGENT_COMPAT.md          # 矩陣（含誠實邊界）
   cat vacant_network/vrun/envmap.py                     # 名單的單一真相
   ssh user1@100.124.254.83 'export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:$PATH; for a in pi opencode claude codex; do printf "%-10s " "$a"; command -v $a >/dev/null && $a --version 2>&1|head -1 || echo "沒裝"; done'
   ```
2. **報缺口**：哪個 agent 在哪一級、缺什麼才能升級。
3. **說下一步**，並指出資源衝突（1003 的吞吐 4 串封頂；R535 在跑時插進去會互搶）。

⚠ **報告用繁體中文**；口徑用「**可究責性**」不用「信任」。

---

## 五、完成的定義

**優先序前兩名（OpenCode、pi）都到 L-real，而且拒交格與交付格都留下可重驗的收據。**

### ✅ 已達成（2026-09-19）

pi、OpenCode **與 Claude Code** 三個都到 L-real，各自拒交格 exit 20 ／ 交付格 exit 0、
`requests_seen > 0`、收據 `--selftest` 先過再驗該跑。

⚠ **達成之後浮出來的新東西，不要當成結案**：

1. **三個 agent 的拒交格都是 `agent_rc = 0`** ——它們都宣告完成、退出碼 0、講得很有把握，
   閘門在行程結束那一刻擋下來。**那不是巧合，是這個設計要處理的那件事。**
2. **收據的 `model` 欄位不是證據**：LM Studio 不檢查 `model`，拿
   `claude-3-5-haiku` 去問 1003 照樣回 gemma 的內容；Claude Code 對不認得的 id
   **放行不擋**（OpenCode 是硬失敗，方向相反）⇒ **沒有任何一個環節會在
   「上游其實不是你以為的模型」時報錯。**
3. **`route()` 按 path 猜家族**，未命名的家族~~會落到公開 API 的預設上游~~
   **2026-09-19 起指到一個會拒絕的本機 sink**（`DECISION_20260919_V1_GATES.md`）：
   `wireproxy` 在開任何連線之前回 502，要走公開 API 得明講
   （`--allow-public-upstream` 或 `VACANT_RUN_ALLOW_PUBLIC_UPSTREAM=1`）。
   ⚠ `route()` **按 path 猜家族這件事本身沒修**，而且這擋的是「沒人指定的路由」
   不是「出網」——agent 繞過 proxy 直連的**結構性補法仍然是 `block_egress.sh`（V3）**。

### ✅ Codex (API key) 也到 L-real（2026-09-19）

`codex-cli 0.147.0`，拒交格 exit 20（`requests_seen=4`、`visible=0/2`）／
交付格 exit 0（`requests_seen=5`、`visible=2/2`），收據 `--selftest` 先過再驗四跑全 OK。
**沒有碰 `~/.codex/auth.json`**：每跑 `mktemp -d` 一個新 `CODEX_HOME`，裡面沒有
auth.json ⇒ 走的一定是 API key 那條。ChatGPT 登入那條一個字都沒動。
⚠ 版本與假上游那輪的 0.153.2 不同，引用時要連機器一起講。

**四個 agent 到 L-real 之後浮出來的東西**：

4. **`agent_rc = 0` 出現在全部四個拒交格。** 四個框架都宣告完成、退出碼 0、講得很有把握，
   閘門在行程結束那一刻擋下來。**不是單一框架的怪癖，是這個設計要處理的那件事。**
5. **交付格的 `ws_end` 三家逐位元相同**（`d1ed637b…`），**拒交格反而分岔**
   （OpenCode／Claude Code＝`add`+`multiply`，Codex＝`sum_numbers`+`multiply_numbers`）。
   ⇒ 「陷阱是題目的性質」只在**敘述寫死介面時**表現成同一份檔案；**敘述含糊時錯法會分岔**。
6. **模型 id：2 放行 ∶ 1 擋。** Claude Code 與 Codex 對不認得的 id 放行（Codex 另印
   `warning: Model metadata ... not found. Defaulting to fallback metadata`），
   OpenCode 硬失敗（`requests_seen=0`）。**那是三次實測不是一條規則，第四家仍要自己量。**
   ⚠ 「fallback metadata 退到什麼」**沒量**——它會改變送出去的 input，也就是改變逐字落盤的內容。
7. **思考模式下的 runaway（1/3，n 很小）**：1003 預設開思考，而 Codex 的 body 帶
   `reasoning:{"summary":"auto"}` **沒有 `effort`** ⇒ 一通 713 秒、94,776 個
   `reasoning_text.delta`、`output_text.delta` 為 0、BrokenPipe、`response_sha256=null`
   （**infra_void 的洞，而 `wire_digest` 簽的就是含 null 的那個配對**）。
   `wrap_agent.sh` 多了**預設不設**的 `VACANT_CODEX_REASONING_EFFORT` 鉤子；
   ⚠ **那是觀測到的緩解不是保證**，而且它把推理整個關掉、代價沒量。
9. **⚠ 一個假拒交格與真拒交格在收據上只差一個欄位**（2026-09-19，Hermes 對照 C）。
   `CUSTOM_BASE_URL` 漏設時，Hermes **不報錯**，安靜走到解析鏈尾去打編死的
   `https://openrouter.ai/api/v1`：
   ```
   requests_seen = 0   wire_by_protocol = {}   agent_rc = 0   ← 0，不是 1
   stop_reason = visible_fail   退出碼 = 20   chain_ok = true
   ```
   **除了 `requests_seen` 以外，每一個欄位都跟一個合法的拒交格一樣**（連
   `agent_rc=0` 都一樣），而且**真的出網去了第三方**。
   ⇒ 這就是 `requests_seen > 0` 為什麼是**唯一**能證明中介發生的欄位，
   也是 `envmap` 誠實邊界 2「名單漏一個變數不會有任何錯誤訊息」的活體標本。

8. **`upstreams_defaulted` 的正確讀法**：它說的是「**這條路由沒人指定、萬一有流量會去公開
   API**」，**不是「已經出網了」**。要判有沒有真的出網看 `wire_by_protocol` 與
   `index.jsonl` 的 `upstream` 欄位。Claude Code 真的出過網（探 `/api/hello`）、
   **Codex 沒有**（`wire_by_protocol` 裡根本沒有 anthropic 這一項）。

### 下一個（優先序）

1. **`block_egress.sh`（V3）** —— ⚠ 口徑要更新：`upstreams_defaulted` 那個洞
   （沒人指定的路由落到公開 API）**2026-09-19 已經補了**（fail-closed 本機 sink）。
   `block_egress.sh` 現在守的是**另一個**洞：agent 繞過 proxy 直連，
   以及 `envmap` 名單漏一個變數。那兩個 sink 擋不住。
2. **`VACANT_CODEX_WIRE=chat`** —— Codex 走 chat/completions 那條**沒量過**，
   只有 chat/completions 的上游要靠它。
3. ~~Hermes~~ ✅ **2026-09-19 到 L-real**（拒交格 exit 20／交付格 exit 0，
   `requests_seen=6`，收據 `--selftest` 先過再驗）。
   ⚠ 只量到 `provider: custom`——**Nous Portal／OpenRouter／Anthropic OAuth／Copilot ACP
   那些要憑證的路一條都沒碰**。其中 **Copilot ACP 會 spawn 外部行程講 ACP**，
   跟 Codex 的 `wss://` 是同型的邊界嫌疑，**但沒量，不准寫成已知**。

**Codex 的 ChatGPT 登入那條：人類說「到時候我跟你一起弄」，不要自己動。**
那不是設定問題——模型通道寫死 `wss://chatgpt.com/backend-api/codex/responses`，
**HTTP 反向代理在那條路上不存在**。

⚠ 對外文案**仍然不准**寫「可以套用在各種 agent 上」——
只能寫「通道與閘門在 N 個 agent 上實測接通，其中 **4 個**有真模型證據」。
