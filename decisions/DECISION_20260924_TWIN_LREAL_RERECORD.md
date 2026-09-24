# DECISION 2026-09-24（四）— 54 格 L-real 重錄：這次有錄影，也有配對收據

資料：`runs/twin_lreal_20260924`（54 格 × 兩臂＝108 次 `vacant run`，19 MB）
錄影：`ops/exhibit/twin/recordings/lreal_20260924.jsonl`（1380 行，510 KB）
配對收據：`ops/exhibit/twin/recordings/lreal_20260924.pack.json`（54 格，639 KB，綁錄影 sha256 `bf0ff8dadd37…`＋逐格鏈頭）

前情：[DECISION_20260919_TWIN_REAL_RUN.md](DECISION_20260919_TWIN_REAL_RUN.md)（上一次 54 格真跑）。
那一批是在 lifecycle 事件流出現**之前**跑的，只有 run 目錄、沒有錄影；
人類裁決**不准**寫「舊 run 目錄 → lifecycle」的轉換器（那等於把事後推導留下來）。
⇒ 本輪用新的 main（`0631ce04`）把同一批 54 格**重跑一次**，這次帶 `--events`，
錄影是**跑的當下**寫出來的，不是事後從 run 目錄推的。

⚠ **這不是 09-19 那一批的錄影。** 它是另一次執行、另一組模型輸出。
09-19 的數字與本批的數字各自成立，下面逐項對照；展場引用哪一批就寫哪一批。

---

## 一、參數：逐項對照 09-19

09-19 的發射腳本還留在 vacant-dev（`/var/tmp/vacant_twinreal/{env,batch,batch2,smoke}.sh`），
本輪照抄，**唯一新增**是每條流一個 `--events` 檔。腳本、log、1004 狀態紀錄全部落在
`runs/twin_lreal_20260924/launch/`。

| 項 | 09-19 | 本輪 | 同？ |
|---|---|---|---|
| 居民 | DUL-89／KAL-52／LIV-51（`roster.default_roster()[:3]`） | 同（實測順序 KAL-52, DUL-89, LIV-51） | ✓ |
| 題目 | 9 題，分兩批：第一批 `s1_01_addmul,s1_12_hms,s1_31_money`；第二批 `s1_05_initials,s1_24_is_pal,s1_30_ord_suffix,s1_32_pct,s1_34_days_in,s1_49_rgb` | 同，同樣分兩批、同樣的題序 | ✓ |
| 題面 | 扣住（`TASK.md`）／寫明（`TASK_explicit.md`） | 同 | ✓ |
| ON 臂 | `--retry revise --max-attempts 3` | 同 | ✓ |
| OFF 臂 | `vacant_on=False`（純 tee） | 同 | ✓ |
| `--timeout` | 300 | 300 | ✓ |
| `--test-timeout` | 預設 30（腳本沒給） | 預設 30（腳本沒給） | ✓ |
| `--sandbox` | auto → `bwrap`（ON 54/54） | auto → `bwrap`（ON 54/54） | ✓ |
| `--feedback-into` | `file` | `file`（108/108） | ✓ |
| 並行 | 四條流 `--shard K:4`，一批跑完再下一批 | 同 | ✓ |
| agent | pi **0.85.1**，`ops/vacantrun/wrap_agent.sh pi "{TASK}"`，node v22.23.2 | 同一個 pi 執行檔（`/home/user1/.local/opt/node-v22.23.2-linux-x64/bin/pi`，`--version`＝0.85.1） | ✓ |
| 後端 | 1004＝`100.86.226.21:1234`，LM Studio **0.4.17**，`gemma-4-12b-it-qat`，parallel 4 | 開跑前實測：`LM Studio.exe` ProductVersion **0.4.17.0**；`lms ps`＝`gemma-4-12b-it-qat`、context 262144、**parallel 4**、**TTL 空白**（手動載入，不會 JIT 到期卸載） | ✓ |
| 非 thinking | 635 份回應 `reasoning_content` 0 筆 | 開跑前探針（`Reply with exactly: OK`）`reasoning_content: ""`；全批掃描見 §三 | ✓ |
| 執行端 | vacant-dev（Ubuntu，8 核） | 同 | ✓ |
| `--events` | **沒有**（當時還不存在） | 每條流一份：`lifecycle/b{1,2}_s{0..3}.jsonl` | **新增**（本輪的目的） |
| 程式版本 | 09-19 的工作樹（套件還叫 `vacant/`） | **main `0631ce04`**（`vacant_network/`、含 lifecycle、錄影重播、配對收據、09-20 的收據認證） | **不同**，見下 |

