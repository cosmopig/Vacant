# R453 預註冊：跨機**真跑**多方執行（零模型呼叫）

（2026-09-06 寫定並簽入，**在任何一台遠端機器產生任何一筆證言之前**。
本文件唯一的用途是把預測與判準釘死在資料之前；跑完之後只准補「結果」，
不准改窗口、不准改分母、不准改判定規則。）

## 〇、為什麼是這一輪

R449 §七-1 的推翻條件寫著：

> 若**真跑（非重放）**的多方執行在門檻以下出現與單執行器不同的交付決定
> ⇒「逐位相同」是重放假象。

R452 §四 的誠實邊界也寫著：

> 全部是重放與模擬……**跨機真跑多方執行仍未做**（R449 §七-1）。

到目前為止，`ops/gain/replay/peer_exec_sim.py`／`r452_suitespec.py` 的每一格
可見標籤都是**同一台 Mac 的同一顆沙箱**算出來的，k 個「執行器」共用一份
`facts` cache 或一支 `_LabelProbe`。那種設定下「k 台一致」是**恆真句**，
不是量測。本輪把 k 台執行器放到**三台不同的機器、三種作業系統、三個
Python 直譯器**上，各自真的開沙箱、各自用自己的金鑰簽自己的鏈，
然後在 Mac 上合票。

同時這一輪也直接測 R452 §六-2 的推翻條件：

> 若真跑跨機執行時渲染碼在不同平台給出不同可見標籤 ⇒「渲染確定性」要加平台限定。

## 一、k 與機器（本輪計畫的組態）

計畫 **k = 3**：

| 代號 | 機器 | 平台 | Python | 角色 |
|---|---|---|---|---|
| `mac` | 本機 MacBook Pro | darwin / arm64 | 3.11（repo `.venv`） | 執行器 ＋ 合票端 |
| `vacantdev` | `user1@100.124.254.83` | Linux (Ubuntu 6.8) | 3.12.3 | 執行器（`nice -n 10`、**至多 2 個 worker**） |
| `win1003` | `w401-win`（Tailscale） | Windows / MINGW64 git-bash | 3.12.5（scratch venv） | 執行器 |

**已完成的可達性探查（寫本文件之前做的，只是探查，尚未產生任何證言）**：
三台都 ssh 得通；`vacant-dev` 的 `~/vacant/Vacant` 已在 `b5daa07`、工作樹乾淨
（只有 untracked 的 `runs/`，**不動它、不 stash**）；`win1003` 的
`/d/vacant/Vacant` 是舊 commit（`485ee55`）所以**不用它**，改在
`/d/vacant/r453_scratch/` 解開本 commit 的 `git archive` 並自建 venv
（Python 3.12.5、`cryptography` 50.0.1，已裝好）。

**Fallback 規則（預先寫死）**：若 `win1003` 在**開始嘗試後 15 分鐘內**無法
跑起沙箱（連不上、venv 壞掉、`vacant/checks.py` 在 Windows 上起不了 harness、
或 `python -I` 路徑問題），本輪**降為 k = 2**（`mac` ＋ `vacantdev`），
在結果檔與報告裡**明說**降級與原因，quorum 相應改為 `2//2+1 = 2`（＝全票）。
不重試第三台、不換第四台機器補位。

## 二、資料與流程（零模型呼叫）

- 題庫：`runs/g_r446_eq5_mbpp`（EQ5 臂，371 題 × 5 候選 = 1855 格）。
- 套件：`ops/gain/replay/cache/suitespec_g_r446_eq5_mbpp.json`（368/371 可轉成
  `SuiteSpec`；3 題參考解回傳 `re.Match`，資料形態排除，R452 §四）。
  ⇒ **本輪的格子數 = 368 × 5 = 1840**。
- 候選碼：在 Mac 上用 `ops.gain.gain_run.extract_code` 從
  `runs/g_r446_eq5_mbpp/calls.jsonl` 抽出，**只把抽出來的碼**送到別台機器。
  prompt、reviewer 紀錄、`calls.jsonl` 本身**不出本機**——執行器本來就只看得到草稿碼。
- 每台執行器：對每一格 `(task, candidate)` 用 `vacant.peerexec.Executor.attest`
  ——它會**在本機用自己的渲染器**把 spec 渲染成驗收碼，跑自己的
  `vacant/checks.py` 沙箱，把結果簽進**自己的** hash-chain。
