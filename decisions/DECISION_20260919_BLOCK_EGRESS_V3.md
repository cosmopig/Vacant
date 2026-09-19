# DECISION 2026-09-19 — `block_egress.sh`（V3 出網封鎖）第一次被量

**狀態**：量完。**擋得住主要的出網路徑，擋不住五條**（逐條在 §4）。
**最重要的一句**：它把「安靜地出網到第三方」換成「安靜地失敗」——
**世界變了，收據沒變**（§3.3，26 個判斷欄位逐字相同）。

**為什麼現在量**：`vacant_network/vrun/wireproxy.py:46` 的誠實邊界寫著「不阻止 agent 走別的
路徑繞過它」⇒ Saltzer & Schroeder 的 complete mediation 不滿足。`block_egress.sh`
就是要補這個洞的那一支，而它要 root、會改整台機器的網路規則、又不在 wheel 裡，
所以從 2026-09-18 寫出來到今天**沒有任何一次實測**
（`docs/AGENT_COMPAT.md` 四處寫著「沒量過」、`docs/INSTALL_LOG_20260919.md` §4 同）。

**逐字證據**：`ops/vacantrun/egress_v3_20260919/`（探針 JSON、iptables 前後快照、
四格 `vacant run` 的 `run_RUN-ON.json`／`agent_stdout.log`／wire 索引、量具本身）。

---

## 1. 量的是什麼、在哪裡量、怎麼保證沒把自己鎖在外面

| 項 | 值 |
|---|---|
| 機器 | vacant-dev `user1@100.124.254.83`，Ubuntu 24.04.4，kernel 6.8.0-137 |
| iptables | v1.8.10（**nf_tables 後端**，不是 legacy） |
| 受測腳本 | `ops/vacantrun/block_egress.sh` sha256 `c86cb0ea…e49f`（`git archive` 出子集，與量測當下的 HEAD `eb655a38` 逐位元相同）<br>⚠ 量完之後另一個 session 的 `vacant`→`vacant_network` 全域改名動到本檔**一行註解**（現為 `02d1ea93…`），**規則與參數處理一個字沒動** |
| 量具 | `ops/vacantrun/verify_egress_block.py` sha256 `f1bb6d34…31d6` ＋ 本次新寫的 11 格探針矩陣 |
| 被封的 uid | **1001（`vagent1`，為這次量測新建、不在 sudo 群、量完 `userdel -r`）** |
| proxy／launcher 的 uid | 1000（`user1`）——**刻意不同 uid**，見腳本誠實邊界 4 |
| 上游 | 1004 `http://100.86.226.21:1234/v1`（`gemma-4-12b-it-qat`） |
| agent | Hermes Agent **0.19.0**（`pip install hermes-agent==0.19.0`，新裝的 venv） |

### 1.1 怎麼避免把自己鎖在外面（三層，都用上了）

1. **規則只打 uid 1001。** ssh 的 sshd 與我的互動式 shell 是 uid 0／1000，
   `-m owner --uid-owner 1001` 對它們一律不比對。腳本自己也擋 `--uid 0`（實測 rc=2）。
2. **心跳保險。** 套用之前先以 root 起一支 watchdog：心跳檔 `HOLD` 超過 300 秒
   沒被摸到就自動 `--undo`。ssh 斷線 ⇒ 心跳停 ⇒ 五分鐘內機器自己回到原狀。
   （本次沒有觸發；收工用 `STOP_WATCHDOG` 正常退出，見 `logs/watchdog.log`。）
3. **全量快照。** 套用前 `iptables-save`／`ip6tables-save` 落盤，收工後逐行比對。

### 1.2 還原驗收（做完一定要驗，這是紅線）

```
OUTPUT 鏈       : -P OUTPUT ACCEPT          （與套用前逐字相同）
OUTPUT6 鏈      : -P OUTPUT ACCEPT          （腳本從頭到尾沒碰 ip6tables）
iptables-save   : 去掉封包計數器後**規則逐字相同**（ipt_full_diff.txt 只剩 [pkts:bytes]）
uid-owner 規則數: 0
vagent1         : id: ‘vagent1’: no such user
/var/tmp/v3egress: 已刪；剩餘行程 0；機器上原有的兩個 http.server 沒被影響
```

---

## 2. 負向控制（**沒有負向控制的「擋住了」不算數**）

鐵律 3：「沒量到」≠「量到 0」。封鎖之前先證明這個 uid **真的出得了網**：

