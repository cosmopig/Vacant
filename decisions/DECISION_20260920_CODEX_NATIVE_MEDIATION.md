# DECISION 2026-09-20：Codex 自己就把 C 類洞補死了（macOS 實測，Linux 未量）

**上位裁決**：`DECISION_20260920_COMPLETE_MEDIATION.md` §五-4 列為「投報率最高的一次調查」。
本檔是那項調查的結果。

**一句話**：Codex 0.153.2 內建的 `network_proxy` 已經在**核心層**（macOS seatbelt）
把「agent 用 shell 直接 curl 出去」堵死，而且流量可以接到 Vacant 的 proxy 上游。
**Codex 那一格不需要我們自己築 netns 圍牆**——但四條附帶條件不滿足就等於沒開。

⚠ **全部實測在 macOS / seatbelt / Intel Mac 上。展場機器是 Linux VM（bwrap/landlock），那條路未量。**
⚠ **沒有一條有官方文件背書**——全部是 binary 字串 ＋ 本機實跑。派去查線上文件的 subagent 沒回來。

環境：`codex-cli 0.153.2`，
binary＝`~/.codex/packages/standalone/releases/0.153.2-x86_64-apple-darwin/bin/codex`（226M，Mach-O x86_64）。

---

## 一、schema（差分解析器探測出來的，不是猜的）

方法：餵故意錯的值進去，讓 serde 把合法欄位吐出來
（`mode="ZZZ"` → `unknown variant 'ZZZ', expected 'limited' or 'full'`；
`mitm.zzz=1` → `unknown field 'zzz', expected 'hooks' or 'actions'`）。

⚠ **是 `[permissions.<name>]`，不是 `[permissions.profiles.<name>]`。**

```toml
[permissions.<name>]
description = "..."
extends = "<另一個自訂 profile>"           # 沒有 builtin 可繼承

[permissions.<name>.filesystem]            # map: 路徑 -> "read"|"write"|"deny"|"none"
"/" = "read"

[permissions.<name>.network]               # NetworkToml，13 欄
enabled = true                             # ★ 總開關，預設 false
mode = "limited" | "full"
allow_upstream_proxy / dangerously_allow_non_loopback_proxy
dangerously_allow_all_unix_sockets / allow_local_binding
proxy_url / enable_socks5 / socks_url / enable_socks5_udp

[permissions.<name>.network.domains]       # 網域 -> "allow"|table
[permissions.<name>.network.unix_sockets]  # 路徑 -> "allow"
[permissions.<name>.network.mitm]                   # 只有 hooks / actions 兩欄
[permissions.<name>.network.mitm.hooks.<h>]         # 7 欄，`host` 必填
[permissions.<name>.network.mitm.actions.<a>]       # strip_request_headers / inject_request_headers
```

`codex features list` 實跑：

| 旗標 | stage | effective |
|---|---|---|
| `network_proxy` | **experimental** | **false** |
| `respect_system_proxy` | under development | false |
| `hooks` | **stable** | **true** |

打開：`codex sandbox --enable network_proxy` 或 `-c features.network_proxy=true`。

---

## 二、繞過電池（`network_proxy` 開、`mode="limited"`、allowlist 只有 example.com）

| 格 | 測法 | 結果 |
|---|---|---|
| A | 白名單 `https://example.com` | `http=200` ✅ |
| B | 非白名單 `https://www.wikipedia.org` | `rc=56`（proxy 斷）**擋下** |
| C | 裸 IP ＋ Host 標頭 | `http=400`（proxy 回絕，沒出去） |
| D | `curl --noproxy '*'` | `rc=6` DNS 解不出來 |
| E | `https://1.1.1.1/` | `rc=56` |
| **F** | **`--noproxy '*'` ＋ 裸 IP** | **`rc=7` 連不出去** |
| **G** | **`env -u` 清掉所有 proxy 變數 ＋ 裸 IP** | **`rc=7` 連不出去** |
| **H** | `nc -z 104.20.23.154 80` | **TCP_BLOCKED** |
| **I** | `nc -z 1.1.1.1 443` | **TCP_BLOCKED** |
| **J** | **python raw socket** | **`PermissionError [Errno 1] Operation not permitted`** |
| K | `dig` 直接查 | `bind: Operation not permitted` |

**對照組（證明量得動）**：同樣的 curl 在 sandbox 外 `http=200`；裸 IP 在 sandbox 外 `http=200`。

⇒ **F/G/H/I/J 就是 C 類洞，而且不是封包計數器那種軟擋，是 `Errno 1`。**

