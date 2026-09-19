# Codex managed requirements：把 agent 的每一次出網鎖進 Vacant（Linux 實測）

**2026-09-20，vacant-dev（Ubuntu kernel 6.8.0-137），codex-cli 0.147.0（musl 靜態 ELF）。**
⚠ 上一輪 macOS 那台是 **0.153.2**，**兩個版本號不可混寫**。

裁決正本：`decisions/DECISION_20260920_CODEX_NATIVE_MEDIATION.md`。
上位裁決：`decisions/DECISION_20260920_COMPLETE_MEDIATION.md`。

---

## 那份 requirements.toml（實測過的那一份，sha256 `b7e4ccb9e0b8fbe3640a3115e7cc88082e4e48fc85ca124cb7c7dc9b90590b31`）

放 `/etc/codex/requirements.toml`（**需要 root；路徑編死在 binary 裡，沒有 env 可以改**）。

```toml
default_permissions = "vacant"
allowed_permission_profiles = { vacant = true }

[feature_requirements]
network_proxy = true

[experimental_network]
enabled = true
allowed_domains = ["100.119.113.56"]
managed_allowed_domains_only = true

[permissions.vacant]
description = "Vacant egress only"

[permissions.vacant.filesystem]
"/" = "read"
"/var/tmp/nwkey" = "write"

[permissions.vacant.network]
enabled = true
mode = "limited"

[permissions.vacant.network.domains]
"100.119.113.56" = "allow"
```

### 🔴 兩件先前卡住的事，都不是「少一個鍵名」

1. **`[permissions.<name>]` 要寫在 `requirements.toml` 自己裡面**，不是 `/etc/codex/managed_config.toml`
   ——那是 legacy 層，profile 放那裡**不會被 requirements 採納**，所以會安靜地掉回 `read-only`。
   binary 裡的決定性一句：
   > `` `permissions.filesystem` is reserved for requirements-level filesystem constraints and cannot define a profile ``
2. 網域天花板的鍵是 **`[experimental_network]`**（top-level，型別 `RawNetworkRequirementsToml`）
   ——**不是** `[network_proxy]`、**不是** `[permission_profiles.x]`。

### 每一塊在承重什麼（逐塊拆掉重跑量出來的）

| 塊 | 拿掉會怎樣 |
|---|---|
| `[feature_requirements] network_proxy=true` **或** `[experimental_network] enabled=true`（**二擇一即可**） | 🔴 **兩個都沒有 ⇒ fail-OPEN**：agent 跑在**主機 netns**、`CODEX_NETWORK_PROXY_ACTIVE` unset、example.com **200**、raw socket 通。**allowlist 靜默失效**（證據 `out_Vc_*`） |
| `default_permissions` ＋ `allowed_permission_profiles` | 「使用者換不掉 profile」那道門（證據 `out_S1_*`） |
| `[experimental_network].allowed_domains` ＋ **`managed_allowed_domains_only = true`** | **網域天花板本身**，見下面的區辨實驗 |

**`managed_allowed_domains_only` 的區辨實驗**（同一份使用者 config，requirements 只差那幾行）：

| requirements | example.com |
|---|---|
| 無 `[experimental_network]` | **200 通** |
| ＋`allowed_domains` ＋ `managed_allowed_domains_only = `**`true`** | **403 擋** |
| ＋`allowed_domains` ＋ `managed_allowed_domains_only = `**`false`** | **200 通** |
| **只有** `enabled = true`（沒 `allowed_domains`） | **200 通** |

---

## 驗收（全部是 `codex exec` 真 agent 用自己的 shell 工具跑腳本、讀落盤檔）

上游＝1003 `gemma-4-12b-it-qat`，隔離 `CODEX_HOME`，假 key ＋ `model_provider="vacantproxy"`。
**沒碰 ChatGPT／`wss://`／`auth.json`。**

### ① 只有 Vacant 的端點通得了（`out_FINAL.txt`）
```
netns=net:[4026532792]                    ← 主機是 4026531840
CODEX_NETWORK_PROXY_ACTIVE=[1]
HTTP_PROXY=[http://127.0.0.1:35243]  ALL_PROXY=[socks5h://127.0.0.1:39825]
GET http://100.119.113.56:1234/v1/models -> http=200  body 是真的模型清單 JSON
```

### ② 其他一律不通
```
1.1.1.1         -> 403  {"status":"blocked","reason":"not_allowed","source":"baseline_policy"}
104.20.23.154   -> 403  同上
example.com     -> 403（http）／rc=56（https）
rawsock 三個目標 -> OSError [Errno 101] Network is unreachable
  ⚠ 包含 100.119.113.56 ⇒ **連 Vacant 也不能裸連，唯一出口是 codex 的 loopback MITM proxy**
```
🔧 **量具修過一次**：`104.20.23.154` 在對照組**也**回 403（Cloudflare `error code: 1003`）
⇒ 那一格原本**不具區辨力**。加上 body 擷取才分得開——擋下來的那個 403 body 是
codex proxy 自己的 `{"status":"blocked",...,"source":"baseline_policy"}`。

### ③ 使用者蓋不掉 — 十條反抗路徑

| # | 攻擊 | 結果 |
|---|---|---|
| S1 | 使用者自建 `wide` profile ＋ `default_permissions="wide"` | 擋下，回落到 required default |
| O2 | 定義**同名** `vacant` profile 想劫持 | **拒絕啟動**（`conflicts with a config-defined profile of the same name`） |
| O3／O4 | config／CLI `danger-full-access` | 擋下 |
| **O5** | **`--dangerously-bypass-approvals-and-sandbox`** | **擋下**（netns `4026532791`，仍非主機） |
| O6／O7／O8 | `-c features.network_proxy=false`／`--disable network_proxy`／config `[features]` | 擋下 |
| **O9** | **專案層 `./.codex/config.toml` 自建 profile** | 擋下 |
| O10b／O11 | `-c permissions.vacant.network.domains={...}`／`.mode="full"` | 拒絕啟動 |

