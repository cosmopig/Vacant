# R531 預註冊：**公開題庫**上的「普通 agent」對「Vacant agent」配對比較

**編號** `R531`。**狀態：草稿，未發射。** 發射由人類或 Fable 的明示指令觸發。
本檔遵 Fable 2026-09-15 裁決九點（下稱「裁決」），
＋ 2026-09-16／09-17 兩則環境更新（1003 不准碰、R530 已於 09-17 收官、1004 空出）。

**它是誰的續作**：R530 問「開放做法的專案題上，有閘門／無閘門差多少」，
用的是**我們自己寫的 20 題**。人類 2026-09-15 的指令換掉的是**題目的來源**：

> 「部署兩個環境，一個是有包括 vacant 一個是普通的 agent，跑多方面的 agent
> 公開測試集，我不希望你做多餘的干涉，我希望你給他做好問題就給他自我放肆地跑，
> 最後比較結果就好。」

⇒ R531 ＝ **公開題庫** × **有閘門／無閘門** × **多種任務形狀** × **只比結果**。

---

## 〇、這個 run **不**回答什麼（收官不准借用）

1. **不**回答「Vacant 讓模型變聰明」。兩臂同模型、同 prompt、同工具、同預算、
   同題序；唯一差別是**宣告完成之後發生什麼**。量到的是閘門與回饋的差。
2. **不**產生可以跟排行榜比的數字。四族裡 `pbf`／`pbc` 的可見／隱藏是**我們切的**，
   分母不是官方分母；`pba`／`pbd` 的切法才是官方的（§二-3）。**這句話要跟著每一個數字。**
3. **不**回答「這套做法能推到真實工程專案」。能進來的公開題庫全部是
   「可在單一 Python 匯入面上被程式判對錯」的形狀。SWE-bench 那一族**進不來**，
   理由是這台機器的規格差一個數量級（13 G 磁碟／7 G RAM／無 Docker vs 官方
   要求的 120 GB／16 GB／Docker），不是「難裝」。
4. **不**回答「效果量是多少」。逐族 n ＝ 25／20／9–12／15，
   點估計的區間寬度是 ±20–35 pp 等級。**點估計不准被引用成數值宣稱。**
5. **不**是一個全新的問題。`pbf`／`pba` 都是**單函式題**＝R460／R529 的形狀；
   真正新的形狀只有 `pbc`（類別級、多方法、有狀態）與 `pbd`（stdin/stdout 腳本）。
   增量在**公開與外部可驗**，不在機制。**這一點是本檔最該被打的地方**（§七-1）。

---

## 一、沿用 R530 的部分（**引用，不重寫**）

裁決第 7 點：「能引用 R530 的就引用不要重寫。」下列各項**逐字沿用**
`DECISION_20260913_R530_OPEN_GOAL_WITH_WITHOUT_VACANT_PREREG.md`，本檔不複述、不修改：

| 項 | 出處 | R531 的差別 |
|---|---|---|
| 臂的定義 | R530 §二-2（`A-SOLO`／`A-GATE`） | **零差別**。`B-PLAIN` ＝ `A-SOLO`、`B-VACANT` ＝ `A-GATE`，就是同一段程式 |
| prompt 逐位元相同 | `openwork_arms.assert_arm_prompts_identical()` | 零差別。這是 **import 時就會炸**的斷言，不是承諾 |
| 預算 | R530 §二-3 的凍結 `OPENWORK_BUDGET` | 零差別（理由見 §四） |
| 工具面與協定 | R530 §二-4（單一 `run_bash`、原生 `tools`） | 零差別 |
| 沙箱與 E-9 | R530 §五-5／`ops/gain/r530/SANDBOX.md` | 零差別（`unshare` ＋ uid 65534） |
| 收據 | `ops/gain/r530/receipts.py` | 零差別 |
| V/GT 稽核紅線 | R530 §五-3 | 零差別 |
| 工作區生命週期／樹雜湊 | `openwork_arms.run_cell`、`wshash` | 零差別 |
| E-10（noop 格 > 20% ⇒ INVALID） | R530 §五-5 | 零差別 |
| `infra_void` 與 retry×4 | 鐵律 3 | 零差別 |

**程式碼改動：零。** 裁決第 1 點「不准改 `openwork_arms.py`／`sandbox.py`／
`receipts.py` 任何一行」——本 run 新增的檔案只有 `ops/gain/r531/`
（轉換器與佇列產生器）與本檔，**既有檔案一個位元組都沒動**。
唯一的例外是 `.gitignore` 加了三行（把產出的題庫樹排除在版控外，§三-4），
那不是程式碼。

