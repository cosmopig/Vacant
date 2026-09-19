# DECISION 2026-09-20：每一次都經過 Vacant——從「封鎖」改成「把別的路拿掉」

**裁決者**：Fable（人類 2026-09-04 明令「判斷交給 Fable」；2026-09-19 重申「他可以等同我的回答」）
**觸發**：人類 2026-09-20 否決既有方向。

> 我不太能接受是「**抓漏但不保證每一次都經過咎責**」，vacant 的意義就是在**每個處理都可以經過究責**
> 所以才可以讓人信任啊。如果你沒辦法用任何的方法去嵌入每個 agent platform 那就要考慮是不是自己做，
> 但我認為這個方法是極其不對的，**我們應該使用任何方法無論是在底層或是 plugin or anything 都可以嘗試**，
> 讓每次的運作都可以經過 vacant 達到最後效果。

人類的論點：**抓漏率 90% 的可究責性等於沒有可究責性。** 這個系統存在的理由就是「每一次都留下可查的紀錄」。

---

## 〇、先更正兩件會改變結論的事實

### 0.1 那 21 格繞過壓測是在「把每個 agent 自己的防護全部關掉」之下量的

```
ops/vacantrun/wrap_agent.sh:88-89   Codex        approval_policy = "never"
                                                 sandbox_mode    = "danger-full-access"
ops/vacantrun/wrap_agent.sh:148     Claude Code  --dangerously-skip-permissions
ops/vacantrun/wrap_agent.sh:184     Hermes       --yolo
```

而 Codex 的**預設**沙箱 `workspace-write` **本來就不給 shell 指令網路**
（binary 裡 `SandboxPolicy` ＝ `read-only / workspace-write / danger-full-access / external-sandbox`，
另有 `network_access`）。

⇒ `DECISION_20260919_BYPASS_STRESS` 的 C 類 5/5 是「**Vacant 在最壞條件下的中介能力**」，
**不是「agent 框架沒有強制力」**。我們自己把別人的圍牆拆了，再去量圍牆有幾個破洞。

⚠ **`wrap_agent.sh` 那三行不改**：那是實驗 harness，無人值守需要它，改了既有 98 個歸檔 run 會失去可比性。
要改的是**產品側**（`possess.py`），見 §二 P0.5。

### 0.2 有 hook 的不是三個是六個

`/Applications/Otty.app/Contents/Resources/agent-integration/` 底下有
`claude / codex / cursor / kimi / opencode / pi` 六份整合、全部在跑
——**一個第三方 app 已經做到我們想做的事的「通知版」**。

| agent | 擴充點 | 證據 |
|---|---|---|
| **Codex** | `pre_tool_use / permission_request / post_tool_use / pre_compact / post_compact / session_start / session_end / user_prompt_submit / subagent_start / subagent_stop / interrupt / stop`；`PreToolUseDecisionWire = allow\|deny\|ask` | binary 字串；裝法 `~/.codex/hooks.json` ＋ `[features].hooks = true`（**預設關**） |
| **Claude Code** | 六個事件；`/etc/claude-code/managed-settings.json`（Linux）、`Application Support/ClaudeCode/managed-settings.json`（macOS），`policySettings` 在 binary 裡 45／261 次 ⇒ **root 持有、使用者蓋不掉** | ⚠ 但 `--bare` 一個旗標就 `skip hooks`，另有 `disableAllHooks` 設定鍵 |
| **OpenCode** | `tool.execute.before` · `command.execute.before` · `permission.ask` · `chat.message` | plugin API |
| **pi** | `~/.pi/agent/extensions/*.ts`，`export default function (pi: ExtensionAPI)` | extension API |

**Codex 另外兩個我們完全沒看到的東西**：
- `ManagedHooksRequirementsToml` / `managed_dir` / `<managed-requirements>/requirements.toml`
  ——**管理員層級、使用者蓋不掉的政策**
- `NetworkMitmToml` / `NetworkDomainPermissionsToml` / `NetworkUnixSocketPermissionsToml` /
  `NetworkHeaderInjectionToml`——**框架自己內建的網路中介與網域白名單，連 unix socket 都列管**

