# enclosure：把 agent 關進一個**只有一扇門**的房間（2026-09-20，vacant-dev）

主張一句話：**「每一次都經過 Vacant」不是靠規勸，是靠「別的路不存在」。**
圍牆用 `bwrap` 的 namespace 做（路不存在），門用 `proxyd --unix` 做
（會終結 HTTP、認得 path、逐通落盤、不持有金鑰）。

⚠ **這不是「不會被繞過」。** 圍牆外面跑的 agent 什麼都連得到，本目錄
一個字都沒有改變那件事。能說的只有：**放進這個 enclosure 的行程，
模型通道以外沒有路可以走**，而那一條路上的每一通都在 journal 裡。

- 機器：vacant-dev（Ubuntu 24.04.4、kernel 6.8.0-137、Python 3.12.3、bwrap 0.9.0）
- 上游：**1004** `http://100.86.226.21:1234`（非 thinking），`gemma-4-12b-it-qat`
- agent 版本：**codex-cli 0.147.0**、**OpenCode 1.18.31**
  （早上那一輪還量了 pi 0.85.1／Claude Code 2.1.259／Hermes 0.19.0，
  **那三格是 byte-pipe 門的結果，不可以跟本輪混寫成一組數字**）
- 前提：`/etc/apparmor.d/bwrap` 已安裝（2026-09-15，見 `ops/gain/r530/SANDBOX.md`）。
  沒裝的話 `run_probes.sh` 的量具檢查會**當場停**，不會安靜地退到沒有沙箱。

---

## 怎麼重跑（負控制與 enclosure 兩組**都會跑**）

```bash
# 圍牆 ＋ 門的全套探針（約 15 秒）
bash ops/vacantrun/enclosure_20260920/run_probes.sh
# 一個 agent 在 enclosure 裡跑完一題
bash ops/vacantrun/enclosure_20260920/run_agent.sh codex
bash ops/vacantrun/enclosure_20260920/run_agent.sh opencode
# **收據的四個欄位與分級**（四組，含三個負控制；約 10 秒）
bash ops/vacantrun/enclosure_20260920/run_attest.sh
```

```bash
# **一張真 agent 的 A 級收據**（pi 0.85.1；八格含三個負控制＋工具改寫探針）
bash ops/vacantrun/enclosure_20260920/run_agent_attest.sh pi \
     timing enc noenc nohook rogue mutate_ctl mutate mutate_all
```

`run_agent_attest.sh` 是 `../../../decisions/DECISION_20260920_FIRST_TIER_A_RECEIPT.md`
的可重跑版本，也是 `run_agent.sh`（真 agent 在圍牆裡）與 `run_attest.sh`
（四個欄位＋分級）**併成的一支**。⚠ 它跟 `run_attest.sh` 的差別就是全部：
**這一支沒有任何一行以事件參數執行 `hookcli`**（去掉註解之後那個 grep ＝ 0，
而同一支 grep 在 `bin/attest_inner.sh` 上 ＝ 1，那是正控制），
canary 只可能由 **pi 自己的 extension** 燒起來。
⚠ `grep -c hookcli` 本身是 4／5，全部在註解裡——**那個數字不是判準**。2026-09-20 實測
`tier="A"`／`applied=true`／`canary_fired=true`／`unexplained=0`，22 格判準全綠。
原始資料在 `evidence_agent_attest/`。

`run_attest.sh` 是 `DECISION_20260920_RECEIPT_ATTESTATION.md` 的可重跑版本：
`enclosure{ns_id, policy_sha256, applied}`／`framework_hook{…, canary_fired}`／
`reconciled{relay_calls, hook_events, unexplained}`／`tier` 四個欄位，
每一格配一個負控制（不套 enc.sh ⇒ `applied=false`；掛鉤拆掉 ⇒ `canary_fired=false`
＋降級；多一通沒有工具事件的 ⇒ `unexplained>0` ＋降級）。
收尾印 `RUN_ATTEST_DONE fail=<n>`，**fail=0 才算過**。
⚠ 它的 canary 是**直接呼叫契約**（`hookcli session_start`），
**不是**某個 agent 框架的掛鉤——兩件事不可以混講。

只有 enclosure 那一組會讓人以為「那些目標本來就關著」，所以
`run_probes.sh` **一定**先在同一台機器、同一分鐘、用同一支探針跑一次
**不套 enc.sh** 的負控制。兩組唯一的差別就是有沒有套 `enc.sh`。