| 探針 | 封鎖前 | 封鎖後 | 還原後 |
|---|:--:|:--:|:--:|
| `tcp4_tailnet_1004`（100.86.226.21:1234） | ✅ | ❌ `No route to host` | ✅ |
| `tcp4_public_ip_literal`（1.1.1.1:443，不經 DNS） | ✅ | ❌ `No route to host` | ✅ |
| `tcp4_openrouter_dns`（openrouter.ai:443） | ✅ 104.18.2.115 | ❌ `No route to host` | ✅ |
| **`https_openrouter_models`（完整 TLS，收到 `HTTP/1.1 200 OK`）** | ✅ | ❌ `Network is unreachable` | ✅ |
| `dns_udp_direct_8888`（直接 UDP 打 8.8.8.8:53） | ✅ 64 bytes | ❌ `EPERM` | ✅ |
| `icmp_ping_1111` | ✅ | ❌ 100% loss | ✅ |
| `proxy_port_loopback`（127.0.0.1:8899，**正向控制**） | ✅ | ✅ | ✅ |
| `dns_via_systemd_resolved`（`gethostbyname`） | ✅ | **✅ 還是解得出來** | ✅ |
| `icmp6_ping_tailnet_1004`（IPv6） | ✅ | **✅ 照樣通** | ✅ |
| `loopback_relay_to_openrouter`（同機另一個 uid 中繼） | ✅ | **✅ `HTTP/1.1 200 OK`** | — |
| `tcp6_tailnet_1004` | ❌ timeout | ❌ timeout | ❌ |

最後那一列是**負向控制自己的負向控制**：1004 的 1234 埠只聽 IPv4，
所以「IPv6 連不上」在封鎖前後都成立 ⇒ **不可以拿它當「IPv6 被擋住了」的證據**。

封鎖前 `verify_egress_block.py` ＝ `NOT_BLOCKED`（量具有牙齒，不是永遠回 BLOCKED）。

---

## 3. 活體標本：Hermes 漏設 `CUSTOM_BASE_URL`（`AGENT_COMPAT.md` §12.2 對照 C）

這是**真實的洩漏路徑**不是人造的：Hermes 0.19.0 解 base_url 的鏈尾是編死的
`https://openrouter.ai/api/v1`，漏設一個環境變數它**不報錯**，安靜出網。

四格 `vacant run`（2×2：接線正確／漏設 × 封鎖 OFF／ON）。
agent 在 uid 1001，proxy＋launcher 在 uid 1000。

| 格 | 接線 | 封鎖 | `accepted` | `stop_reason` | `requests_seen` | `agent_rc` | agent stdout 第一行 |
|---|---|:--:|:--:|---|:--:|:--:|---|
| H1 | 漏設 | OFF | false | `visible_fail` | **0** | **0** | `HTTP 401: Missing Authentication header` ← **openrouter 回的** |
| H3 | 漏設 | **ON** | false | `visible_fail` | **0** | **0** | `API call failed after 3 retries: Connection error.` |
| H2 | 正確 | OFF | true | `visible_pass` | 6 | 0 | （正常完成，wire 六通全到 1004） |
| H4 | 正確 | **ON** | true | `visible_pass` | 6 | 0 | （正常完成，wire 六通全到 1004） |

### 3.1 洩漏被擋住了（H1 → H3）

H1 的 `HTTP 401` 是 openrouter.ai 伺服器回的 ⇒ 一次**完整的 TLS 會話到第三方**。
H3 同一支 wrapper、同一個模型、同一份 TASK，變成 `Connection error`（重試三次）。
`agent_wall_s` 5.811 → 17.691（時間花在重試）。**這是擋住了，不是「沒觸發」。**

### 3.2 正常的路沒有被擋死（H2 → H4）

H4 在封鎖之下照樣 `accepted=true`、`requests_seen=6`、退出碼 0，
wire 索引六通全部 `-> 200 openai http://100.86.226.21:1234/...`。
**擋住了但把正常路也擋死，那叫壞掉不叫封鎖**——這一格是它的區分測試。

### 3.3 ⚠ **但收據看不出差別**（本裁決最重要的一句）

H1（真的出網到第三方）與 H3（被擋下來）的 `run_RUN-ON.json` 逐欄比對：

```
相同欄位（26）：accepted, agent_rc, agent_timed_out, argv, arm, attempts_used,
  failures, feedback_into, infra_void, max_attempts, refused, requests_seen,
  retry, retry_constants, sandbox, stop_reason, upstreams, upstreams_defaulted,
  vacant, visible_passed, visible_total, wire_by_protocol, wire_digest,
  wire_errors, ws_end_sha256, ws_start_sha256
不同欄位（9）：agent_wall_s／run_wall_s（時間）、proxy_url（臨時埠）、
  task_id／workspace（我自己取的名字）、attempts／env／verdict_hash／verdict_sha256（前幾項的衍生）
```