### 程式版本不同帶來的兩個可見差異（都不改變裁決）

1. **收據鏈上多了認證欄位，而本批每一格都是 `tier=C`（未認證）。**
   09-20 起 `attest.py` 會把 `enclosure`／`framework_hook`／`reconciled`／`tier` 簽進 `ws_verdict`。
   本批在 vacant-dev 上跑：沒有 netns 圍牆（看得到 `ens33`／`tailscale0`）、pi 沒裝框架掛鉤
   ⇒ **54 格全部 `tier=C`**。`VACANT_ATTEST` 用的是預設 `warn`，所以收據照發、裁決不受影響
   （`verify_receipts` 總判 OK，另外逐格印「未認證 tier=C」）。09-19 的鏈沒有這個欄位（`tier=null`＝沒量到）。
   ⇒ **展場不可以把這一批講成 A 級。** 它證明的是「每一格的模型通道經過 Vacant、閘門當場判了、
   判決簽了章」，**不**證明「那一跑沒有別的路」。
2. **收據鏈 entry 數**：170（09-19 是 168）。差的 2 筆來自多出來的那一格三次嘗試
   （見 §二 `KAL-52__s1_30_ord_suffix__pc`），不是格式變了。

### 冒煙

正式發射前照 09-19 的 `smoke.sh` 跑了 1 位居民 × `s1_01_addmul`（2 格，落在 vacant-dev
`/var/tmp/vacant_lreal_20260924/smoke/`，**不在本批裡**）：`validate_stream` 0 問題、
`serve_twin.py --check` 過、lifecycle 裡沒有暫存目錄路徑、12 份回應 `reasoning_content` 0 筆。

---

## 二、結果：與 09-19 逐格對照

### 牆鐘與通數

| | 09-19 | 本輪 |
|---|---|---|
| 第一批（18 格） | 9m05s | **8m04s**（08:04:25Z → 08:12:29Z） |
| 第二批（36 格） | 73m43s | **92m09s**（08:12:29Z → 09:44:38Z） |
| 合計 | 約 83 分 | **約 100 分** |
| 模型呼叫（`requests_seen` 加總） | 630（ON 424／OFF 206） | **646（ON 478／OFF 168）** |
| 錄影裡的 `model_call` 事件 | —（沒有錄影） | **646**（ON 478／OFF 168，與 `requests_seen` 逐一相等） |
| `wire_*/*.resp.bin` 檔數 | 635 | 653（其中 1 份 0 位元組＝被 300 秒砍掉時還在傳的那一通） |
| 逐通延遲中位數／p90 | 10.4 s／33.2 s | 11.8 s／44.9 s |
| 完成 token 速率中位數 | 11.3 tok/s | 10.0 tok/s |
| HTTP 狀態 | 200×625、0×10（全是被砍時的 BrokenPipe） | 200×636、0×16（同上，全是被砍時的 BrokenPipe） |

第二批慢了 18 分，主要是**逾時變多**（下面）：一次被砍的嘗試固定吃掉 300 秒。
1004 在整段期間（每 60 秒輪詢一次，99 筆）**始終是 `gemma-4-12b-it-qat=loaded`**，沒有卸載、
沒有別的模型被載入；wire 上沒有任何 4xx／5xx。⇒ **不是 JIT 卸載造成的假逾時**。
⚠ 有沒有**別的客戶端直連 1004** 分走槽位，本輪**沒有量**（只量了載入狀態；
hub 8766 的 `/api/requests` 在收官時是 0 筆，但它只看得到經 hub 的流量）。

### 扣住／寫明：逐題（每格是 3 位居民的合計）