環境變數：`ENC_BASE`（工作根，預設 `/var/tmp/vacant-enclosure-20260920`）、
`ENC_REPO`、`ENC_UPSTREAM`、`ENC_PY`、`ENC_CLEAN=1`（跑完刪工作根，
**只刪自己建的**，靠 `.created_by_vacant_enclosure` 標記檔認）。

收尾印 `RUN_PROBES_DONE out=<目錄> fail=<n>`，**`fail=0` 才算過**。

⚠ **vacant-dev 上不要 clone 整個 repo**（38 G 的碟、每份 clone 786 M，
memory 的「vacant-dev 磁碟陷阱」）。這套只需要兩個東西：

```bash
# 在 Mac 上
tar czf /tmp/venc_kit.tgz --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='evidence' \
    vacant_network ops/vacantrun/__init__.py ops/vacantrun/wrap_agent.sh \
    ops/vacantrun/enclosure_20260920            # 約 500 KB
scp /tmp/venc_kit.tgz user1@100.124.254.83:/var/tmp/
# 在 vacant-dev 上
rm -rf /var/tmp/venc && mkdir -p /var/tmp/venc \
  && tar xzf /var/tmp/venc_kit.tgz -C /var/tmp/venc
cd /var/tmp/venc && bash ops/vacantrun/enclosure_20260920/run_probes.sh
```

`vacant_network` 需要 `cryptography`（vacant-dev 的系統 python3 已有 41.0.7）。
收工：`rm -rf /var/tmp/venc /var/tmp/venc_kit.tgz` ＋ 工作根（或 `ENC_CLEAN=1`）。

---

## 圍牆長什麼樣

`bwrap --unshare-all --die-with-parent`
＋ 最小 rootfs（`--ro-bind /usr /etc` ＋ `/bin /sbin /lib /lib64` 符號連結）
＋ `--proc /proc --dev /dev`
＋ **私有 tmpfs** `/tmp` `/run` `/var/tmp`
＋ `--bind <工作區>`
＋ **唯一一扇門**＝主機的路徑型 unix socket `--ro-bind` 進 `/run/vacant/`。

兩條不可以弄丟的性質：

1. **netns ＋ mount ns 缺一不可。** 只有 `unshare -n` 的時候**路徑型 unix
   socket 照連**——圍牆等於沒有。門穿得過 netns 正是因為它是檔案系統物件。
2. **門的目錄是 `--ro-bind` 不是 `--bind`**（2026-09-20 改）。唯讀之下
   socket 照樣連得上，而可寫是白送出去的一個寫入點（舊版實測
   `WROTE /run/vacant`）。

---

## 門：從 byte pipe 升級成會終結 HTTP 的 Vacant proxy

早上那一版是 `bin/door_host_bytepipe.py`——**不看內容**。於是 enclosure 裡
可以對它送**任何** HTTP 請求，只要對面那台主機收。洞從「任意主機」縮小到
「那一台上游」，**縮小不是關掉**。

現在的門是 `python3 -m vacant_network.vrun.proxyd --unix <sock>`：

| 性質 | byte pipe | proxyd `--unix` |
|---|---|---|
| 終結 HTTP | ✗ | ✓ |
| 非模型 path（`GET /admin`） | **原樣隧道過去（實測 200）** | **403，一個 byte 都沒出去** |
| 逐通落盤（鐵律 3） | ✗（只有 `CONN n`） | ✓ `wire/index.jsonl` ＋ req/resp 原始位元組 |
| 持有金鑰 | — | **不持有**（`sentinel=""`，`Authorization` 原樣穿透） |

`--path-policy` 的預設**跟著聽法走**：`--unix` ⇒ `model`、`--port` ⇒ `any`
（常駐端點的既有行為一個字沒改）。名單在
`vacant_network/vrun/wireproxy.py::MODEL_PATHS`，比對是**逐段**的
（`/v1/modelsX` 擋得住，實測 403）。

⚠ **這是 path 層的閘門，不是內容層的。** 名單上的 path 之下要塞什麼 body
它不管——**擋得住 `/admin` ≠ 擋得住「把資料裝進一個合法的模型請求帶出去」**。

---

## 證據是哪一跑來的（⚠ 兩組，時間不同，不可以混講）