**每一個判斷用的欄位都逐字相同。** 差別只出現在 `agent_stdout.log`，
而那不是收據欄位。

⇒ `docs/AGENT_COMPAT.md` 舊寫的「（封鎖）**能讓『沒被中介到』變成一個看得見的失敗
而不是一個沉默的洞**」**只成立一半**：對**操作者讀 agent 輸出**是看得見的，
對**收據**不是。`requests_seen=0 ＋ agent_rc=0 ＋ visible_fail` 這個組合，
在封鎖前後、在真拒交格與假拒交格之間，**仍然長得一模一樣**。

**可行的補法（便宜、這次順手量到了可行性）**：REJECT 規則自己有封包計數器。
H3 跑完的當下：

```
1  43 pkts  ACCEPT  -o lo            owner UID match 1001    ← 迴圈（agent↔proxy）
2   0 pkts  ACCEPT  -d 127.0.0.0/8   owner UID match 1001    ← 死碼
3   0 pkts  ACCEPT  -d 127.0.0.0/8 tcp dpt:8899              ← 死碼
4  73 pkts  REJECT  owner UID match 1001                     ← **被擋下的出網嘗試**
```

把第 4 條的計數器在 run 前後各讀一次、差值寫進收據，
「這一跑有沒有 agent 試圖繞過中介」就從**沒有欄位**變成**一個數字**。
（本裁決只證明計數器存在且會動，**沒有**實作進 `launcher.py`。）

---

## 4. 它擋不住什麼（逐條，都有實測）

> 這一節是這支腳本的誠實邊界。腳本自己寫了三條（uid 繞過、DNS、迴圈），
> 其中**DNS 那條在預設 Ubuntu 上是錯的**，而另外四條它沒寫。

### 4.1 ❌ **同機另一個 uid 的任何 listener ＝ 中繼**（腳本自己的邊界 4 比想像中寬）

規則 1 是 `-o lo -j ACCEPT`：**放行整條迴圈介面**，不是只放行 proxy 那個埠。
規則 3（`--dport 8899`）因此是**死碼**（實測 0 封包）。

實測：user1 起一支 127.0.0.1:8998 → openrouter.ai:443 的 TCP 中繼，
uid 1001 在封鎖之下經它做完整 TLS，收到 `HTTP/1.1 200 OK`。

⇒ 腳本註解說「只留 proxy 那個埠」與「已對 uid 封鎖出網，只留 127.0.0.1:8899」
**都名實不符**。要名實相符必須把規則 1 拿掉、只留規則 3
（代價：agent 連不到本機其他服務，包含 `127.0.0.53` 的 DNS，見 4.3）。

### 4.2 ❌ **unix domain socket：iptables 根本看不到**

實測：user1 在 `/var/tmp/v3egress/or.sock` 開一個 AF_UNIX 中繼轉給
openrouter.ai:443，uid 1001 連上去 → `HTTP/1.1 200 OK`，0.038 秒。
**這條路即使把迴圈規則收緊到只剩 proxy 埠也還在**，因為它不是 IP 封包。

### 4.3 ❌ **DNS 還是通的**——腳本誠實邊界 3 在 Ubuntu 預設設定上是**錯的**

腳本寫「DNS（53/udp）預設也被擋掉——這是刻意的」。
Ubuntu 24.04 的 `/etc/resolv.conf` 是 `nameserver 127.0.0.53`（systemd-resolved），
**那是迴圈位址** ⇒ 被規則 1／2 放行。實測封鎖後 `gethostbyname("api.openai.com")`
仍回 `172.66.0.243`。真正被擋掉的只有**繞過 resolved 直接打外部 DNS**
（`dns_udp_direct_8888` ⇒ `EPERM`）。

⇒ **一條低頻寬的外洩通道（DNS tunneling）在封鎖之下完整保留。**

### 4.4 ❌ **`verify_egress_block.py` 因此在預設 Ubuntu 上永遠回 `NOT_BLOCKED`**

它把 `negative_control_dns` 的期望寫死成 `False`。而 4.3 說明那一條在
systemd-resolved 機器上**永遠是 `True`**。實測封鎖之後：

```
verdict = NOT_BLOCKED | failed = ['negative_control_dns']
  negative_control_direct_upstream  reached=False   ← 擋住了
  positive_control_proxy_port       reached=True    ← 正常
  negative_control_dns              reached=True    ← 這一條讓 verdict 翻掉
```