- 合票在 Mac：`form_verdict`（帶 Mac 側 `commit_suite_with_gauge` 造出的量具白名單、
  帶 `render_sha256`）→ 每題走 `select_by_quorum` 的同一條早停迴圈。
- **`hidden_check` 只用來計分**（交付正確／假交付），不進機制、不在遠端跑。
- **零模型呼叫**：不碰 `100.119.113.56:8765`、不碰 `100.86.226.21:1234`。
  （`w401-win` 這台機器同時是 8765 的主機，但本輪只用 ssh ＋ 本機沙箱，
  不對它發任何推論請求。）

### 一個必須先說清楚的實作細節

單一執行器只有**一條**鏈，鏈的 append 不能並行。所以每台機器的流程是：
**沙箱在 N 個 worker 行程裡真跑**（那是本輪要量的東西），**簽章與串鏈在主行程
依固定順序序列化**。worker 回傳的是它自己那次真跑的 `ProbeResult`，主行程
把同一個結果交給 `Executor.attest` 去簽。這不是重放別台機器的結果，是
同一台機器同一次執行的結果換一個行程去簽；worker 也回傳它算出的
`render_sha256`，主行程會跟自己算的比對，不符就記成異常而不是默默吃掉。

## 三、預測（P-1 … P-6），窗口寫在括號裡

**P-1 跨機可見標籤一致**：1840 格在 3 台機器上的 `visible_ok` 完全相同。
窗口：**≥ 99.5%（≥ 1831/1840）**。點預測：1840/1840。
理由：R449 §三-2 已在 repo 內看到 2310/2310 相同；已知的 1 ULP 可攜性問題
（`l**2` vs `l*l`）只出現在 **hidden** 側（MBPP+ `atol=0`），可見側沒有。
**低於窗口 ⇒ R452 §六-2 觸發（渲染確定性要加平台限定）。**

**P-2 裁決與 r446 runtime 出貨 sha 相同**：對每一個「非拒交」的題目，
k=3 quorum 選出的 `shipped_sha256` ＝ `rows.jsonl` 的 `gate_code_sha256`。

> ⚠ **窗口的分母要先更正，而且更正的理由必須在跑之前寫下來。**
> 任務書寫的是 345/345（＝ runtime 的 accepted 數）。**345 在本輪的構造下
> 是算術上到不了的數**，原因兩條，都不是跨機不一致：
> 1. runtime 交付的 345 題裡有 **3 題轉不出 `SuiteSpec`**
>    （`mbppplus_Mbpp/{737,787,794}`，`expected_not_a_literal_type:Match`，
>    R452 §四已載明）⇒ 它們**沒有套件可交**，連跑都不會跑。
> 2. 剩下的 342 題裡有 **2 題過不了量具**（`mbppplus_Mbpp/{404,587}`：
>    壞樁 `return a[0] if a else None` 通得過它們的可見套件，
>    `ops/gain/replay/cache/r452_realgauge_g_r446_eq5_mbpp.json` 已落盤）
>    ⇒ `commit_suite` 依 R449 §四-3 **拒絕上鏈**，`select_by_quorum` 回
>    `suite_gate:...` 拒交。這是機制在運作，不是分歧。
>
> 所以本輪的窗口是 **340/340**，並且要求帳目對得起來：
> **340（相符）＋ 3（不可轉）＋ 2（量具擋下）= 345**。
> 26 題 runtime 拒交的，本輪也必須全部拒交（**26/26**）。
> **任何一格落在 340 之外、且無法歸因到具名的機器層原因（平台浮點表示、
> 逾時、缺 import、沙箱 harness 起不來），就是 R449 §七-1 的推翻。**

**P-3 誠實執行器的指名爭議 = 0**：三台都誠實 ⇒ 1840 格的
`dissenters` ∪ `detail_dissenters` ∪ `equivocators` ∪ `rejected` 全空，
`contested` 格數 = **0**。窗口：**0**（任何 > 0 都要逐格列出並歸因）。

**P-4 鏈驗證**：每台機器的 `verify_executor_chain` 為 True（seq 連續、
prev_hash 串對、每一筆簽章用**名冊上的**公鑰驗過）。窗口：**3/3 台為 True**
（降級時 2/2）。