```
題目                 扣住介面（held）                    寫明介面（pc）
                     09-19            本輪               09-19            本輪
                     收/拒｜OFF過     收/拒｜OFF過        收/拒｜OFF過     收/拒｜OFF過
s1_01_addmul         0/3 ｜ 0/3      0/3 ｜ 0/3          3/0 ｜ 3/3      3/0 ｜ 3/3
s1_05_initials       0/3 ｜ 0/3      0/3 ｜ 0/3          3/0 ｜ 3/3      3/0 ｜ 3/3
s1_12_hms            0/3 ｜ 0/3      0/3 ｜ 0/3          3/0 ｜ 3/3      3/0 ｜ 3/3
s1_24_is_pal         0/3 ｜ 0/3      0/3 ｜ 0/3          3/0 ｜ 3/3      3/0 ｜ 3/3
s1_30_ord_suffix     0/3 ｜ 0/3      0/3 ｜ 0/3          3/0 ｜ 3/3      3/0 ｜ 3/3
s1_31_money          0/3 ｜ 0/3      0/3 ｜ 0/3          3/0 ｜ 3/3      3/0 ｜ 3/3
s1_32_pct            0/3 ｜ 0/3      0/3 ｜ 0/3          0/3 ｜ 0/3      0/3 ｜ 0/3
s1_34_days_in        0/3 ｜ 0/3      0/3 ｜ 0/3          3/0 ｜ 3/3      3/0 ｜ 3/3
s1_49_rgb            0/3 ｜ 0/3      0/3 ｜ 0/3          3/0 ｜ 3/3      3/0 ｜ 3/3
```

**逐格的最終結果（ON 收下／拒交、`stop_reason`、OFF 事後稽核）與 09-19 54/54 完全相同。**
差別只在「花了幾次嘗試」與「有沒有被 300 秒砍」，下表。

### 總表

| | 09-19 | 本輪 |
|---|---|---|
| 扣住 n=27：ON 收下／拒交 | 0／27 | **0／27** |
| 扣住：OFF 事後稽核過 | 0 | **0** |
| 寫明 n=27：ON 收下／拒交 | 24／3 | **24／3** |
| 寫明：OFF 事後稽核過 | 24 | **24** |
| ON 收下 ＝ OFF 事後過（逐格） | 54/54 | **54/54** |
| `stop_reason` | `attempts_exhausted` 30、`visible_pass` 24 | **同** |
| 進迴圈（ON 用了 >1 次嘗試） | 30（扣住 27＋寫明 3） | **31**（扣住 27＋寫明 **4**） |
| 迴圈救回（>1 次嘗試而最後收下） | **0** | **1**（`KAL-52__s1_30_ord_suffix__pc`，見下） |
| ON 嘗試次數分佈 | 1 次 24、3 次 30 | 1 次 **23**、3 次 **31** |
| 有任何一次被 300 秒砍的格 | 3 | **7** |
| 被砍的 ON 嘗試／OFF 格 | 8／2 | **13／4** |
| 證據等級（逐格推導） | ON L-real 54/54、OFF L-real 54/54 | **ON L-real 54/54、OFF L-real 54/54** |
| `infra_void` | 0 | **0** |
| 兩臂起點逐位元相同 | 54/54 | **54/54** |
| `postaudit_RUN-OFF.json` 在不在 | 54/54 | **54/54** |
| OFF 的 `accepted` 不是 null | 0 | **0** |
| 三位居民結果完全相同的題（兩種題面都算） | 8/9 | **8/9**（例外是 `s1_30_ord_suffix` 寫明，KAL-52 那格三次嘗試） |

### 唯一一格「迴圈救回」：`KAL-52__s1_30_ord_suffix__pc`

| 嘗試 | stop_reason | agent_rc | 被砍？ | 牆鐘 | 通數 |
|---|---|---|---|---|---|
| 1 | `visible_fail` | −9 | **是** | 300.0 s | 9 |
| 2 | `visible_fail` | −9 | **是** | 300.0 s | 6 |
| 3 | `visible_pass` | 0 | 否 | 211.0 s | 4 |

OFF 那一臂：一次跑完（74 s、4 通、沒被砍），事後稽核**過**。09-19 同一格 ON 一次就過。

⇒ 這一格**不能**講成「回饋讓它做對了」：前兩次沒有自己跑完，是**我們的 300 秒上限**把它停下來的；
第三次它在時限內交出能過的東西。沒有這一層的那一臂一次就交出能過的東西。
兩臂的最終交付正確與否仍然一致（都過）。**本批「迴圈救回」的 1 格，是「被砍兩次之後第三次沒被砍」**，
不是「看了失敗原文之後改對」——我們沒有證據說它讀了 `VACANT_FEEDBACK.md`（R535 量過檔案管道在 wire 上零命中）。

### 逾時：比 09-19 多，而且不集中在同一題