全部：`example.com` 一律 403，`1003` 一律 200。

### ④ 負控制 — `/etc/codex` 不存在時全部要通

| 情境 | netns | PROXY_ACTIVE | 1003 | 1.1.1.1 | example.com | rawsock |
|---|---|---|---|---|---|---|
| 主機（無沙箱） | `4026531840` | 空 | 200 | 301 | 200 | CONNECT_OK |
| **N4** `/etc/codex` 移走 ＋ `-s danger-full-access` | `4026531840` | 空 | 200 | 301 | **200** | CONNECT_OK |
| **N5** 移走 ＋ 使用者 `wide` ＋ `--enable network_proxy` | 4026532792 | 1 | 200 | **301** | **200** | ENETUNREACH |
| **Vc** `/etc/codex` **在**但沒有強制那一行 | `4026531840` | **空** | 200 | 301 | **200** | CONNECT_OK |

**N5 是關鍵**：它證明拿來打的那份 `wide` config **本身有效**（不加 requirements 時真的放行 example.com）
⇒ ③ 裡的「擋下」是 **requirements 擋的**，不是攻擊 config 寫壞。

---

## 🔴 誠實邊界（引用時必須一起帶）

1. **`[experimental_network]` 這個鍵名帶著 `experimental_`**，上游改名／改語意的機率不低，
   而**徵兆是靜默失效不是報錯**（見下面的 `deny_unknown_fields`）。
   ⇒ **展場的收據必須實證 `CODEX_NETWORK_PROXY_ACTIVE=1` ＋ netns ≠ 主機**，
   **不能只檢查設定檔寫了什麼**。`Vc` 那格就是這個 fail-open 的實跑證據。
2. **只量了 `100.119.113.56` 這個裸 IP ＋ 純 HTTP。**
   帶 TLS 的 Vacant 端點、萬用網域（`*.example.com`）、`mode="full"` 在天花板下的行為**都沒量**。
3. **上游只看得到 `CONNECT host:port`，看不到 body。**
   「每一次出網都經過 Vacant」在**出網事件**這層成立，在**內容**那層不成立。兩件事不可講成一件。
4. 只在 **0.147.0 / Ubuntu 6.8.0-137** 上量過，**n = 1 台**。
5. **這一格擋的是 agent 的 shell。Codex 自己的模型呼叫不走這條路**（父行程不在沙箱裡）
   ——那條仍要 Vacant 自己攔。

---

## 量具說謊（兩個，第二個差點造成假陽性）

1. 🔴 **啟動橫幅全程說謊，十次全中**：即使 example.com 被 403、raw socket ENETUNREACH，
   橫幅照印 `sandbox: custom permissions (network access enabled)`。
   **判準只能看子行程的 netns ＋ `CODEX_NETWORK_PROXY_ACTIVE`。**
2. 🔴 **TOML 表作用域陷阱**：把 `default_permissions = "wide"` 用 `>>` 接在使用者 config 尾端，
   而尾端是 `[model_providers.vacantproxy]` 表 ⇒ 它變成
   `model_providers.vacantproxy.default_permissions`，**被靜默忽略**
   ⇒ 第一版是**假的通過**。是負控制報
   `config defines [permissions] profiles but does not set default_permissions` 才抓出來。

**根因**：requirements top-level **沒有 `deny_unknown_fields`**
⇒ **打錯的鍵靜默忽略，只有型別錯才會吐訊號。**
（先前那輪的 `[network_proxy] allowed_domains` 就是死在這。）

## 差分解析器探測（怎麼找到鍵名的，可照抄）

`codex features list` 是最快的探針（會載 requirements、秒回）。
⚠ 餵**錯的型別**不是錯的欄名——top-level 沒有 `deny_unknown_fields`，`zzz=1` 會**靜默忽略**。

| 探針 | 回應（＝區辨訊號） |
|---|---|
| `experimental_network = 1` | `invalid type: integer, expected struct RawNetworkRequirementsToml` ⇒ **鍵名確認** |
| `experimental_network.allowed_domains = 1` | `expected a sequence` |
| `experimental_network.managed_allowed_domains_only = 1` | `expected a boolean` ⇒ **欄位存在** |
| `experimental_network.mode`／`proxy_url`／`mitm` = 1 | **無錯** ⇒ 這三個在 requirements 層**不存在**（只在 profile 層） |
| `[permissions.x]` 單獨寫 | `config defines [permissions] profiles but does not set default_permissions` |
| `permissions.x.network = 1` | `expected struct NetworkToml` ⇒ profile 層用 `domains` map，**不是** `allowed_domains` |

## 其他順手量到的

- `codex exec` **沒有 `-P`**（那是 `codex sandbox` 的）。permission profile 的選擇鍵是
  config 裡的 **`default_permissions`**；`-p/--profile` 是 config profile，**兩回事**。
- `-c` 的 dotted path 會被網域裡的點切斷：
  `-c permissions.x.network.domains."example.com"="allow"` → `unknown variant 'com"'`。
  要寫 `-c '...domains={"example.com"="allow"}'`。
- codex 的 musl binary **每次啟動在 `/tmp` 丟一個 5.5 MB 的 `.so` 且不清**。

## 檔案

`out_*.txt`＝各格的 probe 落盤檔（`net_probe.sh`／`final_probe.sh` 產生）、`base_cfg.toml`＝基準使用者 config。