⚠ **一處必須講明的沿用偏差**：`A-SOLO` 與 `A-GATE` **不是等預算比較**
（R530 §八-4 逐字）。人類問的就是「收第一份」對「有閘門」，
所以這個不對等是**題目本身**不是瑕疵。R530 用 `A-CONF` 當等預算對照，
R531 **沒有 `A-CONF`** ⇒ **本 run 分不開「閘門」與「多試幾次」**（§七-2）。

---

## 二、題庫（本檔自己要寫死的第一件事）

### 二-1　四族與最終題數

| 族 | 來源 | 任務形狀 | 目標 | **最終** | 授權 |
|---|---|---|---:|---:|---|
| `pbf` | BigCodeBench v0.1.4（stdlib-only；hard 分層） | 單函式 `task_func`，規格密 | 25 | **25** | Apache-2.0 |
| `pbc` | ClassEval | **類別級**，多方法、有狀態 | 20 | **20** | code MIT／**資料 CC BY-NC 4.0** |
| `pba` | LiveCodeBench v3（已落盤、sha 已釘） | 演算法推理 | 20 | **見 §二-5** | **不明確**（HF card 只寫 `cc`） |
| `pbd` | CodeContests test split | **stdin/stdout 腳本** | 15 | **15** | Apache-2.0（code）／CC BY-4.0（資料） |

**授權逐字記錄**（裁決第 3 點）：
- **ClassEval 是 CC BY-NC 4.0（非商用）**。我們是非商業學術與展覽用途，可用；
  **原始資料不得再散布**，轉出來的題庫樹也不進版控。
- **LCB 的授權不明確**：HF dataset card 的 YAML 只寫 `license: cc`，
  **沒有指明 BY／SA／NC**；題目本身抓自 LeetCode／AtCoder／Codeforces。
  照實記「授權不明確」，引用時要一起講。
- BigCodeBench 的 GitHub harness repo **已於 2026-07-20 封存（read-only）**；
  資料仍在 HF 且授權不變，但不會再修。
- `bigcodebench-hard` 的 card **沒有 license 欄位**，沿用母集的 Apache-2.0——
  **這是推定不是宣告**。

逐檔來源 URL、版本、sha256、題 id 清單全部在
`ops/gain/r531/manifest.json`（由 `ops/gain/r531/fetch_sources.py` 與
`build_bank.py` 產生）。**原始資料在 `.vacant-private/benchmarks/`，不進 repo。**

### 二-2　建置管線（四階段，全部零模型呼叫）

```
fetch_sources.py            抓 → 算 sha256 → .vacant-private/benchmarks/sources.json
build_bank.py select        選 2× 候選池 → manifest.json（釘死 id 清單）
build_bank.py render        渲染成 templates/ hidden/ gauge/（132 個候選）
ops/gain/r530/gauge.py      雙向量具（E-3）
build_bank.py finalize      **只留量具合格的**，每族取前 N → tasks_r531.json
```

**為什麼先選 2 倍再裁**：`TASK_FORMAT.md` §七 對 `gauge/` 的判準
（參考解必須全過、每個壞樁都必須被擋）**本來就是題目的合格條件**，
而公開題庫轉過來有多少會踩到這一條，**事前量不出來**。
⇒ 規則在看到「哪幾題」之前就寫死，而且它就是 E-3 既有的判準，
不是為了救某幾題發明的新標準。**淘汰名單逐題落盤**在
`manifest.families[*].finalize.dropped`，含每一題是哪一條不過。

### 二-3　V/GT 切法（裁決第 4 點：用題庫**自帶**的測試）

| 族 | 官方有 public/private 之分嗎 | 可見 | 隱藏 |
|---|---|---|---|
| `pbf` | **沒有** | `TestCases` 的前 **2** 個 `test_*` 方法（原始碼定義順序） | 其餘方法 |
| `pbc` | **沒有** | 前 ⌈k/3⌉ 個方法的 `test_code` | 其餘方法 ＋ 類別級測試類 |
| `pba` | **有，官方的** | `public_test_cases` | private（官方隱藏） |
| `pbd` | **有，官方的** | `public_tests` | `private_tests` ＋ `generated_tests`（取前 15，依輸入長度） |

**一條都不是我們寫的測試**——全部來自題庫自帶的測試碼，只做「切」與
「包成 `check_*()`」兩件事（`acceptance.py` 的執行語意）。

