# DECISION 2026-09-19 — 1.0.0 的兩道門檻：收據分得出假中介、上游不准安靜出網

**裁決依據**：Fable 5.1（等同人類的回答）。兩道都「現在就能做、不被任何決定擋住」。
**基底**：`integrate/20260919`。**未 push、未動 `main`、未用 worktree。**
**口徑**：全文用「可究責性／讓依賴有根據」，不用「信任」。

---

## 〇、先講撞車：改名那條線在同一棵工作樹上落地了

回報時我判斷「不會撞」——**那個判斷是錯的，而且錯在我只查了版控沒查工作樹**。
當時 `git branch -a` 掃過每一條分支的 tree，沒有任何一條有 `vacant_network/`
目錄，所以我判定改名還沒開始。實際上改名那條線**不是在另一條分支上做**，
它就在**這一棵工作樹**裡做 `git mv vacant/ → vacant_network/`（未提交），
在我編輯到一半的時候落地。

**結果是沒事，而且是運氣加結構兩半**：

- `git mv` 搬的是**檔案**，我改的是**內容** ⇒ 我在 `vacant/vrun/*.py` 上的
  編輯原封不動被搬進 `vacant_network/vrun/*.py`，一個 byte 沒丟。
- 對方的掃描是 `vacant.` → `vacant_network.` 的路徑改寫，跟我的內容改動**正交**，
  兩邊各自落在同一個檔案裡而沒有互相覆蓋（實測：我在 docstring 裡寫的
  `` `vacant/vrun/verify_receipts.py` `` 也被對方順手改成 `vacant_network/…`）。
- 唯一要我自己收的是**新增**的兩個測試檔（untracked ⇒ 對方的掃描掃不到），
  import 由我改成 `vacant_network`。

**留給下一個人的教訓（這一條比兩道門檻本身更容易再犯）**：
「會不會撞」不能只問 `git branch`。大規模改名**多半不在分支上做**，因為做的人
要一次跑完整棵樹的 sed。要判有沒有在跑，看的是 `git status --porcelain | grep '^R'`
與工作樹上的目錄名，而且**要在開工前與收工前各看一次**——我只看了開工前那一次。

---

## 一、門檻二：`verify_receipts` 要能分出「零請求的假拒交格」

### 1-1 問題（repo 裡有落盤證據，不是推論）

`runs/v1_five_agent_matrix_20260919/controls.sh` 把 `/bin/true` 和一行 `cp`
放在 agent 的位置，**一通模型都不打**：

```
ctl_norequest_refuse    exit 20   accepted=false  visible_fail   rs=0  wire={}  rc=0  chain_ok=true
ctl_norequest_deliver   exit 0    accepted=true   visible_pass   rs=0  wire={}  rc=0  chain_ok=true
```

而那一批的驗章結果逐字留在
`runs/v1_five_agent_matrix_20260919/controls_receipts_verify.txt`：

```
run 2　鏈 2　entries 4　驗過 4　失敗 0　壞鏈 0
...
總判：OK
```

⇒ **退出碼、`accepted`、`stop_reason`、`agent_rc`、`chain_ok` 五個欄位在零通
模型呼叫下全部成立，而驗章器的總判是乾淨的 `OK`。**
唯一分得出來的是 `requests_seen` 與 `wire_by_protocol`，而
`verify_receipts.py` 當時 **grep 不到 `requests_seen`**。

### 1-2 為什麼不把 `chain_ok` 改成 `false`

**鏈確實是完整的。** 那兩格的每一筆簽章都驗得過、seq 連續、prev_hash 串得上、
條數對得上 rows。把它說成壞掉，是用一個假的技術事實去修一個真的認識論問題
——**那是另一種說謊**，而且它會讓「鏈壞了」與「這一跑沒有中介」在 CI 上同形。

所以**新增一個正交的維度**，讓「鏈完整」與「中介發生過」分開講：