| 組 | 工作根 | 時間（UTC） | 產生它的腳本 |
|---|---|---|---|
| 探針（圍牆／門／寫入） | `…-20260920c` | 2026-09-20 18:16 | `run_probes.sh`，**與本目錄committed 版本逐字相同** |
| agent 兩格 | `…-20260920b` | 2026-09-20 18:13 | `run_agent.sh`，**與本目錄 committed 版本逐字相同** |

⚠ **18:16 想在同一個工作根把 codex 那格一起重跑，被擋下來了，但不是門的問題**：
另一個並行的 agent 在 18:15 於主機裝了 `/etc/codex/requirements.toml`
（帶著它自己的 `.SENTINEL_CLAUDE_DELETE_ME` 標記），codex 0.147.0 於是在
**啟動時**就退件——
`approval_policy = "never" cannot be used because requirements do not allow
sandbox_mode = "danger-full-access"`，`door_calls=0`、`agent_rc=1`。
那是 `wrap_agent.sh` 的 codex 段跟一個**臨時的主機政策**撞在一起，
跟 enclosure 與門都無關（同一支腳本在 18:11 與 18:13 各跑成功一次）。
**沒有去動別人的檔案。** 它被移除之後可以直接重跑驗證。

## 量到什麼（每一格都有負控制，全部是 2026-09-20 這一輪重跑的）

### 1. 圍牆：6 擋 1 通，兩邊 `mismatched=0`

| 目標 | 負控制（不套 enclosure） | enclosure |
|---|---|---|
| `ext_ip_upstream`（上游 IP，HTTP） | `HTTP/1.1 200 OK` | `OSError [Errno 101] Network is unreachable` |
| `ext_ip_cloudflare`（1.1.1.1:443） | connected | `[Errno 101]` |
| `loopback_own`（127.0.0.1:<自己起的>） | connected | `[Errno 111] Connection refused` |
| `unix_path_tmp`（主機 `/tmp` 的 socket） | connected | `[Errno 2] No such file or directory` |
| `unix_abstract`（抽象 socket） | connected | `[Errno 111]` |
| `dns_example` | `('104.20.23.154', 80)` | `gaierror [Errno -3]` |
| **`door_relay_sock`** | connected | **connected** |

`evidence/probe_negctl.json`、`evidence/probe_enclosure.json`。

### 2. 門講 HTTP 之後：非模型 path 被擋，`mismatched=0`（7 格）

| 格 | 門 | 請求 | got | want |
|---|---|---|---|---|
| `relay_models` | 真上游 · model | `GET /v1/models` | **200** | 200 |
| `relay_admin` | 真上游 · model | `GET /admin` | **403** | 403 |
| `echo_admin` | echo · model | `GET /admin` | **403** | 403 |
| `echo_chat` | echo · model | `POST /v1/chat/completions` | **200** | 200 |
| `echo_any_admin` | echo · **any（負控制）** | `GET /admin` | **200** | 200 |
| `echo_pipe_admin` | echo · **byte pipe（負控制）** | `GET /admin` | **200** | 200 |
| `echo_lookalike` | echo · model | `GET /v1/modelsX` | **403** | 403 |

**「沒有隧道過去」的證據不在狀態碼，在上游的收件紀錄**
（`evidence/echo_hits_*.jsonl`，上游是一台**什麼 path 都回 200** 的 echo）：

- `echo[model]` 收到 `/admin` 的次數 = **0**
- `echo[any]` = **1** ← 負控制：同一支探針、同一條 path，政策關掉就到得了
- `echo[pipe]` = **1** ← 負控制：門不終結 HTTP 就會隧道過去

### 3. 兩個 agent 在 enclosure 裡跑完一題，門的通數 > 0

| agent | rc | door_calls | by_path | solution.py |
|---|---|---|---|---|
| codex-cli 0.147.0 | 0 | **2** | `/v1/responses` ×2（都 200） | ✓ sha256 `ba1a531f…` |
| OpenCode 1.18.31 | 0 | **3** | `/v1/chat/completions` ×3（都 200） | ✓ sha256 `ba1a531f…` |

`door_calls` 讀的是**門自己的 journal**，不是 agent 的 stdout
（`evidence/agent_*.json`、`evidence/journal_agents_relay.jsonl`）。

⚠ **這裡踩到今晚第二個量具說謊，記下來**：第一次連跑兩格時 OpenCode 那格
`door_calls=0`、`SOLUTION_ABSENT`，但 **`agent_pipe_rc` 還是 0**。真因是
`run_agent.sh` 用 `[ -S socket ]` 判斷「門在不在」——前一格的 proxyd 收到
SIGTERM 之後還沒把 socket 檔 unlink，所以它判成「門已經起來了」而不起自己
那一扇。**檔案在 ≠ 門活著**。現在改成真的連一次（`door_alive()`）。