⚠ **兩個已知殘餘，寫在前面**：
1. `pbf`／`pbc` 的切法是我們切的 ⇒ **分母不是官方分母**，
   通過率**不可以跟 BigCodeBench／ClassEval 排行榜比**。
2. 切開時，類別層級的 `setUp`／`tearDown`／helper 必須進**兩份**
   （沒有 `setUp` 隱藏測試跑不起來）。如果作者把期望值寫成類別屬性，
   那個值會同時出現在兩邊 ⇒ **可見那份洩漏了一點隱藏的資訊**。
   這是結構性殘餘，不是 bug，**不准消音**。

### 二-4　逐族可見／隱藏條數（收官要逐族印，不合成）

見 `manifest.families[*].case_stats`。建置時量到的中位數：

| 族 | 可見中位 | 隱藏中位 |
|---|---:|---:|
| `pbf` | 2 | **3** |
| `pbc` | 10 | 13 |
| `pba` | 2 | 12 |
| `pbd` | 1 | 15 |

⚠ **`pbf` 的隱藏只有 3 條**（BigCodeBench 每題測試方法數中位 5）。
低於 R530 `TASK_FORMAT` 的 tight 10–16 與 loose 5–7。
裁決第 4 點已事前指定：**該族主指標用二元（全過才算過）**，
條數少影響的是「部分正確」的解析度，不是主指標本身。
**四族解析度不同，這是「不合成總分」的第二個理由**（第一個是形狀不同）。

### 二-5　`pba` 取不到 20 題（**要 Fable 點頭的第二件事**，裁決第 9 點）

LCB v3 有 189 題，但**只有 12 題有參考解**
（`ops/gain/data/lcb_v3_probe_solutions.json`）。E-3 的判準是
「量不到不是通過」：沒有 `good.py` 的題不計入覆蓋，`coverage_n != n_tasks` ⇒ 紅。
⇒ **這一族的硬上界是 12，不是 20。** 再經量具裁減後的最終題數見 §六 的預檢表。

裁決第 2 點寫「任何一族驗不過就**整族拿掉並回報**，不要替換成別的湊數」。
`pba` 不是「驗不過」，是「驗得過但湊不到 20」。
**本檔的處理：保留該族、把題數照實降到可得的數量、在收官報告逐字說明。**
要不要改判成整族拿掉，**由 Fable 決定，本檔不自己拍板。**

---

## 三、環境與紀律

### 三-1　只用 1004

R530 已於 **2026-09-17 收官（12/12 塊）**，1004 完全空著，
載著 `gemma-4-12b-it-qat`（context 262144／parallel 4／無 TTL）。
**1003 一格都不准碰**（人類在用 qwen 27B；vacant-dev 這個 VM 也跑在那台上）。
⇒ R531 的四塊**全部寫 1004 的端點**，四串。

### 三-2　執行機事實（實測，不是轉述）

Ubuntu 24.04／Python 3.12.3／**沒有 pip、沒有 ensurepip、沒有 docker、沒有 pytest**／
RAM 7 GiB／磁碟剩 13 G。第三方 Python 只有 `requests`／`yaml`／`cryptography`。
⇒ 題庫的四族全部限定在**標準庫跑得動**的子集，這是選題條件不是偏好。

### 三-3　「自我放肆地跑」的準確意思（裁決第 8 點）

**發射後任何人不得介入單格的執行。** agent 在沙箱裡想做什麼都可以：
72 輪工具呼叫、自己讀檔寫檔、自己跑 `run_tests.sh`。
**兩臂都可以自己跑測試**（`run_tests.sh` 就在工作區裡）；
差別只是**只有 `B-VACANT` 那一臂的結果構成閘門**。
`B-PLAIN` 就算自己跑了、看到紅的、還是宣告完成，**那份就是交付**。

**沒有網路是環境事實，不是限制條款**（裁決第 8 點逐字）：
沙箱 `network_isolated=true` 是 E-9 的發射前提，凍結的 `RULES` 也逐字告訴模型
「You are offline… no network, no package installation」。
⚠ 收官要一起講的理由：題庫是**公開的**，網路上到處是答案；
能上網就分不清「模型想出來的」與「抄來的」。

### 三-4　產出不進版控