⇒ `docs/VACANT_RUN.md` §5 步驟 4 寫的「**verdict 必須是 BLOCKED**」
**照著跑永遠不會成立**。錯的方向是安全的（假警報不是假安心），但它讓量具失去用處：
一個永遠回 NOT_BLOCKED 的驗證器跟一個永遠回 BLOCKED 的一樣沒有鑑別力。

附帶：該檔用 `subprocess.run(["iptables","-S","OUTPUT"])` 抓旁證，
但**只接例外不看 returncode** ⇒ 在它自己規定的執行方式（agent 的 uid）下
`iptables_S` 恆為空字串 `''`，而不是它 docstring 承諾的「拿不到也要記下拿不到」。

### 4.5 ❌ **IPv6 完全沒被碰**

腳本只下 `iptables`，**一行 `ip6tables` 都沒有**。實測封鎖之下 ICMPv6 ping
tailnet 對端（`fd7a:115c:a1e0::6135:e216`）照樣 1.0 ms 通。

**誠實邊界**：本機沒有公網 IPv6 路由（`curl -6 https://api.openai.com` ⇒
`Couldn't connect`），tailnet 對端的 1234 埠也只聽 IPv4 ⇒
**「IPv6 上的 TCP 出網」在這台機器上沒量到可用路徑，所以是「沒量」不是「沒有」**。
但 `ip6tables-save` 前後逐字相同是結構事實：**一台有公網 IPv6 的機器上，
這支腳本等於沒封。**

### 4.6 ⚠ **既有連線：送出方向會斷，但已經到手的位元組還讀得完**

封鎖前建好一條到 1004 的 TCP 連線，每 5 秒在同一條連線上發一次請求：

```
15:23:02  套用封鎖
15:23:04  i=6  ok   ← 讀到的是上一則回應殘留在**核心接收緩衝區**的位元組
15:23:19  i=9  ok   ← 同上
15:23:24  i=10 BrokenPipeError    ← 送出方向斷了
```

⇒ 送出方向在封鎖後**一個週期內**就失效；但 iptables 收不回已經進到本機記憶體的
資料。對「agent 已經把東西送出去了」這件事，封鎖是**事後無效**的。

### 4.7 ⚠ `--uid-owner` 只認送出封包的 uid（腳本自己的邊界 2，本次確認前提成立）

本次的 `vagent1` **不在 sudo 群**（實測 `sudo` ⇒ `a password is required`），
所以「agent 能 sudo 就繞得過」在這次的配置下沒有發生。
但這也說明：**這支腳本的有效性完全建立在「agent 跑在一個專屬、不能提權的 uid」
這個前提上**，而那個前提**不是這支腳本提供的**（見 §5）。

### 4.8 ⚠ 操作危害三條（都實測）

| 危害 | 實測 |
|---|---|
| **套兩次、拆一次** | 規則變成兩份；`--undo` 只拆掉各一份，**仍然在封鎖**（`1.1.1.1:443` ⇒ `No route to host`），而畫面上印的是「**已拆除**」 |
| **沒套用時 `--undo`** | stderr 出現四行 `iptables: Bad rule`，但 `\|\| true` 吞掉，最後一行仍印「已拆除」、退出碼 0 |
| **`--dry-run`** | 什麼都沒做，但照樣印「**已對 uid=1001 封鎖出網，只留 127.0.0.1:8899**」 |

三條都是同一個病：**印出來的那句話是它自己說的，不是量到的**——
正是 `verify_egress_block.py` docstring 第一段在講的那件事，只是腳本自己犯了。

### 4.9 ⚠ 不持久化、不是網路層以外的任何東西

- 沒有 `iptables-persistent`／`netfilter-persistent`（實測都 not-found）
  ⇒ **重開機規則自動消失**。安全面是好事（不會忘了拆），
  但「以為還封著」是真的風險，展場機器開機後必須重套。
- 只擋**網路層出口**。不擋寫共享檔案系統、不擋 agent 自己的本機動作
  （lint／git／內建重試），也不擋任何非 IP 的 IPC。
- REJECT 給 agent 看到的是 `No route to host`／`Network is unreachable`／`EPERM`
  ⇒ **agent 分不出「被管制」與「網路爛掉」**。這對展場說法有用：
  可究責性不需要 agent 知道自己被管，但也不該宣稱 agent「被告知」。

---

## 5. 要真的用 V3，`vacant run` 本身缺兩件（都是這次撞到的）