| 欄位 | 值 | 意思 |
|---|---|---|
| `chain_ok` | `true`／`false` | **語意一個字都沒改** |
| `mediated` | `true` | 每一格 `requests_seen > 0` |
| | `false` | **有格子是 0** ⇒ 那一格沒有中介發生過 |
| | `null` | **這條鏈沒記這件事**（舊鏈）⇒ 沒量到，不是量到 0 |
| `void_reason` | `"no_requests_seen"`／`null` | `mediated is False` 時說出是哪一種 |

總判從三值變四值，**退出碼也分開**（VOID 不與 BROKEN 同形）：

| verdict | exit | 意思 |
|---|---|---|
| `OK` | 0 | 鏈完整 ＋ 每格都有流量 |
| **`VOID`** | **3** | **鏈完整，但有格子零請求** |
| `BROKEN` | 1 | 鏈壞了（簽章／seq／prev_hash／對帳） |
| `UNVERIFIABLE` | 1 | 沒公鑰／空鏈／glob 零筆命中 |

優先序 `BROKEN > VOID`：兩者同時成立時判 BROKEN（鏈壞了比較嚴重），
但 `mediated` 照樣落盤——**兩個維度不准互相吃掉**（selftest K）。

`broken_chains_n` 這一欄**刻意不把 VOID 算進去**：它的語意是「鏈壞了」，
而 VOID 的鏈沒壞。已歸檔資料的這一欄因此一個數字都沒變。

### 1-3 負控制：`--selftest` 多了四條

舊的 selftest（A–G）只證明「抓得到**壞鏈**」，而這一次量到的那件事**鏈根本沒壞**。
新增：

| 代號 | 造什麼 | 要求 |
|---|---|---|
| **H** | `ctl_norequest_refuse` 的逐欄複製（exit 20／accepted=false／visible_fail／agent_rc=0／`requests_seen=0`） | `verdict == "VOID"`、`void_reason == "no_requests_seen"`、指得出是哪個 task_id |
| **H2** | 同上 | **`chain_ok is True`、`failures == []`** ——VOID 不准把鏈說成壞的 |
| **H3** | 同上，走 `run_glob` | **總判 `VOID`**、`broken_chains_n == 0`、`exit_code == 3` |
| **I** | `--allow-no-suite` 的形狀（`accepted_is_null=true`、`stop_reason="ungated"`）**但 `requests_seen=3`** | `verdict == "OK"` ——**不准誤殺** |
| **J** | 舊鏈：payload 裡**沒有** `requests_seen` 欄位 | `verdict == "OK"`、`mediated is None`、`requests_seen_total is None` |
| **K** | 壞鏈 ＋ 零請求同時成立 | `BROKEN` 優先，但 `mediated` 照樣講得出來 |

**對負控制的負控制**：`tests/test_vrun_receipt_mediation.py::test_selftest_carries_the_negative_control`
把 `mediation_of` 整個打成「永遠是 True」，然後要求 `selftest()` **回 1**。
沒有這一條，H／I／J 有可能只是恆真式。

### 1-4 `--allow-no-suite` 為什麼不會被誤殺

兩個維度**正交**，判斷各問各的：

- `--allow-no-suite` 的指紋是 `accepted_is_null == true` 或
  `stop_reason ∈ {no_suite, ungated}`。那一格明講「**這一次不量驗收**」。
- 零請求的指紋是 `requests_seen == 0`。那一格說的是「**這一次沒有中介**」。

一個 ungated 而且模型通道有流量的跑 ⇒ `OK`，並且 `ungated_task_ids` 把它列出來。
可執行證明：selftest I ＋ `test_allow_no_suite_with_traffic_is_not_killed`
（後者是真的跑一次 `launcher.run(allow_no_suite=True)`，不是造資料）。

### 1-5 驗給你看（repo 裡的真資料，不是測試造的）