| 格 | 09-19（ON 每次被砍？／OFF 被砍？） | 本輪 |
|---|---|---|
| `DUL-89__s1_30_ord_suffix__held` | [是,是,是]／是 | [是,是,是]／是 |
| `KAL-52__s1_30_ord_suffix__held` | [是,是,是]／是 | [是,是,是]／是 |
| `LIV-51__s1_30_ord_suffix__held` | [是,是,否]／否 | [是,否,是]／否 |
| `KAL-52__s1_30_ord_suffix__pc` | [否]／否 | **[是,是,否]／否** |
| `LIV-51__s1_24_is_pal__held` | [否,否,否]／否 | **[是,否,否]／是** |
| `LIV-51__s1_32_pct__held` | [否,否,否]／否 | **[否,否,是]／是** |
| `LIV-51__s1_49_rgb__held` | [否,否,否]／否 | **[是,否,否]／否** |

- 30 格拒交裡，**6 格**至少有一次嘗試被砍；其中 **4 格的最後一次嘗試就是被砍的那次**
  （`DUL-89`／`KAL-52`／`LIV-51` 的 `s1_30_ord_suffix__held`，以及 `LIV-51__s1_32_pct__held`）。
  那 4 格的「拒交」有一部分是**我們沒等它**，展場必須標出來（`any_attempt_timed_out`／`draft_done.timed_out` 在資料上）。
- 被砍時還在傳的那一通，wire 上是 `BrokenPipeError`（status 0）；上游那一通有的跑到 1629 秒才結束
  （09-19 最長 1506 秒）。**為什麼會有這麼長的一次生成，本輪沒有分析，不替它編原因。**
- 這些逾時與 09-19 是**同一個條件**（`--timeout 300`、模型全程載著、沒有 4xx／5xx），
  不是基礎設施故障 ⇒ **不標 `infra_void`、不補跑、不挑掉**。補跑其中幾格會讓同一批有兩種條件，
  理由與 09-19 §七之一相同。

### 「它每一次都說自己做完了」

```
ON 臂（逐次嘗試）：(stop_reason, agent_rc) → 次數
                     09-19   本輪
('visible_fail',  0)   82     79     ← 交付物沒過驗收，而 agent 回報「成功」
('visible_fail', -9)    8     13     ← 被我們的 300 秒上限砍掉的，不算
('visible_pass',  0)   24     24
OFF 臂：('ungated', 0) 52 → 50 ／ ('ungated', -9) 2 → 4
```

**沒有被我們砍掉的失敗嘗試，全部回報成功：09-19 是 82/82，本批是 79/79。**

---

## 三、非 thinking：逐通掃 `reasoning_content`

判準與 09-19 相同：逐通掃 `wire_*/*.resp.bin` 的 SSE 塊（腳本 `launch/scan_reasoning.py`）。

```
回應檔數：653（652 個解析得出 SSE 塊；1 個是 0 位元組的被砍那一通）
含非空 reasoning_content 的回應數：0 ／塊數：0
usage.completion_tokens_details.reasoning_tokens：{'0': 639}
回應宣稱的 model：{'gemma-4-12b-it-qat': 20464 塊}
```

同一支腳本對 09-19 那批重掃：635／0／0／`{'0': 632}`——**兩批一致**。
⚠ 09-19 裁決寫的是「`usage.reasoning_tokens` 全部 `None`」，那是頂層欄位；本腳本讀的是
`completion_tokens_details.reasoning_tokens`，兩台都回 0。**兩個欄位都不可以拿來分辨 thinking**，
判準仍然只有 `reasoning_content`。

另外記一件兩批都有、但沒人寫過的事：回應內容裡有 `<|channel>thought\n<channel|>` 這個**空的**
thought 通道標記（09-19：467/635、本批：484/652；vacant-dev 的 stream log 兩批都印得出來）。
標記之間是空的、`reasoning_content` 也是空的 ⇒ 仍判非 thinking；但**展場若把模型原文印上螢幕，
這兩個標記會跟著出現**。

---

## 四、錄影怎麼合成的（四條流 × 兩批 → 一份）

每條流各寫一份 lifecycle（`lifecycle/b{1,2}_s{0..3}.jsonl`，8 份，原樣保存在 run 目錄裡）。
合成用 `launch/merge_lifecycle.py`：

- 每一行**原樣**搬（位元組不動、不重新序列化）；
- 依 `ts_ms` 做 k 路合併，**同一個檔內的相對順序不變**。每個 `run_id` 只活在一條流裡
  ⇒ 它的 `seq` 仍然各自連續（`lifecycle.validate_stream` 的判準）；
- 合併前後逐行 sha256 的多重集合必須相等、合併後 `ts_ms` 必須單調不減，否則不寫。