**P-5 每題牆鐘**：每台機器上「一題」的沙箱＋簽章時間。**兩個數字都要報，
窗口掛在第一個上**（先寫清楚，免得事後挑對自己有利的那個）：

- **P-5a 全五格**：把一題的 5 個候選全部證言完的耗時（本輪為了 P-1 必須全跑）。
  窗口：**中位數 ≤ 5 秒**。
- **P-5b 早停前綴**：`select_by_quorum` 實際會跑的那幾格（跑到第一個通過就停）
  的耗時——**這才是部署時的成本**，也是展場那句「秒級」對應的東西。
  無窗口，照實報中位數／p95／最大值。

兩者都同時報 p95 與最大值，並附註該台機器用了幾個 worker。
理由：R449 §三 量到單格沙箱 ~630 ms、簽章 1.0 ms；本題庫 1840 格裡有 309 格
可見驗收沒過，那些格子會多花 `conform_failure_detail` 的
⌈log2 n⌉+2 次沙箱（n≈3 ⇒ 約 4 次）去二分出條號——那是 `detail_dissenters`
這條歸屬通道的成本，本輪**不關掉它**。
**這一條超窗不會推翻 R449 的機制結論，只會改「展場秒級」那句話的措辭。**

**P-6 渲染逐位可攜**：368 份 spec 的 `suite_sha256` 與 `render_sha256`
在三台機器上完全相同。窗口：**368/368 兩者皆同**。
（這是 P-1 的上游：標籤相同但渲染不同，代表兩件事互相抵銷；
`form_verdict` 會用 `render_sha256` 把渲染漂移的票擋在計票之外。）

## 四、判定規則（三選一，跑之前就寫死）

- **REAL_MATCHES_REPLAY**：P-1 ≥ 窗口、P-2 = 340/340 且拒交 26/26、P-3 = 0、
  P-4 全 True、P-6 = 368/368。
  ⇒ R449 §七-1 **未觸發**；「門檻以下逐位相同」不是重放假象。
  R452 §六-2 **未觸發**。
- **REPLAY_ARTIFACT**：P-2 出現任何一格不符，且**無法**歸因到具名的機器層原因
  ⇒ R449 §七-1 **觸發**，R449 §三 那張表要加「僅在單機重放下成立」的限定，
  §四-1 的採用裁決要重審。
- **INVALID**：任一台機器沒跑完、鏈驗不過、或標籤大量缺漏（> 1% 的格子沒有結果）
  ⇒ 本輪不產生任何關於 §七-1 的結論，照實說「沒測到」。

歸因用的「具名機器層原因」只有這四類，其餘一律算 REPLAY_ARTIFACT：
(a) 平台浮點表示／libm 差異（要能指出是哪一題、哪一條測資、差幾 ULP）；
(b) 沙箱逾時（要能指出該格的 wall time 貼著 8 秒上限）；
(c) 缺 import／解譯器版本差異造成的 `loads_ok=False`（要能指出模組名）；
(d) 沙箱 harness 起不來（`CheckInfraError`，照鐵律 3 記 `infra_void`，
    **不進分子也不進分母**，並且要單獨列出格數）。

## 五、產出（本 repo）

- `ops/gain/replay/peer_exec_real.py`（executor／verdict 兩個角色）
- `ops/gain/replay/r453/att_<machine>.ndjson`（逐格證言，含 LogEntry）
- `ops/gain/replay/r453/pub_<machine>.json`（公鑰、平台、Python、commit、
  承重檔案 sha256、牆鐘）
- `ops/gain/replay/r453/r453_result.json`（P-1…P-6 ＋ 判定 ＋ 逐題比對表）
- `ops/gain/replay/r453/r453_table.txt`

## 六、誠實邊界（本輪自己的）

- 三台機器共用**同一份** `vacant/checks.py` 沙箱與**同一份**渲染器。
  R449 §六 的「相關性沙箱故障未建模」在本輪**依然成立**：本輪測的是
  平台／直譯器差異，不是異質沙箱。渲染器有 bug，三台會一致地錯。
- 三台都誠實。本輪**不測**腐化、不測說謊者——那些 R449 已在模擬裡量過，
  本輪唯一的問題是「真跑時誠實者還會不會一致」。