```
$ python3 -m vacant_network.vrun.verify_receipts --glob 'runs/v1_five_agent_matrix_20260919/controls/*'
中介：有 0　**零請求 2**　沒記這件事 0
ctl_norequest_deliver   RUN-ON   2  2  0   1  1  b286cb63…  VOID
ctl_norequest_refuse    RUN-ON   2  2  0   1  1  90d6a2f3…  VOID
總判：VOID

$ python3 -m vacant_network.vrun.verify_receipts --glob 'runs/v1_five_agent_matrix_20260919/cells/*'
run 20　鏈 20　entries 40　驗過 40　失敗 0　壞鏈 0
中介：有 20　**零請求 0**　沒記這件事 0
總判：OK
```

**同一批、同一把尺、同一天的資料**：兩個假格子翻成 VOID，20 個真格子不動。

---

## 二、門檻三：沒指定的 upstream 不准安靜落到公開 API

### 2-0 選 (b)：指到一個會拒絕的本機 sink。**理由**

**(a) 拒絕啟動的致命缺點是：它用一個沒量到的東西判一個罪。**

`upstreams_defaulted` 說的是「**這條路由沒人指定**」，
它**不等於**「這一跑會用到這條路」——這個區別 `docs/AGENT_COMPAT.md` §10.6
已經釘死過一次了。實例就在手上：

- **pi 的 40 格**每一格 `upstreams_defaulted: ['anthropic']`，而那條路
  **一通流量都沒有**。照 (a)，這 40 格全部拒絕啟動。
- **Codex 那一跑**同樣列著 `anthropic` 而 `wire_by_protocol` 裡根本沒有 anthropic。

⇒ (a) 會把一批**行為上完全乾淨**的跑整批擋掉，而且擋的理由是一個預測不是一個量測。
那與鐵律 3（「沒量到」≠「量到 0」）同一條紀律的反面。

**(b) 的性質剛好相反，三種情況各自最小驚訝**：

| 情況 | (b) 的行為 |
|---|---|
| 那條路**沒有流量** | **逐位元不變**（pi 的 40 格、Codex 那一跑） |
| 那條路**有流量** | **當場死在本機**，502 ＋ 一段講得出「要設哪個變數」的 JSON，原文落盤 |
| **兩條上游都釘死** | 完全不受影響（五 agent 矩陣 20 格、`controls.sh`） |

**沒有選「印個警告然後照樣走」**——那就是 `9eeb1d9e` 之後的狀態，而它沒用：
看得見沒有擋住任何東西。

### 2-1 怎麼做的

- `envmap.SINK_UPSTREAM = "http://unspecified-upstream.vacant.invalid"`。
  `.invalid` 是 **RFC 2606 保留 TLD**，**保證解析不出來** ⇒ 就算哪天有人繞過
  `wireproxy` 的檢查拿這個字串去連，結果是**連不上**而不是**連到別人家**。
  （這是 `envmap` 誠實邊界 2 那句「漏掉的路要連不上，不是偷偷連上」的同一條。）
- `wireproxy._handle_inner()` 在**組 header 之前**就判 `envmap.is_sink(base)`：
  不組 header（真鑰連碰都沒碰）、**不開 socket、不解析 DNS**，直接回 502。
  請求本體仍然逐位元落盤、仍然算進 `requests_seen`——**被擋下來也是發生過的事**。
- `describe_upstreams()` 多一個 `fallback` 欄位：`None`／`"sink"`／`"public"`。
  **`source` 的形狀凍結**（仍然只有 `env:<VAR>` 與 `default`），因為 README ×3 與
  既有測試引著它；新的事實寫在新欄位裡，不改舊欄位的語意。
- 逐跑落盤：`upstreams`（含 `fallback`）、`upstreams_defaulted`（**語意沒動**）、
  `upstreams_sinked`、`upstreams_public_allowed`、`wire_blocked`。