### 4. 門不持有金鑰：`Authorization` 原樣穿透、header 不上碟

- 上游收到 `Bearer ENCLOSURE-CALLER-KEY`（`evidence/echo_hits_model.jsonl`）
  ——⚠ 那是**探針自己造的字串**，不是任何真鑰；本目錄掃 `sk-ant` 等真鑰
  形狀是零命中。
- 門的 state 目錄 `grep -r 'ENCLOSURE-CALLER-KEY'` **0 命中**。
  **正控制**：同一支 grep 在同一個目錄找 `chat/completions` 命中 4 個檔
  ⇒ 不是 grep 沒讀到那些檔案。
- `evidence/door_state_*.json` 裡沒有任何 key 欄位，`path_policy` 寫在裡面。

### 5. 門目錄唯讀（正面驗，不是假設）

`evidence/write_ro.json`／`write_rw.json`。探針印的是 **errno 名字**，
因為「寫不進去」有至少五種 errno：

| 路徑 | `--ro-bind`（現在） | `ENC_DOOR_RW=1`（負控制，＝舊的 `--bind`） |
|---|---|---|
| `/run/vacant` | **EROFS** | **WROTE** |
| `/tmp`（私有 tmpfs） | WROTE（量具活著的正控制） | — |
| 工作區 | WROTE | — |
| `/usr` | EROFS | — |

⚠ 這個探針是為了修掉早上的一個量具說謊做的：用
`echo x > "$d/f" || echo READONLY` 去量，`/home/user1` 印了 `READONLY`，
真因卻是 `No such file or directory`。

---

## 檔案

```
run_probes.sh          ← 一鍵重跑：負控制 ＋ enclosure ＋ 門 ＋ 寫入，全部
run_agent.sh           ← 一個 agent 在 enclosure 裡跑完一題
bin/enc.sh                  圍牆本體（bwrap 參數；門是 --ro-bind）
bin/door_guest.py           enclosure **內**的 127.0.0.1:8787 → unix socket
                            （byte pipe，但住在圍牆裡面 ⇒ 繞不過外面那一側）
bin/door_host_bytepipe.py   **已被取代**的舊門。留著只為了當負控制
bin/probe_targets.py        圍牆探針（tcp／unix／abstract／dns／http）
bin/targets_up.py           把三個探針目標立起來
bin/echo_upstream.py        什麼 path 都回 200、**逐通記下 path** 的假上游
bin/door_http_probe.py      在 enclosure 裡對門講 HTTP，逐格對答案
bin/write_probe.py          寫入探針，印 errno 名字（EROFS ≠ ENOENT）
bin/inner.sh                enclosure 內部：拉起 door_guest 再跑 wrap_agent.sh
evidence/                   上面每一格的原始 JSON 與 log
run_agent_attest.sh    ← **真 agent 的 A 級收據**：上面兩支併成一支，八格
bin/agent_attest_inner.sh   enclosure 內部：探針 ＋ 真 agent（**零 hookcli 呼叫**）
bin/strip_hook_pi.sh        `nohook` 負控制：刪掉 extension 再 exec 真的 pi
evidence_agent_attest/      A 級那一輪的原始 JSON／掛鉤日誌／門的 journal
```

⚠ **`evidence/` 只有索引與 log，沒有原始 bytes。** `*.req.bin`／`*.resp.bin`
（agent 那兩格加起來約 300 KB）留在 vacant-dev 的工作根，收工時刪了；
`journal_*.jsonl` 是門的**索引**，body 不進 repo。要原始 bytes 就重跑。

## 相關

- 門的實作：`vacant_network/vrun/proxyd.py`（`--unix`／`--path-policy`）、
  `vacant_network/vrun/wireproxy.py`（`_ThreadingUnixHTTPServer`、
  `MODEL_PATHS`／`is_model_path`、`_refuse_nonmodel_path`）
- 可執行的性質守門：`tests/test_vrun_unix_door.py`（9 格，每格配負控制）
- bwrap 在這台機器上的前提：`ops/gain/r530/SANDBOX.md`、
  `vacant_network/vrun/sandbox.py` 的模組 docstring
- 圍牆外面的那條線（`vacant install` ＋ 常駐 proxy）：
  `ops/vacantrun/possess_linux_20260920/`