機制：環境變數只是勸導，真正咬人的是 seatbelt。binary 裡的 sbpl 片段：
```
; when network access is enabled, these policies are added after those in seatbelt_base_policy.sbpl
; allow DNS lookups while application traffic remains proxy-routed
(deny default)
(allow network-outbound (remote ip "localhost:<PORT>"))
```

Codex 自己生一張 CA 並自簽（`openssl x509` 實證）：
`subject=CN=network_proxy MITM CA`，落在 `$CODEX_HOME/proxy/ca-*.pem`，
然後把 **40 個環境變數**注進子行程（`HTTP_PROXY` / `ALL_PROXY=socks5h://…` /
`NPM_CONFIG_*` / `SSL_CERT_FILE` / `NODE_EXTRA_CA_CERTS` / `GIT_SSH_COMMAND` 走 `nc -X 5 -x` …）。

---

## 三、上游可以接 Vacant（實測成功）

起一個會記 log 的 proxy 在 `127.0.0.1:9911`，把 `HTTPS_PROXY`／`HTTP_PROXY` 放在
`codex sandbox` 的**父行程**環境裡。我們的 proxy log：

```
2026-09-20T01:51:23  REQ CONNECT example.com:443 HTTP/1.1
```

三種組合（`allow_upstream_proxy=true`／不設／再加 `--enable respect_system_proxy`）**都**命中，都 `http=200`。

⇒ 鏈：**sandbox 子行程 → Codex 的 loopback MITM proxy → Vacant proxy → 外網**

⚠ **誠實邊界**：上游看到的是 `CONNECT host:port`，**不是明文 body**。
Codex 自己解 TLS 再用 CONNECT 隧道丟給我們。
⇒ 這條鏈給 Vacant 的是**每一筆出網的網域＋時間**，**不是內容**。
要內容得走 Codex 自己的 `mitm.hooks`／`inject_request_headers`，**那條沒跑通**。

---

## 四、unix socket（我們自己補不了的那條）

| 設定 | 結果 |
|---|---|
| sandbox 外（對照組） | `UNIX_OK b'HELLO_UNIX'` |
| profile 沒寫 `unix_sockets` | **`PermissionError [Errno 1]` 擋下** |
| `[..network.unix_sockets] "<path>" = "allow"` | `UNIX_OK` |
| `--allow-unix-socket <path>` 旗標 | `UNIX_OK` |
| `dangerously_allow_all_unix_sockets = true` | `UNIX_OK` |

seatbelt 規則是路徑語意：
```
(allow network-bind     (local  unix-socket (subpath (param "UNIX_SOCKET_PATH_n"))))
(allow network-outbound (remote unix-socket (subpath (param "UNIX_SOCKET_PATH_n"))))
```

⚠ **抽象 socket 在 macOS 上根本不存在**（Linux 專屬）⇒ 那題在 macOS 上不成立。
**Linux 上是一個全新的、必須量的格子。**

---

## 五、`/etc/codex/requirements.toml`：管理員層，使用者蓋不掉

⚠ **這一整節是讀 binary 讀出來的，不是跑出來的。** 這台 `/etc/codex/` 不存在（`ls` 實證）。

層級順序（binary 內的 layer 列舉）：
```
packagedDefaults < enterpriseManaged < mdm < system < user < profile < project < dotCodexFolder < sessionFlags
```

絕對路徑（binary 字串，鄰接出現）：`/etc/codex/config.toml`、`/etc/codex/requirements.toml`。
其他識別字串：`<managed-requirements>/requirements.toml`、`<mdm:…>`、`<enterprise-managed:…>`、
`/etc/codex/managed_config.toml`（legacy）。

`ConfigRequirementsToml` 有 **39 欄**，跟我們有關的：
`allowed_permission_profiles`、`default_permissions`、`allowed_sandbox_modes`、
`allowed_approval_policies`、`allow_managed_hooks_only`、`feature_requirements`、
`experimental_network`、`network_proxy.enabled`、`permissions.*`、
`hooks.managed_dir`、`hooks.windows_managed_dir`。

**「使用者蓋不掉」的直接證據**——binary 裡的錯誤字串顯示它不是「合併」而是**駁回並強制回落**：
```
Configured value for `permission_profile` is disallowed by requirements;
  falling back from `X` to required value `Y`
requirements.toml default_permissions `X` must be allowed by allowed_permission_profiles
```

`hooks.managed_dir` ＋ `allow_managed_hooks_only` ＝ 只跑管理員目錄裡的 hook，
使用者自己的 `~/.codex/hooks.json` 被忽略。

---

## 六、hooks