`.gitignore` 新增三行，把 `ops/gain/r530/{templates,hidden,gauge}/pb*` 排除。
理由是授權（ClassEval CC BY-NC、LCB 不明確）＋ repo 紀律
（比照 EvalPlus 的 `.vacant-private/` 先例）。
**repo 裡只有轉換器與 `manifest.json`**；題庫可由 manifest 的釘死 id ＋ sha256
在任何一台重建，重建結果的 `_root_sha256` 必須逐位元相同。

---

## 四、預算（沿用凍結值，理由是資料不是偏好）

`OPENWORK_BUDGET` **一格都不改**。R530 完成的 120 格實測：
`stop_reason` ＝ `visible_pass` 63／`declared_done` 40／`attempts_exhausted` 8／
`gate_exhausted` 6／`budget_calls` 3，**零 `budget_wall`、零 `budget_tokens`**。

⇒ **這個預算在這個題型上沒有咬到。** 沒咬到的上限，調寬只會拉長牆鐘、
不會讓模型更自由。`max_context_tokens=200_000` 是唯一可能咬到的一項，
**留著，它撞到就是資料**。

---

## 五、主指標與檢定（裁決第 7 點：本檔自己要寫死）

### 五-1　主指標（**發射前指名，看資料之前**）

R530 §九-1 把「拒交的格子主指標讀哪一個」留白了。**R531 不留**：

1. **主指標（二元，逐題）**：`delivered_all_hidden_pass`
   ＝「有出貨」**且**「全部隱藏驗收通過」。拒交 ⇒ **0**。
   這是「客戶到底拿到能用的東西沒有」，也是公開題庫 `pass@1` 的慣例。
   `A-SOLO` 沒有拒交語意（`accepted` 恆 True）⇒ 它的值就是 `hidden_all_pass`。
2. **次指標（連續，逐題）**：`hidden_frac_delivered`（拒交 ⇒ 0.0）。
3. **佐證（不是指標）**：`hidden_frac`（不管有沒有出貨，最終工作區有多好）。
   它與 (1)(2) 的差**就是拒交的代價**——`B-VACANT` 拒交的那些格，
   工作區可能其實還不錯，那正是「這個機制丟掉了多少」的量。

### 五-2　檢定（**逐族分開，不合成總分**）

- **主指標** ⇒ **McNemar 精確檢定**（`vacant/research.py::mcnemar_*`），逐族。
- **次指標** ⇒ **Wilcoxon signed-rank 精確版**（`wilcoxon_signed_rank_exact`），逐族。
- **多重比較**：四族用 **Holm–Bonferroni** 校正（`holm_bonferroni`）。
- **逐 seed 算，不併 n**（R460／R529 的同一條）。本檔只發 seed-1；
  第二顆 seed 由人類看過實測 `wall_s` 再決定。
- ⚠ **不做 pooled 分析。** 四族的題數、難度、切法、隱藏條數都不同，
  合起來的那個數字沒有對應到任何一個問題。

### 五-3　四狀態（沿用 R530 的形狀，**門檻重寫**）

R530 的門檻是對**我們自己寫的 20 題**訂的。公開題庫的天花板不同
（污染 ⇒ 第一次就對的比例高；`pbd` ⇒ 地板效應），所以門檻要重訂：

| 狀態 | 判準（逐族） | 與 R530 不同在哪、為什麼 |
|---|---|---|
| **HIT** | McNemar 單邊 p < 0.05 **且** b/c 方向為 `B-VACANT` 優 | 同 R530 |
| **REPLICATED_ON_HARD** | 上者成立，**且**該族 `B-PLAIN` 的 `visible_all_pass` < 60% | R530 沒有這一格。加它是因為公開題庫的污染會把效果壓掉，**分得出「在難題上也成立」才有價值** |
| **UNRESOLVED** | 同號但 p ≥ 0.05，或配對差 b+c < 5 | R530 的 b+c 下界是對 20 題訂的；四族最小 n＝9 ⇒ **b+c < 5 直接判 UNRESOLVED 不解讀** |
| **NULL/INVALID** | E-10 紅（noop > 20%）、或 `infra_void` > 10%、或該族 b+c ＝ 0 | b+c＝0 ＝ 兩臂逐題完全相同 ⇒ **量具沒有解析度**，不是「沒有效果」 |

### 五-4　污染預檢（發射前擋門，裁決第 5 點）

每族抽 **3** 題共 **12** 題，**只跑 `A-SOLO` 一輪**，
量「第一次就通過全部可見測試」的比例＝ `A-SOLO` 的 `visible_all_pass` 佔比。