輸入全部是同一次 `run_twin.py --events` **跑的當下**寫的；這一步只決定行的先後，
不新增、不刪、不改任何一筆 ⇒ 不是被禁止的「run 目錄 → lifecycle」轉換。

| 驗證 | 結果 |
|---|---|
| `lifecycle.validate_stream`（合併後 1380 行） | **0 問題** |
| 錄影裡的建置機路徑（`/var/tmp`、`/home/`、`/Users/`） | **0 行** |
| `pair_receipts.py --recording … --runs runs/twin_lreal_20260924` | ✓ 54 格，綁 sha256 `bf0ff8dadd37…` |
| `pair_receipts.py --check --recording ops/exhibit/twin/recordings/lreal_20260924.jsonl` | ✓（sha256＋逐格鏈頭） |
| `serve_twin.py --check`（預設＝`recordings/*.jsonl` 全部） | ✓ fixture、✓ lreal，兩份都「配對收據綁定過」 |
| `verify_receipts --selftest` | **PASS** |
| `verify_receipts --glob 'runs/twin_lreal_20260924/runs/*'` | **總判 OK**：54 條鏈、170 筆 entry 逐筆驗過、中介有 54／零請求 0；逐格另印 `tier=C` |
| 配對收據的證據等級 | `evidence_counts` ON `{'L-real': 54}`、OFF `{'L-real': 54}`；`void_cells` 空 |

---

## 五、⚠ 兩件要主線決定的事（本輪沒動程式）

### 1. 預設開機時，這份 L-real 錄影**一格都播不出來**

`serve_twin.load_recordings` 對同一個 `cell_id` 是「**先來的贏**」，預設錄影清單是
`sorted(recordings/*.jsonl)` ⇒ `fixture_20260924` 排在 `lreal_20260924` 前面，
而兩份錄影**共用全部 54 個 cell_id** ⇒ 實測 `lreal_20260924.jsonl` **收了 0 格**
（`problems` 54 條「已經在 fixture_20260924.jsonl 裡，這一份不收」）。
`serve_twin.py --check` 仍然兩份都 ✓，因為它是逐檔驗、不驗兩份放在一起的結果。

⇒ 想播 L-real，現在要嘛 `exhibit_boot.sh --recording ops/exhibit/twin/recordings/lreal_20260924.jsonl`
明講只播這一份，要嘛把 fixture 移出 `recordings/`、要嘛改優先序。**哪一個是主線的決定**
（fixture 是 L-none 的離線備援，有它存在的理由），本輪只把事實記下來。

### 2. 這一批沒有 `twin.sidecar/1` 旁註

收到「改用 `feat/twin-postaudit-sidecar`」的指示時，本批已經發射（08:04:25Z 起跑）。
照指示**不中斷、不換程式**（同一批兩種程式版本比少一份旁註更糟）。
⇒ 錄影旁邊**沒有** `lreal_20260924.sidecar.jsonl`；OFF 臂事後稽核的原始資料
`postaudit_RUN-OFF.json` 在 run 目錄裡 **54/54 都在**，之後要不要、怎麼補旁註由主線決定。
（旁註分支合併之後，若它的 `pair_receipts.py --check` 要求旁註，這份錄影會被擋——那是預期的。）

---

## 六、展場文案：哪些要跟著改

`30 件被擋下` 那一組數字是 **09-19 那一批**的。播這份錄影時，對應的數字要照本批寫：

| 文案 | 09-19 | 本批（`lreal_20260924`） |
|---|---|---|
| 有差別／沒差別 | 30 格／24 格 | **30 格／24 格**（同） |
| 被擋下（ON 拒交，OFF 事後量起來也沒過） | 30 件 | **30 件**（同） |
| 迴圈救回 | **0/30** | **1/31**——而那 1 格是「被 300 秒砍兩次、第三次沒被砍」，OFF 一次就過；**不可以講成回饋讓它做對了** |
| 沒被砍的失敗嘗試裡 agent 回報成功 | 82/82 | **79/79** |
| 拒交格裡有被我們砍過的 | 3 格 | **6 格**（其中 4 格最後一次就是被砍的） |
| 證據等級 | L-real 54/54 | L-real 54/54；**另外收據上是 `tier=C`（未認證），不可以講 A 級** |

- 「30 件被擋下**不含**讓它做對了」這句話在本批**仍然成立**：兩臂的交付物正確與否逐格一致（54/54），
  這一層改變的是不合格的東西會不會出去，不是它合不合格。