- **逃生口（兩個入口，都必須明講）**：
  `vacant run --allow-public-upstream`，或 `VACANT_RUN_ALLOW_PUBLIC_UPSTREAM=1`
  （給 `ops/gain/r5xx/*_queue.sh` 那種改不動 argv 的 wrapper）。
  空字串／`0`／`no` 都不算明講。

### 2-2 負控制：**先證明修改前真的會落到公開 API**

不送任何 bytes，只看解析結果（`describe_upstreams` 是純函式）。
`scratchpad/negctl_before.txt` 逐字留檔，在 `eb655a38` 上跑的：

```
### 只指定 anthropic（Claude Code 的實況）
  anthropic  -> http://100.86.226.21:1234       source=env:VACANT_RUN_UPSTREAM_ANTHROPIC
  openai     -> https://api.openai.com/v1       source=default defaulted=True

 route('/api/hello') = openai
 join_upstream -> https://api.openai.com/api/hello        ← 真的出網的那一通
```

修改後，同一個情境：

```
### 只指定 anthropic（Claude Code 的實況）
  anthropic  -> http://100.86.226.21:1234                  fallback=None
  openai     -> http://unspecified-upstream.vacant.invalid fallback=sink

### 五 agent 矩陣：兩條都釘死
  anthropic  -> http://100.86.226.21:1234                  fallback=None
  openai     -> http://100.86.226.21:1234/v1               fallback=None   ← 完全不受影響

### 逃生口（明講之後）
  openai     -> https://api.openai.com/v1                  fallback=public ← 路還在
```

**那條負控制被做成了永久測試**
（`test_negative_control_the_road_to_the_public_api_is_still_there`），
理由寫在它的 docstring 裡：**沒有它，「擋住了」就沒有對照**——一個永遠解析不到
公開 API 的系統，與一個被擋住的系統，在只驗後者的測試底下長得一模一樣。

### 2-3 「沒開連線」怎麼證

`tests/test_vrun_fail_closed_upstream.py::test_sink_refuses_in_process_without_opening_a_connection`
斷言 `index.jsonl` 那一列的 `error == "unspecified_upstream_sink"`，並且
**`"gaierror" not in error`**。真的去連 `.invalid` 會拿到 `gaierror` 的 repr
——拿到我們自己的字串，就代表那一步根本沒走到。
另外斷言假上游的 `seen == []`（沒有任何伺服器收到東西）。

---

## 三、⚠ 已歸檔資料的可比性（**這一節是這份裁決的重點，不是附註**）

### 3-1 不會變的：6,468 筆（99.7%）

`runs/` 底下所有 verdict 收據共 **6,962 筆**，其中 **6,468 筆 payload 裡
根本沒有 `requests_seen` 這個欄位**：

| 型別 | 有欄位 | 沒有欄位 |
|---|---:|---:|
| `conform_verdict`（R445／R460R／R529…） | 0 | 2,581 |
| `harness_verdict`（R460／R460R…） | 0 | 3,711 |
| `ws_verdict`（R530 ＋ `vacant run`） | 494 | 176 |

**沒有欄位 ⇒ `mediated = null` ⇒ 判 `OK`。** 這是刻意的：把它們判成 VOID
等於把一句它們沒說過的話塞進已歸檔的資料裡（鐵律 3）。
實測確認：`--glob 'runs/g_r460r1_*'` 仍然是 `總判：OK`、`失敗 0`、`壞鏈 0`，
`broken_chains_n` 一個數字都沒變。

### 3-2 **會變的：20 格，從 OK 變 VOID**

| 位置 | 格數 | 這是什麼 | 判 VOID 對不對 |
|---|---:|---|---|
| `runs/v1_five_agent_matrix_20260919/controls/` | 2 | **就是那兩個負控制本身**（`/bin/true`、一行 `cp`） | **對，這正是要抓的東西** |
| `runs/twin_fixture_20260919/runs/` | 18 | 展件替身的**離線 fixture 跑**（不打模型） | **對**，但要跟著改口徑（見下） |