`vacant_network/vrun/possess.py` 目前**一個 hook 都沒寫**（`AgentSpec` :169-240 只碰 `env`／provider 區塊，
:705 的 wire 函式表同）。**這條路是零開採。**

---

## 一、「每一次都經過 Vacant」在技術上可不可能？

**可能，在 kernel 的 namespace 層，對「模型通道與外送位元組」這個範圍。**
但不是在目前投的那一層，也不能靠單一層。

### 1.1 「複製一份封鎖規則」這條路永遠到不了

`DECISION_20260919_BLOCK_EGRESS_V3` §4 那五條殘餘不是五個獨立的 bug，
是**同一個方法論的必然產物**：`block_egress.sh` 是**列舉式**的，封一條它就多一條。

unix socket 那格特別致命——**0.034 秒 200 OK、封包計數器 0**。
在那條路上「量到 0」是**錯的答案**。再加十條規則只是把殘餘從 5 變 4。

### 1.2 「減法」這條路到得了，而且本 repo 已經做過一次

`vacant_network/vrun/sandbox.py` 對**隱藏測資**用的就是正確招式，docstring 逐字寫著：

> 最小 rootfs 之下 repo 根本不在沙箱的檔案系統裡 ⇒ 那條洩漏通道**不可表達**，
> 而不是「存在但我們不准它讀」。

**同一招從來沒有被用在網路上。**

`bwrap --unshare-all` ＋ 最小 rootfs ＝ **network namespace ＋ mount namespace**，
V3 那五條殘餘一次全死：

| V3 殘餘 | 為什麼在 enclosure 裡不存在 |
|---|---|
| 同機他 uid 的 127.0.0.1 中繼 | netns 裡沒有那個 `lo`，那個 listener 不在這個網路堆疊上 |
| **unix domain socket** | 抽象 socket 由 netns 隔離；**路徑型 socket 靠 mount ns**——最小 rootfs 裡沒有 `/tmp`／`/run`／`/var/tmp`，那個 `.sock` 檔**不存在** |
| systemd-resolved 的 DNS | `127.0.0.53` 不在這個 netns 上，沒有 resolver |
| IPv6 | netns 裡沒有 v6 路由（不是「沒擋」，是沒有） |
| 已送出的位元組收不回 | ns 在 agent 啟動**之前**就建好，沒有「之前」 |

⚠ **精確度要求：`unshare -n` 單獨不夠。** 它只殺抽象 socket，**殺不掉路徑型 socket**，
必須是 netns ＋ mount ns。**這一條分辨錯，整個結論就垮。**

⇒ 在 enclosure 裡，「這一次有沒有經過 Vacant」**不是抓漏率，是結構事實**。
C 類的 `curl http://<IP>:1234`（IP 字面值、不留 DNS）只會有兩種結果：打到中繼並被記下，
或 `Network is unreachable`。**沒有第三種。**
用 `DECISION_20260918` §1.1 那把尺：**這是 L5，不是 L3。**

### 1.3 真正的不可能性（這三條是證明，不是「我們沒試出來」）

1. **無法中介一個能修改中介者的主體。** 這是 reference monitor 的定義本身，不是工程缺陷。
   有 root 的人可以 `nft flush`。
   ⇒ 宣稱必須**綁在主體邊界上**，並把邊界狀態（政策 sha256、netns 識別）寫進收據，
   讓「關掉」成為**看得見的狀態改變**而不是沉默的缺口。
   這正是 `checkpoint.py`「存檔點自身成鏈」的同一招，延伸到**執行政策本身也成鏈**。
2. **模型在行程內就沒有 wire。** `wireproxy.py` 誠實邊界 5 已經寫了（llama.cpp in-process、MLX）。
   enclosure 對這種 agent 會產出一個**乾淨得漂亮但是假的** 0
   ⇒ 必須有**正面訊號**，不能用「沒有外部封包」推論「有被中介」。
3. **TLS 內容需要 CA，而 CA 是倫理問題不是技術問題。**
   但展場不需要解它：enclosure 裡唯一到得了的就是我們自己的中繼，內容在中繼那端本來就是明文。