- 候選碼是 r446 已歸檔的草稿，不是現場生成的。**「真跑」指的是執行，不是生成。**
- `hidden_check` 只在 Mac 上、只從既有 cache 讀，只用來計分。
- 量具白名單在 **Mac 側**造（`run_suite_gauge` ＋ `commit_suite`，
  ＝`commit_suite_with_gauge` 拆成可並行的兩段，判準與樁集合與 R452 的
  `real_gauge` 逐字相同：1 參考解 ＋ 4 壞樁）。遠端機器不重跑量具——
  這一段仍是單機的，本輪不宣稱量具跨機可攜。
- Windows 那台的 `vacant/checks.py` 走的是 `os.name != "posix"` 分支：
  **沒有** `setrlimit` CPU／記憶體上限、**沒有** `killpg` process group 清理。
  這是既有程式碼的既有形狀，本輪不改它；它意味著 Windows 執行器的資源隔離
  比另外兩台弱，若出現只在該台發生的逾時，歸因時要優先考慮這一條。

---
預註冊者：Claude Opus 5（實作），待 Fable 稽核。
簽入 commit：見本檔隨附的 round453 commit（**本文件與 `peer_exec_real.py`
先簽入，然後才 `git archive` 送到遠端**）。

---

# 結果（2026-09-06 跑完後補寫；上面每一個字未改，窗口與判定規則未動）

## 〇、先講兩件對自己不利的事

1. **k = 2，不是 3。** `win1003` 在開始嘗試後 **2 分鐘**內就確定跑不起沙箱
   （16:51 開始、16:53 定位到根因），依 §一 的 fallback 規則降為 k = 2。
   根因不是連線、不是 venv，是 `vacant/checks.py` **在 Windows 上根本不能用**
   （詳見 §四），落盤在 `ops/gain/replay/r453/win1003_sandbox_failure.json`。
2. **P-3 的窗口破了（10 格），而破法是我自己的窗口寫壞了，不是機器不一致。**
   那 10 格 ＝ §三 P-2 早就點名要排除的那 2 題 × 5 個候選，被指名的是**套件**
   不是任何一台機器。詳見 §三 P-3。我**沒有**改窗口；我加了一個更細的
   計數（P-3b）並且兩個數字都報。

## 一、實際跑到的機器

| 代號 | 平台 | Python | workers | nice | 牆鐘 | 格數 | 錯 | 鏈驗證 | vacant_id（前 24） |
|---|---|---|---|---|---|---|---|---|---|
| `mac` | macOS 15.7.3 / x86_64 | 3.12.10 | 6 | 0 | 135.4 s | 1840 | 0 | True | `zQmXqnnkmkaVaRTARC8nESWa` |
| `vacantdev` | Linux 6.8.0-137 / x86_64 / glibc 2.39 | 3.12.3 | 2 | 10 | 149.7 s | 1840 | 0 | True | `zQmNWi3ewAdrE9jbBHuAJuhV` |
| ~~`win1003`~~ | Windows 10 / MINGW64 | 3.12.5 | — | — | — | **0 可用** | 20/20 | — | — |

⚠ **預註冊 §一 那張表有兩個字寫錯了，在這裡更正而不是回去改它**：Mac 被寫成
`darwin / arm64`、`Python 3.11`，實際是 **x86_64 / Python 3.12.10**
（`pub_mac.json` 落盤）。那是寫預註冊時憑印象填的欄位，不影響任何預測或窗口
——但兩台都是 x86_64 這件事**縮小了 P-1 的說服力**：本輪量到的是
「同一個 CPU 架構、兩個作業系統、兩個 Python 小版本」之間的一致，
**不是跨 CPU 架構**（arm64 vs x86_64 的浮點與 libm 差異正是 R449 §六
那條 1 ULP 邊界的來源）。跨架構仍未測。

碼怎麼到那台機器上的：`git archive 7c4c14d`（本預註冊的 commit）的子集
tarball，`sha256=da5096b81abfdc119ee4993fcc88f2f67a3fd9a24570d916ac41884733640ef4`，
scp 到 `~/vacant/r453_scratch/`（vacant-dev）／`D:/vacant/r453_scratch/`（win1003）
解開；**vacant-dev 的 `~/vacant/Vacant` 一個字都沒碰**（它本來就在 `b5daa07`、
工作樹乾淨，但本輪需要的新檔不在那個 commit 裡，所以走 tarball 而不是 git pull）。
候選碼走 `ops/gain/replay/r453/pool_g_r446_eq5_mbpp.json`
（`sha256=1dbc5deb7b986752f10a901a3cca230576829bc54cfbb6af3821a9bd3fe2d1b6`，
368 題 × 5，1.93 MB）——**`calls.jsonl`、prompt、reviewer 紀錄一個位元組都沒出本機**。

