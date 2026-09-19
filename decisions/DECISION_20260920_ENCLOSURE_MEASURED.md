# DECISION 2026-09-20：enclosure 成立，五個 agent 全部進得去（vacant-dev 實測）

**上位裁決**：`DECISION_20260920_COMPLETE_MEDIATION.md` §五-1 列為「**整個方案的單點風險**」。
本檔是那項量測的結果：**沒有單點風險。**

機器：vacant-dev（Tailscale `100.124.254.83`、hostname `user1`、Ubuntu 24.04、kernel 6.8.0-137、Python 3.12.3）。
上游：1004 LM Studio `http://100.86.226.21:1234`、模型 `gemma-4-12b-it-qat`。

**沒有重開任何機器、沒有改任何 sysctl、沒有殺任何不是自己起的行程。**
（人類的 29 天 `http.server 8000` 與 17 天 `claude --resume win1003` 全程存活，
`vacant-exhibit.service` 全程 `active`。）

---

## 一、enclosure 的定義

```
bwrap --unshare-all --die-with-parent
  --ro-bind /usr  --ro-bind /etc
  /bin /sbin /lib /lib64 → 符號連結
  --proc /proc  --dev /dev
  私有 tmpfs：/tmp  /run  /var/tmp          ← 路徑型 socket 死在這裡
  --bind <工作區>
  唯一一扇門：主機的路徑型 unix socket → /run/vacant/relay.sock
              enclosure 內一支 127.0.0.1:8787 → 那個 socket 的轉送器
```

## 二、先證明圍牆是圍牆

| 目標 | 負控制（不套 enclosure） | **enclosure** | 只有 `unshare -n`（無 mount ns） |
|---|---|---|---|
| 外部 IP `100.86.226.21:1234`（GET /v1/models） | **通**（`HTTP/1.1 200 OK`） | 擋（`Errno 101 Network is unreachable`） | 擋 |
| 外部 IP `1.1.1.1:80` | **通** | 擋（Errno 101） | 擋 |
| 同機**他 uid**（`nobody`, uid 65534）的 `127.0.0.1:19001` | **通** | 擋（Errno 111） | 擋 |
| **路徑型 unix socket** `/tmp/vacant_probe_20260920.sock` | **通** | 擋（`Errno 2 No such file`） | 🔴 **通——沒擋住** |
| 抽象 unix socket `@vacant_probe_abs_20260920` | **通** | 擋（Errno 111） | 擋 |
| DNS `example.com` | **通**（104.20.23.154） | 擋（`gaierror -3`） | 擋 |
| **門** `/run/vacant/relay.sock` | 通 | **通** | 不存在 |

- **負控制 7/7 全通、`mismatched=0`** ⇒ 那些目標**本來就是開的**，不是量到一堆本來就關著的東西。
- enclosure **6 擋 1 通、`mismatched=0`**。

⚠ **`DECISION_20260920_COMPLETE_MEDIATION` §一-2 的「關鍵精確度」被量到了**：
只有 `unshare -n` 時，`/tmp` 裡的**路徑型 socket 照連**。**netns ＋ mount ns 缺一不可。**

**端到端**（enclosure 內 `curl`）：

| 指令 | 結果 |
|---|---|
| `curl http://127.0.0.1:8787/v1/models`（門） | `HTTP=200 bytes=500`，回來的是真的模型清單 |
| `curl http://100.86.226.21:1234/v1/models`（直連上游） | `HTTP=000 rc=7` |
| `curl https://api.openai.com/v1/models` | `HTTP=000 rc=6`（名字解不出來） |
| `/etc/ssl/certs/ca-certificates.crt` | **在**（`--ro-bind /etc` 帶進來） |

**逃脫嘗試全部失敗**：

- `nsenter -t 1 -n ip addr` → **rc=1**，`reassociate to namespace 'ns/net' failed: Operation not permitted`
- enclosure 內再 `unshare -r -n` → 起得來，之後連外仍 `AFTER_UNSHARE_BLOCKED`
- `/sys/class/net` 不存在；`/proc` 只看得到 **4** 個行程（PID ns 真的有）；`/proc/net/tcp` 只有標頭 1 行
- `/usr` `/etc` 唯讀；`/home/user1` **根本不存在**；工作區寫得進去
- **七個憑證檔全部 `ABSENT`**（`.claude/.credentials.json`、`.codex/auth.json`、
  `.config/opencode/auth.json`、`.pi/agent/auth.json`、`.git-credentials`、`.cline-keys`、repo）
  ——**不是「擋住」，是不在檔案系統裡。`NEVER_TOUCH` 在 enclosure 裡是白拿的。**

## 三、五個 agent