---

## 二、投哪幾層、什麼順序

⊕＝結構性關閉 · ○＝記得到 · △＝部分 · ✗＝無
（A/B/C/D ＝ `DECISION_20260919_BYPASS_STRESS` 的四類繞過）

| 層 | A | B | C | D | 可安裝性 | 可逆性 | 跨平台 |
|---|:-:|:-:|:-:|:-:|---|---|---|
| **1. enclosure（bwrap netns+mountns，唯一一條路到中繼）** | ⊕ | ⊕ | ⊕ | ⊕ | 一次 root ＋ systemd unit | 刪 unit；ns 本來就不持久 | **Linux 完整**；macOS 只到 pf-per-uid（△）；Windows 不做 |
| **2. 收據對帳欄位 ＋ fail-closed 分級** | ○ | ○ | ○ | ⊕ | 純程式 | — | 全平台 |
| **3. 收歸 agent 自己的防護開關** | △ | △ | **⊕（Codex）／△** | ✗ | 近乎零成本 | 改回去 | 全平台 |
| **4. 框架掛鉤** | ⊕ | △ | ⊕ | ⊕（**唯一能分模型叫的 vs 框架自己叫的**） | 一檔／agent | 刪那個鍵 | 全平台，但每家不同、隨版本改 |
| **5. managed settings** | ⊕ | — | — | — | root 寫一個檔 | 刪檔 | Linux／macOS |
| **6. MCP** | ✗ | ✗ | ✗ | ✗ | 低 | 高 | 全平台 |
| **7. LD_PRELOAD / seccomp** | ✗ | △ | △ | ✗ | 高 | 中 | 差 |
| **8. PATH shim（現況）** | ✗ | ✗ | ✗ | ✗ | 已裝 | 已有 | **Linux 已證偽** |

### 順序（排定，不是選項）

- **P0 enclosure。** 只有它能讓人類要的那句話為真，而且 `sandbox.py` 已有 `BwrapSandbox`。
  ⚠ 展場 VM 要先做主機政策決定：Ubuntu 24.04 的 `kernel.apparmor_restrict_unprivileged_userns=1`
  擋掉非特權 bwrap（`sandbox.py` docstring 已量過並**刻意沒自己決定**）。
  **展場機器是我們的，就決定它。**
- **P0 收據對帳 ＋ fail-closed 分級。** 沒有這個，enclosure 只產生資料不產生宣稱。
  新欄位：`enclosure{ns_id, policy_sha256, applied}`、
  `framework_hook{agent, contract_version, canary_fired}`、
  `reconciled{relay_calls, hook_events, unexplained}`、`tier`。
  任一不成立 ⇒ 收據寫「未認證」、退出碼不是 0。
- **P0.5 把 agent 自己的防護開關收歸 Vacant 管。** 最便宜的一筆：
  `vacant install` 本來就在寫 Codex config，順手把 `sandbox_mode` 釘在 `workspace-write`，
  並把 agent 的沙箱／approval 姿態寫進收據。**現在這格是負的。**
- **P1 框架掛鉤，四個 agent 各一格，而且要 canary。** Claude Code → OpenCode → Codex → pi。
- **P2 managed settings**：把掛鉤從「刪得掉」升級成「那個 uid 刪不掉」。
- **不做 MCP**：agent 選擇呼叫的東西，L1，對人類的問題零貢獻。它是 UX 面。
- **不做 LD_PRELOAD**：Codex 是 Rust、Claude Code／OpenCode 是 Node、Go 靜態二進位直接發 syscall；
  子行程 unset 就沒了。seccomp user-notif 真的擋得住，但 netns 用 5% 成本拿到 95% 價值，而且我們已經有碼。
- **降級 PATH shim**：保留當入口便利，**文件與收據上明寫它不承重**。

### 掛鉤那條跟「不自造 agent」相容嗎

**它是那條原則的最佳實現，但前提是宣稱不能靠它。**

原則三要的是「不跟 agent 框架競爭，當那一層它們都載得動的東西」。
hook 是**廠商自己開的擴充點**——用它就是最強意義上的「跑在既有框架上」。
違反原則的是 fork 框架或出 patch 過的 binary。