- 但「迴圈救回 0/30」**不可以**原樣搬來講本批。
- n 的獨立單位是**題（9 題）**不是格；居民之間不是獨立重複（本批同樣 8/9 題三位居民完全一致）。

## 七、還不能說的話（沿用 09-19 §七，本批的補充）

1. 不能說「Vacant 讓 agent 做對了」——本批唯一的救回是逾時之後的重跑，不是回饋的證據。
2. 不能說「A 級」——54 格全部 `tier=C`。
3. 不能說「兩批一模一樣」——最終裁決逐格相同，但嘗試次數、逾時、通數都不同（上表）。
4. 不能把本批與 09-19 **併成一批 108 格**講：兩次執行、兩個程式版本、同一組題目與居民，
   是**重複**，不是更多樣本；而且獨立單位仍然是題。
5. 「重播」不是「正在發生」——這份錄影是 2026-09-24 08:04–09:44Z 在 vacant-dev＋1004 跑的紀錄。

## 八、動了哪些檔

```
runs/twin_lreal_20260924/                 新增：108 跑的全部落盤（19 MB，不含工作區 ws/）
  ├─ runs/<cell_id>/…                      同 09-19 的形狀（run_RUN-{ON,OFF}.json、wire、收據、postaudit）
  ├─ lifecycle/b{1,2}_s{0..3}.jsonl         四條流 × 兩批的原始 lifecycle（錄影的來源）
  └─ launch/                                發射腳本、stream log、1004 輪詢、code_commit、合併與掃描腳本
ops/exhibit/twin/recordings/lreal_20260924.jsonl       錄影（1380 行，510 KB）
ops/exhibit/twin/recordings/lreal_20260924.pack.json   配對收據（54 格，639 KB）
runs/INDEX.{md,json}                      重生（build_runs_index.py，--check OK）
decisions/DECISION_20260924_TWIN_LREAL_RERECORD.md     本檔
```

**`vacant_network/` 與 `ops/exhibit/twin/*.py` 一個字都沒動。**

### 重跑指令（零機時）

```bash
python3 -m vacant_network.vrun.verify_receipts --selftest
python3 -m vacant_network.vrun.verify_receipts --glob 'runs/twin_lreal_20260924/runs/*'
python3 ops/exhibit/twin/pair_receipts.py --check --recording ops/exhibit/twin/recordings/lreal_20260924.jsonl
python3 ops/exhibit/twin/serve_twin.py --check
python3 ops/exhibit/twin/serve_twin.py --check --recording ops/exhibit/twin/recordings/lreal_20260924.jsonl
```

發射指令（要機時）在 `runs/twin_lreal_20260924/launch/batch.sh`（路徑是 vacant-dev 的 `/var/tmp`）。

## 收尾（主線，2026-09-24 同日）

1. **旁註是事後轉寫的。** 這批在旁註程式（`twin.sidecar/1`）合併前發射，照「同一批不換程式」
   跑完 ⇒ 量的當下沒有寫旁註。主線用 `ops/exhibit/twin/sidecar_from_postaudit.py` 把每格
   已經存在的 `postaudit_RUN-OFF.json` 換成旁註格式（`recordings/lreal_20260924.sidecar.jsonl`，
   54 筆，其中 30 筆沒有全過——與 ON 拒交 30 格對得上）。
   - 不重量、不改錄影一個位元組；只轉寫 run 目錄 `ws_end_sha256` **等於**錄影裡那一跑
     `run_ended.ws_end_sha256` 的那幾筆（對不上整批不轉，有測試）。
   - 每筆帶 `derived_from`；`ts_ms` 取那一跑的 `run_ended.ts_ms`（舊檔沒記量完的時間，
     mtime 會被 checkout 改寫，不拿它當時間）。
   - 配對收據重建：格子內容逐位元組不變，只多綁了旁註的 sha256。
2. **錄影撞 id 的規則改成「證據等級高的贏」**（`serve_twin.load_recordings`）。舊規則「先載入的贏」
   讓照檔名排序在前的 `fixture_*`（L-none）蓋掉這批 L-real，54 格一格都播不出來。
   同級撞 id 仍然先來的贏；輸的那一份每一格都寫進 `problems`。有負控制。
3. **展場文案**：本批的數字（救回 1/31、79/79、拒交裡 6 格被砍過、全部 tier=C）只能描述**本批**；
   官網（vacant-docs-web）目前引用的是 09-19 那批（救回 0/30），那句對 09-19 仍然成立，
   但展場播的是本批——要不要改由人類決定（官網 push 即上線）。