| 結果 | 動作 |
|---|---|
| **> 80%** | **停下來回報**。那代表閘門不會啟動，實驗量不到東西 |
| **60–80%** | 回報但可續 |
| **< 60%** | 直接發射 |

預檢跑在 `runs/_probe/` 底下、seed `g-r531-pre`，**不是證據、不進任何分析**。

---

## 六、時程與中止準則

### 六-1　規模（seed-1，只用 1004 四串）

R530 實測每格牆鐘中位數：`A-SOLO` **430 s**、`A-GATE` **591 s**；
逐塊（15 格／塊）2.4–7.6 h，**同台同題庫不同 seed 差 2.8×**。

```
牆鐘(h) = 題數 × 2 臂 × 每格中位秒數 ÷ 4 串 ÷ 3600
```

| 情境 | 每格中位 | 牆鐘 |
|---|---:|---:|
| 樂觀（R530 的 s1/s3 塊） | 500 s | **≈ 4.8 h** |
| 悲觀（R530 的 s2 塊） | 1,400 s | **≈ 13.4 h** |

（題數以 69 估；最終題數見 §二-5 與預檢後的回報。）

### 六-2　中止準則（**事前寫死，不准當場想**）

1. 污染預檢 > 80% ⇒ **不發射**，回報。
2. 任一族 `noop_cell` 比例 > 20% ⇒ 整個 run **INVALID**（E-10）。
3. `infra_void` > 10% ⇒ 停下來查後端，不補跑。
4. 牆鐘超過 **20 h** 仍未收完 ⇒ 停下來問人類，**不自行砍題或砍族**。
5. 1004 要讓給別的實驗 ⇒ **停在塊的邊界**（`RunLedger` 斷點續跑），不砍格。

---

## 七、Fable 該質疑的三點（本檔自己列，不等人來問）

**質疑 1：這是新問題，還是 R529 換一個題庫再跑一次？**
`pbf`（25 題）與 `pba`（≤12 題）**都是單函式題**＝R460 的形狀。
真正沒量過的形狀只有 `pbc`（類別級、多方法、有狀態）與 `pbd`（stdin/stdout）。
⇒ 如果 Fable 判「這是 R529 的第 N 次複製」，那 69 題裡有 37 題是在買已有的答案。
我的辯護是「增量在**公開與外部可驗**」——別人可以拿 BigCodeBench 自己重跑我們的分母。
**但那是展覽的價值不是實驗的價值**，而本 repo 的交付物是展覽（CLAUDE.md）。
這一點該由 Fable 裁，本檔不自己判。

**質疑 2：沒有 `A-CONF` ⇒ 分不開「閘門」與「多試幾次」。**
R530 §八-4 把 `A-GATE` vs `A-CONF` 指定為等預算的那一刀。R531 只有兩臂
（人類要的就是兩個環境），所以**贏了也說不出是閘門贏還是重試贏**。
加 `A-CONF` 的代價是牆鐘 ×1.5。**要不要加，是 Fable 的裁決不是我的選擇。**

**質疑 3：污染，而且它傷的是檢定力不是正確性。**
BigCodeBench 2024-06、ClassEval 2023-08、LCB v3 全部 ≤2024-08-10、
CodeContests 2022。gemma-4-12b 幾乎確定看過。
- 對**比較**：兩臂同模型同資料 ⇒ 污染不偏向任何一臂，**比較站得住**。
- 對**檢定力**：污染的題第一次就寫對 ⇒ **閘門根本不會啟動** ⇒ 配對差全是 0
  ⇒ McNemar 的 b/c 都掉。**污染不是讓結論變錯，是讓實驗量不到東西。**
- ⇒ §五-4 的預檢就是量這件事，而 §五-3 新增的 `REPLICATED_ON_HARD`
  就是為了把「在沒被污染的那半邊也成立」分出來。

---

## 八、發射前紀錄 F1–F7（裁決第 7 點；發射時逐項填，空著不准發射）

| # | 項 | 值 |
|---|---|---|
| **F1** | 程式碼 sha（`ops/gain/r531/*.py`、`ops/gain/r530/openwork_arms.py`） | 發射時填 |
| **F2** | 題庫 sha（`ops/gain/r531/bank_sha256.json` 的 `_root_sha256`） | 發射時填 |
| **F3** | 佇列 sha（`ops/gain/r531/queues/r531_main.json`） | 發射時填 |
| **F4** | 污染預檢結果（逐族 ＋ 合計） | 發射時填 |
| **F5** | 雙向量具結果（`coverage_n`／`stubs_blocked_n`／`n_tasks`） | 發射時填 |
| **F6** | 真後端冒煙 C1–C8 | 發射時填 |
| **F7** | 發射時間戳 ＋ 後端 `/v1/models` 探針 | 發射時填 |