但必須切開：**如果「每次必經」建立在 hook 上，每一次版本更新都是一次對核心宣稱的靜默降級**
（`--bare` 一個旗標就 skip hooks）。那樣撐不久，最後會被逼去自己做 agent
——**原則會被自己的重量壓垮**。

⇒ **分工：kernel 給「有沒有」（保證），hook 給「是什麼、為什麼」（語意與閘門）。**
保證不可以依賴廠商；紀錄的品質可以。

---

## 三、某個 agent 兩條路都不給怎麼辦

**先更正前提：在 Linux 上這件事不會發生。** enclosure 完全不需要 agent 配合
——它連 agent 叫什麼名字都不必知道。
⇒ **「兩條路都不給」不是 agent 的屬性，是平台的屬性。**
真正會落到那格的是：沒有 root 的 macOS、Windows、以及行程內模型。

**決定：三級，級別是量出來的不是宣告的，展場只跑 A 級。**

| 級 | 條件 | 收據能說的話 | 退出碼 |
|---|---|---|---|
| **A 全程受控** | enclosure 成立 ＋ 掛鉤 canary 有燒 ＋ `unexplained == 0` | 每一通模型呼叫都經過 Vacant，且都對得上一個工具事件 | 0／20／21 既有語意 |
| **B 全程紀錄、工具層未閘門** | enclosure 成立、無掛鉤 | 每一個離開的位元組都留下紀錄；**分不出哪通是模型叫的、哪通是框架自己叫的** | 新碼，不是 0 |
| **B′ 反轉** | 行程內模型 | 工具層每次有紀錄；**模型通道不在網路上，Vacant 沒看到它** | 新碼，不是 0 |
| **C 未受控** | 兩者皆無 | **拒發收據**，不是發一張弱的 | 新碼 |

三條紀律：

1. **級別由探針決定。** SessionStart 放 canary：一個必定觸發掛鉤的工具呼叫、
   一個必定出現在中繼日誌的 `connect()`。沒燒到就自動降級。
   ⚠ **不准用「我們裝過了」推論「它在」**——這正是 Linux 上 `install-status`
   說「✓ 已寫入」而 codex 其實起不來的同一個病。
2. **C 級不發收據。** 意思不明的收據比沒有更糟：它會讓「拒交」與「沒跑過」長得一樣，
   那正是 A 類那四格的病。
3. **展場只允許 A 級。** 不要出「支援五個 agent、其中三個降級」。
   牆上直接列每個 agent 的級別與降級原因——**一個活的「誰可以被究責」計分板**。
   既誠實，也是更好的展件。

---

## 四、口徑

**現在那句「繞得過，但繞過一定留下痕跡」不是不夠，是目前為假。**
C 類 5/5 繞過而收據一個字沒變；unix socket 在封鎖之下 200 OK 而計數器 0。
拿 21 格去打會當場斷掉。

### 新的講法（可直接進 README，每句對應一個收據欄位）

> **Vacant 不宣稱 agent 不會想繞過。它做的是把別的路拿掉。**
>
> 在 Vacant 圍起來的執行域裡，agent 跑在自己的 network namespace 與 mount namespace 中：
> 除了通往 Vacant 中繼的那一條路以外，**沒有其他路由、沒有 DNS、看不到其他行程的 socket 檔**。
> 不是「我們擋掉了別的路」，是**別的路在那個 namespace 裡不存在**。
> 所以「這一次有沒有經過 Vacant」不是抓漏率，是結構事實。
>
> **有效範圍寫在每一張收據上**：`enclosure`（namespace 識別 ＋ 政策 sha256）、
> `framework_hook`（哪個框架鉤子、哪個契約版本、開場 canary 有沒有燒）、
> `reconciled`（中繼看到的每一通有沒有對得上框架事件）。
> 任一不成立，收據**不會變弱一點**——它會寫「未認證」，退出碼不是 0。
>
> **Vacant 不宣稱能約束擁有 root 的人。** 圍牆是安裝者用更高權限築的，安裝者就是被究責的那一方。
> 要讓圍牆失效必須由他動手，而那個動作會改掉 `enclosure` 雜湊
> ——**關掉 Vacant 是看得見的狀態改變，不是沉默的缺口**。
>
> **三件明寫做不到的事**：模型跑在 agent 行程內時網路上沒有通道，圍牆給出的「零外部流量」
> 是真的但不構成「有被中介」；TLS 內容要中繼配合或憑證，我們不裝憑證；
> 圍牆只管網路，不管 agent 在自己工作區裡做了什麼。