⚠ **`runs/twin_fixture_20260919` 那 18 格要跟著改口徑**：它們是
**fixture**（離線、零模型），引用它們時本來就不可以說「這是 Vacant 中介到的證據」。
驗章器現在會替我們把這句話講出來。**它們不是壞資料，是被標對了類別的資料。**
`runs/twin_real_20260919`（真模型）不受影響，仍然是 `OK`。

⚠ **`runs/v1_five_agent_matrix_20260919/controls_receipts_verify.txt` 這個落盤檔
沒有重跑覆蓋**——那份檔案是 2026-09-19 當天的**歷史紀錄**，它記的是
「當天那把尺說了什麼」。改寫它等於讓紀錄描述一件沒發生過的事
（同 `CLAUDE.md` 對預註冊檔逐塊指令的處理方式）。新的結果在本檔 §1-5。

### 3-3 `vacant demo gate` 的總判從 `OK` 變 `VOID`，而那是**故意的**

demo 那隻假 agent 一通模型都沒打 ⇒ 它**就是**假拒交格的形狀，
與 `ctl_norequest_refuse` 在收據上只差 task_id。所以：

- `_assert_not_a_performance()` 現在**釘死 `VOID`**：判回 `OK` 要當場死掉
  （代表尺分不出零請求的格子），判 `BROKEN` 也要死掉（代表鏈真的壞了）。
- 畫面上多印四行，講出為什麼是 VOID、以及換成真 agent 會是 OK。
- **demo 拿自己當那條負控制**：連第一幕都被自己的尺判成「這不是中介的證據」，
  那把尺才值得相信。

### 3-4 行為改變一覽（給重跑既有腳本的人）

| 改動 | 誰會感覺到 | 誰不會 |
|---|---|---|
| 零請求 ⇒ VOID、exit 3 | 驗 fixture／負控制批次的腳本（本來吃 `rc == 0`） | 真跑（`cells/*` 20 格全 OK） |
| 沒指定的 wire ⇒ sink | 只釘一條上游**而且**那條路真的有流量的跑 | 兩條都釘死的、那條路沒流量的 |
| `--allow-public-upstream` | 需要公開 API 的人要多打一個旗標 | 本地模型的人 |

---

## 四、**擋不住什麼**（每一條都寫進了 docstring，改碼請保留）

1. **門檻二擋得住「完全沒打」，擋不住「打了但打到別的地方」。**
   `requests_seen > 0` 只代表有 bytes 經過本機的 proxy，**不代表那些 bytes 去了
   你以為的那台機器**。要判那件事得看 `run_<ARM>.json` 的 `wire_by_protocol`
   與 `upstreams`（含 `wire_*/index.jsonl` 的 `upstream` 欄位），而
   **那些欄位不在簽章鏈上** ⇒ 驗章器對它們一個字都說不出來。
   **把上游欄位也簽進收據是下一個動作，這次沒做。**
2. **門檻二也擋不住「打了幾通但都是非模型流量」。** `requests_seen` 把外掛清單、
   遙測、`/v1/models` 探測都算進去（`docs/VACANT_RUN.md` §4 已經有這條：
   某一格假上游收到 16 通而**沒有一通是模型請求**）。
   ⇒ `mediated: true` 的正確讀法是「**proxy 上有流量**」，不是「**模型被問了**」。
3. **門檻三擋的是「沒人指定的那條路由」，不是「出網」。**
   使用者自己把上游指到公開 API 照樣放行（那是明講的，本來就該放行）；
   agent 繞過 proxy 直連照樣擋不住（`vacant_network/controller.py:7-8` 的同一條
   邊界）。**結構性補法仍然是 `block_egress.sh`（V3）**，那一條沒有被這次取代。
4. **門檻三擋不住 `envmap` 名單漏一個變數。** Hermes 漏設 `CUSTOM_BASE_URL`
   那個活體標本（`AGENT_COMPAT.md` §12.2 對照 C）走的是**框架自己編死的**
   `https://openrouter.ai/api/v1`——那條路根本沒經過 `vacant run` 的上游解析，
   sink 在那裡不存在。