- **stage `stable`、effective `true`。**
- 人類的 `~/.codex/config.toml` 第 276–280 行**已經明寫** `[features] hooks = true`（Otty 放的；
  `/Applications/Otty.app/Contents/Resources/agent-integration/codex/otty-hook.sh` 註解逐字寫了裝法）。
  `~/.codex/hooks.json` 存在，掛了 `PermissionRequest`／`SessionStart` 等事件。
- **升級不會蓋掉**（寫在 config.toml，升級換的是 binary）；
  而且 `codex doctor --json` 顯示 feature flag overrides 只有 `memories=true`
  ⇒ `hooks=true` 跟內建預設一樣，那行刪了也還是 true。
- 事件全集：`PreToolUse` · `PermissionRequest` · `PostToolUse` · `PreCompact` · `PostCompact` ·
  `SessionStart` · `SessionEnd` · `UserPromptSubmit` · `SubagentStart` · `SubagentStop` ·
  `Stop` · `Interrupt`。
  handler 型別：`Command` / `Agent` / `Prompt` / `McpTool`（後兩者 binary 說 "not supported yet"）。

---

## 七、🔴 四條會讓它整個退回「沒開」

### 7.1 `network_proxy` 關著的時候 `mode="limited"` **靜默失效**——這是 fail-**open**

| 組合 | 結果 |
|---|---|
| profile 沒寫 `[network]` 或沒寫 `enabled` | **不給網路**。`curl` → `rc=6`（DNS 就死） |
| `enabled=true` ＋ `network_proxy` **關** | **全開，`mode="limited"` 完全不生效**。`nc -z 1.1.1.1 443` → **TCP_OPEN**；非白名單 wikipedia.org → **`http=200`** |
| `enabled=true` ＋ `network_proxy` **開** | 核心層強制（§二） |

⚠ **你設了 allowlist、它不報錯、它也不執行。**

⇒ **Vacant 的收據必須實證 proxy 有在跑**——檢查子行程環境有 `CODEX_NETWORK_PROXY_ACTIVE=1`，
或我們的上游真的收到流量。**不能只檢查設定檔寫了什麼。**
這就是本專案「判成 0 之前先證明量得動」那條紀律的 Codex 版本。

### 7.2 父行程不在沙箱裡

Codex 自己的模型呼叫不走這條路。`codex doctor --json` 說 `"managed proxy": "not configured"`。
⇒ Vacant 要記模型呼叫**還是得自己攔**，現有 proxy 那條路不變。

### 7.3 上游只看得到 `CONNECT host:port`，看不到 body

「每一次執行都要經過 Vacant」在**出網事件**這一層成立，在**內容**那一層不成立。
**報告裡不可以把這兩件事講成一件。**

⚠ binary 裡還有一句 Codex 自己的自白：
`This terminal was launched outside the sandbox, bypassing any managed network proxy.`

### 7.4 🔴 Linux 沒量到

展場機器是 Linux VM，後端是 **bwrap / landlock 不是 seatbelt**。
上面所有 `Errno 1` **都是 macOS 的證據**。

---

## 八、要補什麼才敢說「夠了」

- [ ] **Linux VM 上重跑 F/G/H/I/J ＋ unix socket 四格**（已派）
      ⚠ Linux 多一格 macOS 沒有的：**抽象 namespace socket**
- [ ] `sudo mkdir /etc/codex` ＋ requirements.toml，**實證使用者蓋不掉**（§五目前是讀的不是跑的）
- [ ] `codex exec` ＋ **API key（不走 ChatGPT）**驗 legacy `sandbox_mode="workspace-write"` ＋ `network_access`
- [ ] `mitm.hooks` / `inject_request_headers` 跑通——能把「歸屬 metadata」簽進每一筆出網的話收據會強很多
- [ ] **官方文件核對**（目前零條有文件背書）

---

## 九、動了什麼、還原了沒

- **完全沒碰** `~/.codex/auth.json`、任何 token、`wss://` 登入路徑。
- **完全沒改** `~/.codex/config.toml`。實測全部用隔離的 `CODEX_HOME=<scratchpad>/ch`。
  驗證：`shasum -a 256` → `558641c7…a834f6`，mtime 仍是 `Sep 18 14:49`（早於該次 session）。
- scratchpad 產物、兩個背景行程（logging proxy、unix socket server）已 `pkill`，`us.sock` 已刪。
- repo 內的 `__sbx_probe` 探測檔已刪。
- 副作用：跑 sandbox 時 macOS 在 `~/Library/Logs/DiagnosticReports/` 產生數個 `echo`／`sh` 的 `.ips`
  ——那是 seatbelt 殺掉受限子行程的正常產物，**不是 codex 自己 crash**
  （一開始誤判過，讀 `parentProc: codex` 才看出是子行程被殺）。