### 怎麼扛住有人拿 21 格來打

**不要辯解，把那 21 格變成這句話的驗收條件。**
那批資料是 PATH shim 版本量的，這句話不是 PATH shim 版本說的。

- **預註冊**：同一份 `runcell.sh`、同樣五 agent × 四類、同樣把每個 agent 的防護關到底，
  只換成在 enclosure 裡跑。
- **通過條件**：C 類五格的兩個 `curl` **每一個都要在中繼日誌或收據上出現一列**
  （成功或 `Network is unreachable` 都算，「沒有那一列」不算）；
  B 類的離線位元組要落在中繼那側；unix socket 探針要得到連線拒絕。
- **預先寫死否證條件**：只要有任何一格在 enclosure 裡仍產出「世界變了、收據沒變」，
  這句話就是假的，就撤掉——照 V3 那次撤掉舊句子的同一作法。
- **負向控制**：不套 enclosure 那格，`enclosure.applied` 必須是 `false` 而不是 `0`（鐵律 3）。

---

## 五、資訊不足、發射前必須補的六項

1. **五個 agent 進得了 enclosure 嗎（完全沒量）。** R530 的 bwrap 只跑過短指令，
   沒跑過需要 node／npm cache／自己設定目錄的完整 agent。
   要量：每個 agent 在「只有中繼到得了」之下能不能跑完一題，還是直接硬失敗。
   **這是整個方案的單點風險。**
2. **掛鉤到底會不會燒、擋不擋得下來（完全沒量）。**
   矩陣：5 agent × {事件有燒／能 deny／在 `--dangerously-skip-permissions`／`--yolo` 之下仍然燒／
   managed policy 蓋得住}。
   ⚠ 特別要量 Claude Code 的 `--bare`（文件逐字 `skip hooks`）與 `disableAllHooks`
   能不能被 managed settings 釘死——**這格決定框架切面是 L3 還是 L5**。
3. **Codex `[features].hooks` 的預設與持久性。** Otty 必須自己去翻它 ⇒ 預設關。
   升級會不會被蓋掉？`managed_dir` 的 `requirements.toml` 能不能強制它？
4. **Codex 內建的 `NetworkMitm` / `NetworkDomainPermissions` / `NetworkUnixSocketPermissions`
   到底是什麼。** 如果它就是廠商支援的「所有流量走我們的中繼、逐網域白名單」，
   Codex 這格可能根本不需要我們自己的圍牆。
   **這是目前投報率最高的一次調查，成本只有讀文件。**
5. **展場 VM 的 AppArmor 決定。** `kernel.apparmor_restrict_unprivileged_userns=1` 底下裸 bwrap 起不來；
   兩個選項（只放行 `/usr/bin/bwrap` 的 profile，或走 `sudo -n bwrap` 並把工作區放 `/var/tmp`）
   `sandbox.py` 已量過，**要一個人類決定**。
6. **行程內模型的正面偵測訊號。** 現在只有「沒有外部封包」，推不出「有被中介」。
   缺一個正面判據（例如中繼那端 session 計數 > 0 才准發 A 級收據）。

---

## 六、一句話

人類是對的，而且比他想的更可行——
**不可能的是「靠更多封鎖規則補到 100%」，可能的是「把別的路拿掉」**，
而這個 repo 為了隱藏測資已經寫過那一招（`sandbox.py` 的最小 rootfs），只是從來沒把它用在網路上。

展場機器是 Linux VM、是我們自己的、而且本來就要離線
——**那正是這招成本最低、效果最完整的地方**。