5. **`route()` 按 path 猜家族這件事本身沒修。** Claude Code 的 `/api/hello`
   仍然被判成 openai wire；改的只是「那條 wire 沒人指定時落到哪」。
6. **`mediated: null` 不是「安全」，是「不知道」。** 6,468 筆舊資料在這個維度上
   **什麼都沒被驗證**。它們判 OK 的唯一理由是「不准把沒說過的話塞進去」，
   不是「它們通過了」。

---

## 五、還不能說的話

- ❌ 「`vacant run` 不會出網。」→ 只能說「**沒人指定的那條路由**現在不會靜靜出網」。
  使用者指定的上游、agent 繞過 proxy、框架編死的預設，三條路都還在。
- ❌ 「收據能證明 agent 真的被 Vacant 中介了。」→ 只能說「收據現在**分得出**
  『一通都沒打』這一種假格子」。打了但打到別的地方，收據仍然說不出來。
- ❌ 「已歸檔的 98 個 real_run 的中介性被驗證了。」→ **6,468 筆舊 verdict 在這個
  維度上是 `null`＝沒量到。** 要回頭驗它們得重跑，而那不在這次範圍內。
- ❌ 「`mediated: true` ＝ 模型被問了。」→ 它只說 proxy 上有流量（見 §四-2）。
- ❌ 「1.0.0 的門檻清光了。」→ 這次做的是 Fable 5.1 的門檻二與門檻三。
  其餘門檻（尤其把 `upstream` 簽進收據、`block_egress.sh` V3）**沒動**。
- ⚠ **這兩道都只在 macOS 這一台跑過測試**（Python 3.12.10）。
  `vacant-dev`／1003／1004 上**沒有重跑**，展場那台 Linux VM 也沒有。

---

## 六、落地清單

**碼**（都在 `vacant_network/vrun/`，跟著改名那條線一起走）
- `verify_receipts.py` — `mediation_of()`、`mediated`／`void_reason`、四值總判、
  `exit_code()`（0／3／1）、`render()` 多印零請求那一行、selftest H/H2/H3/I/J/K
- `envmap.py` — `SINK_UPSTREAM`／`is_sink()`／`ALLOW_PUBLIC_VAR`／
  `public_upstream_allowed()`、`describe_upstreams(..., allow_public=)` ＋ `fallback` 欄位
- `wireproxy.py` — `_refuse_unspecified()`、`stats["blocked"]`、
  `_finish()`（索引＋統計抽成一份，sink 與轉送共用）
- `launcher.py` — `allow_public_upstream=`、`--allow-public-upstream`、
  `upstreams_sinked`／`upstreams_public_allowed`／`wire_blocked`、被擋時的 stderr 一行
- `demo.py` — 釘死 VOID ＋ 畫面上四行說明

**測試**
- 新增 `tests/test_vrun_receipt_mediation.py`（7 條，含交付格／拒交格兩種負控制）
- 新增 `tests/test_vrun_fail_closed_upstream.py`（4 條，含「路還在」的負控制）
- 改 `tests/test_vrun_upstream_provenance.py`（原本那條斷言 `api.openai.com` 的
  測試自己寫著「預設值變了…這條測試的前提要跟著改」——改了，並拆成正反兩組）
- 改 `tests/test_demo_gate.py`（VOID ＋ 多一條「尺判回 OK 也要死」的負控制）

**文件**
- `docs/VACANT_RUN.md` — 四值總判表、sink 與逃生口、兩條誠實邊界
- `README.md`／`README.en.md`／`README.ja.md` 誠實邊界 22 — 那個洞補了，
  但**補的是哪一半**要講清楚
- `.claude/commands/goal.md` — `block_egress.sh` 現在守的是**另一個**洞