**承重檔案跨機逐位相同（7/7）**——這是「跨機一致」這句話的前提，不是裝飾：

| 檔案 | sha256（兩台相同） |
|---|---|
| `vacant/peerexec.py` | `616022515fc3f4c9…` |
| `vacant/suitespec.py` | `b83adac1564d18c1…` |
| `vacant/checks.py` | `91799f4d65b1fa2a…` |
| `vacant/logbook.py` | `e4bb0da72ba9bc2b…` |
| `vacant/identity.py` | `b25923e580fb9a8a…` |
| `ops/gain/gain_run.py` | `8e0b84525d758b4f…` |
| `ops/gain/replay/peer_exec_real.py` | `51f4cf07726b82ce…`（＝ `7c4c14d` 那一版） |

⚠ 最後一列要說清楚：**執行器跑的是 `7c4c14d` 的 `peer_exec_real.py`**
（`51f4cf07…`）。本檔在跑完之後又改過（只改 `--role verdict` 的報表，見 §五），
所以 repo 現在那一份的 sha 是 `5072411e…`，**與兩台執行器上跑的那一份不同**。
簽章與標籤那一側一格都沒重跑。

## 二、結果總表

```
P-1 跨機可見標籤一致   1840/1840  (100.0000%)   窗口 >=99.5%   PASS
P-2 出貨 sha 與 r446   340 相符 / 0 不符；拒交 26 相符 / 0 不符；
                       量具擋下 2                窗口 340/340   PASS
P-3a contested 格      10        窗口 0                        FAIL（見下）
P-3b 執行器被指名格    0                                       PASS
P-4 鏈驗證             mac True、vacantdev True                PASS
P-6 渲染逐位可攜       render 368/368、suite 368/368            PASS

判定：REAL_MATCHES_REPLAY_EXCEPT_P3
R449 §七-1 推翻：未觸發        R452 §六-2 推翻：未觸發
```

## 三、逐條

**P-1（PASS，1840/1840）。** macOS/3.12.10 與 Linux/3.12.3 兩台各自渲染、
各自開沙箱，1840 格可見標籤**一格不差**。連 `first_failing_test`（FAIL 陣營
卡在第幾條）也一格不差——`detail_dissenters` 恆為空就是證據。
另外：兩台的 3680 個標籤與**既有的單執行器 cache**
（`peerexec_facts_g_r446_eq5_mbpp.json`，R449／R452 全部重放結果的來源）
比對，**3680/3680 相符、0 不符**。R449 §六 那條「MBPP+ 隱藏測資 `atol=0`
跨機不可攜（1 ULP）」在可見側**沒有出現**，與預測一致。

**P-2（PASS，340/340 ＋ 26/26）。** 帳目照預註冊對得起來：
**340（quorum 選出的 sha ＝ runtime `gate_code_sha256`）＋ 3（轉不出 SuiteSpec）
＋ 2（量具擋下）＝ 345**（runtime 的 accepted 數）；runtime 拒交的 26 題本輪
**26/26 也拒交**。零不符 ⇒ **R449 §七-1 未觸發**：門檻以下的「逐位相同」
在真跑跨機下**仍然成立**，不是重放假象。
量具擋下的兩題是 `mbppplus_Mbpp/404`、`mbppplus_Mbpp/587`，理由 `gauge_failed`
（壞樁 `return a[0] if a else None` 通得過它們的可見套件），與預註冊逐字相同。

**P-3（P-3a FAIL、P-3b PASS）。** 10 格 contested ＝ 上面那 2 題 × 5 個候選，
每一格的 `rejected` 都是 `[["mac","suite_not_gauged"],["vacantdev","suite_not_gauged"]]`，
而 `dissenters`／`detail_dissenters`／`equivocators` **全空**。
也就是說：**沒有任何一台機器被指名**，被指名的是那套驗收
（`form_verdict` 的 docstring 自己寫過「被指名的不是執行器，是那套驗收」）。
我在預註冊裡把 `rejected` 寫進 P-3 的聯集，那是**窗口寫壞了**——它與 P-2 的
排除清單重複計算了同兩題。**窗口不改**（改窗口就是事後配合結果）；改的是
報表多出一個 P-3b＝只算執行器被指名的格數，**0/1840**。兩個數字都印在
`r453_table.txt` 與 `r453_result.json` 裡。