任務：`Create a file named solution.py … exactly: def add(a, b): / return a + b`。
跑法＝enclosure 內跑 repo 既有的 `ops/vacantrun/wrap_agent.sh <agent> <prompt>`，
`VACANT_RUN_PROXY=http://127.0.0.1:8787`。
「門的通數」＝主機側中繼 log 數到的連線數＝**真的有經過 Vacant 那條路的證據**。

| agent | 版本 | 起得來 | 跑完一題 | 門的通數 | 硬/軟失敗 |
|---|---|:-:|---|:-:|---|
| **pi** | 0.85.1 | ✅ | ✅ `solution.py` 正確 | 2 | 無 |
| **OpenCode** | 1.18.31 | ✅ | ✅ 正確 | 3 | 無 |
| **Claude Code** | 2.1.259 | ✅ | ✅ 正確 | 3 | 軟：印 `[claude-code:unrecognized_model]` 後照跑 |
| **Codex** | 0.147.0 | ✅ | ✅ 正確（**它自己的 bash 工具也在 enclosure 裡跑**） | 5 | 軟：印 `Model metadata … not found` 後照跑 |
| **Hermes** | 0.19.0 | ✅ | ✅ 正確 | 5 | 無（裝好之後零問題） |

門的通數合計 22 ＋ 後續唯讀門測試 1 ＝ log 裡 23 筆，對得起來。
`--version` 在 enclosure 裡四個原生 agent 全部 rc=0。

**六個預想的失敗點，逐條實測**：

1. **node/npm**：`node` 不在非互動 PATH 上（**主機上就會發生，不是 enclosure 造成的**）。
   `node_modules`、`~/.npm`、npm cache **一個都不需要**。
2. **自己的設定目錄**：`~/.claude` `~/.codex`（除 `packages/`）`~/.config/opencode` `~/.pi` `~/.hermes`
   **全部沒綁，五個 agent 照跑**——`wrap_agent.sh` 走 relocate 變數在私有 `/tmp` 現做一份設定。
3. **DNS**：沒有一個 agent 在啟動時因為解不出名字而死。
4. **TLS 根憑證**：`CA_PRESENT`。
5. **暫存目錄**：需要，**私有 tmpfs 就夠**（`mktemp -d` 全部落在裡面）。
6. **零硬失敗。** 兩個軟失敗與 enclosure 無關。

⚠ **口徑**：這是**一題、one-shot 模式**的結果。
**互動 TTY 模式、MCP server、git 操作、需要 `npx`／外掛下載的長任務都沒量。**

## 四、最小綁定清單

| agent | 要 `--ro-bind` 的路徑 | 備註 |
|---|---|---|
| Claude Code | `/home/user1/.local/share/claude`（216 MB ELF，bind 不佔磁碟） | 走 PATH 要再綁 `/home/user1/.local/bin` |
| Codex | `/home/user1/.codex/packages` | ⚠ **只綁 `packages/`，不要綁整個 `~/.codex`**（`auth.json` 在那裡） |
| pi | `/home/user1/.local/opt/node-v22.23.2-linux-x64`（936 MB） | `ENC_PATH` 要含 `<該目錄>/bin`，否則 `#!/usr/bin/env node` 找不到 node |
| OpenCode | 同上（`opencode.exe` 在該目錄的 `lib/node_modules/opencode-ai/bin/`） | |
| Hermes | 一個 venv。**vacant-dev 上要自己裝**：`python3 -m venv … && pip install hermes-agent`（< 1 分鐘、**214 MB**） | 系統沒有 `pip`／`pipx`，`python3 -m venv` 可用 |

**要帶真實設定目錄進去時**：`--ro-bind /dev/null <path>/auth.json` **有效**
（實測 enclosure 內 `stat` size=0、讀出空內容）。
⚠ 對照組（不遮蔽）＝**真的讀得到**（3932 bytes）。
⚠ 第一次量這格時 `head` 回 `Permission denied`，**那是量具說謊**（複測 `os.access`／`open` 都 True）
——**不准拿那一次的輸出當「不綁也讀不到」的證據**。

**磁碟**：enclosure 檔案系統成本 ≈ 0（全是 bind mount）。唯一實際佔磁碟的是 Hermes 的 214 MB，已清掉；
清掉前確認過那是自己建的，父目錄（09-19 的舊證據）**原封不動**。收工 `df` 回到 2.5G，與開工相同。

## 五、AppArmor：五天前就過了，而 `sandbox.py` 的 docstring 過期了

- `kernel.apparmor_restrict_unprivileged_userns = 1`（來自 `/usr/lib/sysctl.d/10-apparmor.conf`，**沒動它**）
- **但裸 `bwrap --unshare-all` 現在起得來**，`rc=0`，uid 對、netns 只有 `lo`
- 原因：**`/etc/apparmor.d/bwrap` 已經存在，日期 Sep 15 01:43**，內容就是 `ops/gain/r530/bwrap.apparmor`
  （`profile bwrap /usr/bin/bwrap flags=(unconfined) { userns, }`），`aa-status` 認得它。
  **`DECISION_20260920_COMPLETE_MEDIATION` §五-5 的選項 (1) 在 2026-09-15 經人類授權裝好了**，
  紀錄在 `ops/gain/r530/SANDBOX.md`。

