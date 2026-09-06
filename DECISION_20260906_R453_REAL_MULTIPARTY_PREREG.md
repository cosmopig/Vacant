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