**P-4（PASS）。** 兩台的鏈各自用**名冊上的**公鑰驗過（seq 連續、prev_hash 串對、
每一筆簽章）。book head：`mac 9f34a546…`、`vacantdev d0389abb…`（不同金鑰 ⇒
不同簽章 ⇒ 不同鏈頭，這是預期，不是分歧）。

**P-5（PASS，但要看清楚哪個數字）。**

| 機器 | workers | P5a 中位 | P5a p95 | P5a max | P5b 中位 | P5b p95 | P5b max | 總牆鐘 |
|---|---|---|---|---|---|---|---|---|
| `mac` | 6 | **1.069 s** | 3.871 s | 41.638 s | 0.207 s | 3.569 s | 41.638 s | 135.4 s |
| `vacantdev` | 2 | **0.250 s** | 1.695 s | 38.222 s | 0.050 s | 1.657 s | 38.222 s | 149.7 s |

中位數兩台都遠在 5 秒窗口內。**max 那一欄不是機器慢，是候選在無窮迴圈**：
最慢的三題（`Mbpp/84`、`Mbpp/260`、`Mbpp/71`）在**兩台上都最慢、而且時間幾乎相同**
（84：41.6 s vs 38.2 s；260：39.1 vs 37.6；71：19.3 vs 18.5），逐格看是單一候選
吃滿 10 秒沙箱上限，再乘上 `conform_failure_detail` 的二分次數。
那是題目與候選的性質，不是平台差異——這一點本身也是 P-1 的旁證。

**P-6（PASS，368/368 ＋ 368/368）。** 每一題的 `suite_sha256` 與 `render_sha256`
在兩台上完全相同；`form_verdict` 帶著 Mac 側算的 `render_sha256` 去計票，
**沒有任何一筆證言因為 `render_mismatch` 被擋**。⇒ **R452 §六-2 未觸發**，
「渲染確定性」目前不需要加平台限定——**但只限 macOS/Linux 這兩個平台**
（Windows 那台連沙箱都跑不起來，這句話對 Windows **沒有量到**）。

**額外（不在 P-1…P-6 裡，但它保護整份結果）：`_select_loop` vs 真的
`select_by_quorum`＝366/366 相符**（2 題沒有合法 commit 因此跳過）。
合票端拿到的是遠端離線簽好的證言，沒有辦法把遠端私鑰搬過來讓
`select_by_quorum` 現場簽，所以本檔自己寫了一條早停迴圈——**自己寫的迴圈就是
自己的規格**，除非它跟被稽核過的那一支對得起來。用重放探針讓
`select_by_quorum` 看到相同的 k 條標籤流，逐題比出貨索引，366/366。

**計分（`hidden_check` 只在這裡出現）**：368 題中交付正確 274、假交付 66、
拒交 28（＝ 26 ＋ 量具擋下的 2）。

## 四、win1003 為什麼出局（根因，不是「連不上」）

`vacant/checks.py` 產生的 runner 用 `selectors.DefaultSelector()` 監看候選
worker 的 **stdout pipe**。Windows 上 `DefaultSelector` 是 `SelectSelector`，
而 Windows 的 `select()` **只吃 socket，不吃 pipe／檔案 handle**：

```
File ".../selectors.py", line 314, in _select
    r, w, x = select.select(r, w, w, timeout)
OSError: [WinError 10093] 可能是應用程式尚未呼叫 WSAStartup，或 WSAStartup 發生失敗。
```

⇒ runner `rc=1`、stdout 空 ⇒ **每一格 `run_python_check` 都會回 False**。
還有第二個獨立的 bug 把上面這個蓋住：`tempfile.TemporaryDirectory` 清理時
`PermissionError [WinError 32]`（Windows 上 `kill()` 之後 handle 未即時釋放），
所以第一眼看到的是例外不是錯誤標籤。兩者都落盤在
`ops/gain/replay/r453/win1003_sandbox_failure.json`（含完整 traceback）。