⇒ **那條「要人類決定」的問題消失了。**

| 選項 | 現在成本 |
|---|---|
| **(1)（現用）** | **零**。已裝、已載入、**只放行 `/usr/bin/bwrap` 一支**，其餘 binary 的限制一格沒鬆，也沒關那個 sysctl。回滾兩行 |
| (2)（`sudo -n bwrap` ＋ `/var/tmp`） | **不需要了**。可用備援（`sudo -n` 是 NOPASSWD，實測 rc=0），但代價仍在：confined bwrap 沒有 `dac_override` ⇒ 工作區不能放 `drwxr-x---` 的 `$HOME` 底下，＋每格多一次 `sudo`，＋`sandbox.py::_kill_group` 的教訓（提權過的行程組只有 root 殺得掉）會回來。**不建議** |

### ⚠ 兩件要修的文件漂移

1. **`vacant_network/vrun/sandbox.py` 模組 docstring 第 44–58 行**仍以**現在式**寫
   「裸 `bwrap` 在這台機器上起不來」「需要其中一項主機政策改動」。
   **那是 2026-09-13 的實測，2026-09-15 之後不成立。**
2. **`ops/gain/r530/SANDBOX.md` 最後一行**寫回滾「（或重開機後自然不載入）」——**很可能是錯的**：
   `apparmor.service` enabled ＋ active，`ExecStart=/lib/apparmor/apparmor.systemd reload` 會重載整個
   `/etc/apparmor.d/`，`apparmor_parser -Q` 對那個檔 `PARSE_OK` ⇒ 開機後**應該會**載入。
   ⚠ **但沒有重開機驗證（人類明令不准）** ⇒ 這是間接證據不是量到的。
   展場機器會被關機開機，**下次合法重開時要順手確認**。

## 六、🔴 誠實邊界（「沒量到」≠「量到 0」）

1. **真的 `proxyd` 沒接上去。** 本次的門是一支**不看內容的 byte pipe**，
   只證明「門開得起來、agent 走得過」。
   ⚠ **`vacant_network/vrun/proxyd.py` 只聽 TCP `127.0.0.1:<port>`，沒有 AF_UNIX**
   ——那是把這套接進 `vacant run` 的**具體程式碼缺口**。
2. 🔴 **門是 byte pipe 就等於一條通往 `upstream:1234` 的 TCP 隧道。**
   上線時那扇門**必須是會終結 HTTP 的 proxy**（會擋非模型 path 的那種），
   否則「唯一那條路」只是把洞從「任意主機」**縮小到「那一台上游」，不是關掉**。
3. **門的目錄要用 `--ro-bind` 不要 `--bind`。** 實測：唯讀綁定之下 unix socket **照樣連得上**
   （拿回 `HTTP/1.1 200 OK`），而目錄變成不可寫；現在用的 `--bind` 讓 enclosure
   **寫得進主機的門目錄**（實測 `WROTE /run/vacant`）。**要改的一行。**
4. `--new-session`（`BwrapSandbox` 有、本次的沒有）沒量。它擋 TIOCSTI 注入但會斷互動 TTY。
5. 只量了 one-shot、一題、單一 enclosure。**並行多格、長任務、auto-compact、MCP、
   `npx` 動態下載、互動模式都沒量。**
6. **macOS 上做不到**（沒有 bwrap、沒有 namespace）⇒ 這件事只在 Linux 成立。
   展場機器是 Linux VM ⇒ 對交付物不構成問題，**但開發機上永遠驗不了這一層**。
7. ⚠ **vacant-dev 與 Mac 的版本號不同，不可混寫**
   （Linux：claude 2.1.259、codex 0.147.0；Mac：claude 2.1.278、codex 0.153.2）。

### 量具說謊紀錄（本輪自己踩到並複測的三個）

- `nsenter_rc=0` 那一次抓到的是 **pipeline 的 rc 不是 nsenter 的**（直接抓＝rc=1）
- `READONLY /home/user1` 其實是 `No such file or directory`（**不是唯讀，是不存在**）
- `head` 讀 `auth.json` 回 `Permission denied` 那一次**複測不成立**

**上面表格裡的每一格都是複測後的值。**

## 七、一句話

**這條技術路線沒有單點風險。圍牆成立（減法，不是封鎖），五個 agent 全部進得去，
AppArmor 那一關五天前就過了。剩下的是把 `proxyd` 接到門上，而且那扇門要會講 HTTP。**