---

## 九、區塊註冊（`run_r530.py::_check_decision` 會**整組逐字**比對）

沒有註冊的塊不准發射。下列各行由
`python3 ops/gain/r531/make_queue.py` 產生於
`ops/gain/r531/queues/REGISTRATION.txt`，**逐字貼入**：

<!-- BEGIN R531_REGISTRATION -->

### 九-1　污染預檢（`--out runs/_probe/…`，不是證據）

```
R530_BLOCK: g_r531_pre_1 tasks=pba_01_lcb2728,pbc_02_sseval12,pbd_03_concerts arms=A-SOLO seed=g-r531-pre endpoint=http://100.86.226.21:1234/v1/chat/completions
R530_BLOCK: g_r531_pre_2 tasks=pba_02_lcb2730,pbc_03_sseval15,pbf_01_ebench19 arms=A-SOLO seed=g-r531-pre endpoint=http://100.86.226.21:1234/v1/chat/completions
R530_BLOCK: g_r531_pre_3 tasks=pba_03_lcb2754,pbd_01_olitaire,pbf_02_bench273 arms=A-SOLO seed=g-r531-pre endpoint=http://100.86.226.21:1234/v1/chat/completions
R530_BLOCK: g_r531_pre_4 tasks=pbc_01_asseval0,pbd_02_utations,pbf_03_bench310 arms=A-SOLO seed=g-r531-pre endpoint=http://100.86.226.21:1234/v1/chat/completions
```

### 九-2　正式 run seed-1（1004 四串）

```
R530_BLOCK: g_r531_s1_1004_1 tasks=pba_01_lcb2728,pba_05_lcb2757,pba_09_lcb2792,pbc_01_asseval0,pbc_05_sseval21,pbc_11_sseval32,pbc_16_sseval41,pbc_23_sseval65,pbd_01_olitaire,pbd_07_eversion,pbd_13_keyboard,pbd_17_mparison,pbf_02_bench273,pbf_06_bench346,pbf_10_bench594,pbf_14_bench777,pbf_18_bench857,pbf_23_bench988 arms=A-SOLO,A-GATE seed=g-r531-s1 endpoint=http://100.86.226.21:1234/v1/chat/completions
R530_BLOCK: g_r531_s1_1004_2 tasks=pba_02_lcb2730,pba_06_lcb2779,pba_10_lcb2802,pbc_02_sseval12,pbc_06_sseval23,pbc_12_sseval33,pbc_17_sseval42,pbc_24_sseval73,pbd_02_utations,pbd_09_utergame,pbd_14_sshopper,pbd_18_emainder,pbf_03_bench310,pbf_07_bench368,pbf_11_bench720,pbf_15_bench785,pbf_20_bench928,pbf_24_bench990 arms=A-SOLO,A-GATE seed=g-r531-s1 endpoint=http://100.86.226.21:1234/v1/chat/completions
R530_BLOCK: g_r531_s1_1004_3 tasks=pba_03_lcb2754,pba_07_lcb2784,pba_11_lcb2808,pbc_03_sseval15,pbc_07_sseval24,pbc_13_sseval35,pbc_18_sseval49,pbc_25_sseval76,pbd_03_concerts,pbd_10_8bgroups,pbd_15_traction,pbd_19_ngthegap,pbf_04_bench324,pbf_08_bench454,pbf_12_bench765,pbf_16_bench800,pbf_21_bench963,pbf_25_ench1027 arms=A-SOLO,A-GATE seed=g-r531-s1 endpoint=http://100.86.226.21:1234/v1/chat/completions
R530_BLOCK: g_r531_s1_1004_4 tasks=pba_04_lcb2755,pba_08_lcb2786,pba_12_lcb2810,pbc_04_sseval18,pbc_09_asseval3,pbc_14_sseval36,pbc_20_sseval54,pbc_26_sseval77,pbd_06_faflower,pbd_11_1604aera,pbd_16_indarray,pbf_01_ebench19,pbf_05_bench326,pbf_09_bench592,pbf_13_bench771,pbf_17_bench854,pbf_22_bench971,pbf_26_ench1090 arms=A-SOLO,A-GATE seed=g-r531-s1 endpoint=http://100.86.226.21:1234/v1/chat/completions
```

<!-- END R531_REGISTRATION -->