**沒有把它硬湊成第三台**，理由要講明白：如果只修掉第二個 bug（讓清理容忍
`PermissionError`），win1003 會交出 1840 個**全部 False** 的標籤，於是在
k=3、quorum=2 下 mac＋vacantdev 過半、win1003 在約 1531 格被指名為少數方。
機制會正確地指名它——但那不是「誠實執行器的分歧」，那是一台沙箱壞掉的機器
（鐵律 3 的 `infra_void`）。把它算進 P-1…P-6 會讓 P-3 以一個**與預註冊問題無關**
的理由失敗，然後再被重新詮釋成別的東西；那正是預註冊存在的目的所要擋的事。
它也不能被改成「證明機制會指名壞機器」——**那個實驗沒有預註冊**。

這條發現對展場的定位有直接後果：CLAUDE.md 說展件要「離線可跑、可無人值守」，
而 `vacant/checks.py` 目前的 `os.name != "posix"` 分支是**看起來有、實際不能跑**。
它不在本輪的修改範圍（改它會動到全體共用的沙箱、且要重跑所有既有結果），
記在這裡當標本。

## 五、跑完之後改過的東西（逐項，全部只在報表端）

`ops/gain/replay/peer_exec_real.py` 在拿到數字之後改了三處，**沒有任何一格
標籤、簽章、鏈或選擇被重算**（executor 那一側跑的是 `51f4cf07…`，一次都沒重跑）：

1. **加** `P3b_executor_named_dissent_cells`：只算 `dissenters`／`detail_dissenters`
   ／`equivocators`。P-3a 的窗口與數字原樣保留並照樣印 FAIL。
2. **修**「哪個數字對應哪個推翻條件」的接線：第一版寫成
   `r449_seven_1_overturn = (decision == "REPLAY_ARTIFACT")`，而預註冊 §四
   把 §七-1 逐字綁在 **P-2** 上。P-2 零不符卻印出「§七-1 觸發」是接線錯誤，
   不是量測結果。改成 `not P2.pass`。
3. **加** 第四個判定標籤 `REAL_MATCHES_REPLAY_EXCEPT_<破掉的預測>`：預註冊 §四
   的三個標籤不是窮盡的（P-2 全對但別的窗口破掉會掉進縫裡）。掉進縫裡就給它
   自己的名字，不塞進 REPLAY_ARTIFACT（那會宣告一件沒發生的事），
   也不塞進 REAL_MATCHES_REPLAY（那會把破掉的窗口當沒看見）。

第一版（未改接線）跑出來的原始輸出是：`判定：REPLAY_ARTIFACT`、
`R449 §七-1 推翻：觸發`，數字則與現在**逐格相同**（P-1 1840/1840、
P-2 340/0/26/0、P-3a 10、P-4 兩台 True、P-6 368/368）。留在這裡供對帳。

## 六、本輪的誠實邊界（補充 §六 已寫的）

- **k=2 的 quorum ＝ 2 ＝ 全票**，所以本輪**沒有量到**「少數方被指名」那條路徑：
  兩台一致時無從產生少數方。R449 §三 那張「說謊者 100% 被指名」的表**仍然只有
  模擬證據**，本輪一個字都沒有加強它。
- 本輪只證明了**誠實執行器在兩個 POSIX 平台上會一致**。三台、異質作業系統、
  以及「一台被腐化時真跑會不會照樣指名」都還沒做。
- 量具白名單仍然只在 Mac 一台上算（366/368 上鏈，與 R452 的 366/371 對得起來：
  368 可轉 − 2 量具擋下 ＝ 366）。**量具跨機可攜性本輪沒有量。**
- 兩台共用同一份 `vacant/checks.py` 與同一份渲染器 ⇒ R449 §六 的
  「相關性沙箱故障未建模」**原封不動成立**。本輪量的是平台／直譯器差異，
  不是異質沙箱；渲染器有 bug，兩台會一致地錯，爭議率仍是 0。
- 候選是 r446 已歸檔的草稿。「真跑」指的是**執行**，不是生成。
- `pub_mac.json` 的 `git_dirty=True`：Mac 跑的時候工作樹有未追蹤的 `r453/` 產物
  正在寫入。承重檔案的 sha 逐一落盤且與 `7c4c14d` 相符，所以 dirty 不影響結論。