`vacant_network/vrun/launcher.py:303-307` 的 proxy 與 agent **在同一個行程樹、同一個 uid**，
而 `--uid-owner` 只認 uid ⇒ 整支 `vacant run` 跑在被封的 uid 上，**proxy 自己的上游
也會被封死**。launcher 沒有 `--agent-uid`。本次是手工包了一層
（`outer.sh`：`sudo -n -u '#1001'` 把 agent 降權，proxy 留在 user1）才量得成。

降權之後又撞到第二件：**Hermes 以 0600 建檔（不吃 umask）**，
launcher（另一個 uid）讀不到 ⇒ `_frozen_*` 的 `copytree` 直接
`PermissionError: [Errno 13]` 把整跑炸掉（`shutil.Error`，退出碼 1、沒有收據）。
本次在 wrapper 收尾 `chmod -R a+rwX` 繞過。

⇒ **「V3 可用」不等於「`block_egress.sh` 存在」。** 要能用，`launcher.py` 至少要有
(a) `--agent-uid` 把 agent 降到專屬 uid 而 proxy 留在操作者 uid，
(b) 凍結前對工作區做一次可讀化（或改用 root 讀）。這兩件**本裁決沒有做**。

---

## 6. 結論（口徑：可究責性，不是信任）

1. **`block_egress.sh` 會動，而且擋得住它宣稱擋的主要路徑**——不是壞掉、不是缺相依。
   負向控制、正向控制、活體標本、還原驗收四項齊備。
2. **complete mediation 仍然不滿足。** 加上它之後，繞過中介的路從「隨便一條」
   收斂到 §4 的五條（同機他 uid 的迴圈 listener、unix socket、systemd-resolved 的
   DNS、IPv6、已送出的位元組）。**收斂不是關閉。**
3. **它改變世界但不改變收據**（§3.3）。要讓「有沒有人試圖繞過」進到收據，
   最小改動是把 REJECT 規則的封包計數器差值寫進 `run_*.json`。
4. **文件要改三處**：`VACANT_RUN.md` §5「verdict 必須是 BLOCKED」不成立（§4.4）；
   「DNS 預設也被擋掉」不成立（§4.3）；「只留 proxy 那個埠」不成立（§4.1）。
5. **對展覽**：展場機器（Linux VM）如果要用 V3，重開機要重套（§4.9），
   而且畫面上**不可以說「agent 逃不掉」**——正確的說法是
   「**它只能走這一條路出去，而這條路上的每一個位元組都留了下來**」，
   後面接 §4 的五條，一條都不能省。

## 7. 這份裁決**沒有**證明的事

- **沒有量五個 agent**，只量了 Hermes 0.19.0 一個。其餘四個（Claude Code、Codex、
  OpenCode、pi）在封鎖之下會怎樣**沒量**。特別是 Codex 的 `wss://chatgpt.com`
  那條路——封鎖之下它應該連不上，但**沒量**。
- **沒有量 IPv6 上的 TCP 出網**（本機沒有公網 v6 路由，見 §4.5）。「沒量」不是「沒有」。
- **沒有量 raw socket／`AF_PACKET`**（需要 CAP_NET_RAW，`vagent1` 沒有，但沒有實際去打）。
- **沒有量 `bwrap`／`unshare` 沙箱與本封鎖併用**。`unshare --net` 是更強的隔離
  （連 proxy 都到不了），兩者的取捨沒量。
- **沒有把任何改動寫進 `vacant_network/vrun/`**。§3.3 的計數器補法與 §5 的兩個缺口都只是提案。
- **沒有在展場機器上量**（本次在 vacant-dev）。

---

### 附：逐字證據清單（`ops/vacantrun/egress_v3_20260919/`）

```
probe_before.json / probe_after.json / probe_restored.json   11 格探針矩陣（前／中／後）
verify_before.json / verify_after.json                       受測量具自己的輸出
dryrun.txt / apply.txt / undo.txt                            腳本三種模式的逐字輸出
ipt_before.txt / ipt6_before.txt                             套用前全量快照
ipt_after_apply_OUTPUT.txt                                   套用後的規則（順序）
ipt_counters_after_h3.txt                                    §3.3 的封包計數器
ipt_double_apply.txt / ipt_double_apply_one_undo.txt          §4.8 的操作危害
ipt_after_undo_OUTPUT.txt / ipt_after_undo_full.txt / ipt_full_diff.txt   還原驗收
hold.jsonl                                                   §4.6 既有連線的逐次紀錄
unix_relay_after.json                                        §4.2 unix socket 繞過
h_{nocustom,wired}_{noblock,block}/                          四格 vacant run 的收據與 wire
harness/                                                     本次量具與 wrapper（可重跑）
```
