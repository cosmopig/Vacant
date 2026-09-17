# R532 預註冊：把 worker 換成 **qwen3.8-27b**，跑與 12B **完全相同**的五個題組

> **狀態：待凍結。** 本檔為發射前的預註冊正文。發射前必須：
> (1) Fable 核；(2) 人類簽字；(3) ledger 簽入；(4) §七-0 的兩處改碼落地（**本檔不是唯一阻擋項**，見 §十一）。
> 凍結之後 §一～§八 **一個字都不准改**；要改只能加**附錄**。

人類指示原文（2026-09-17）：「著手去規劃更強的本地模型跑 vacant 的效果，先規劃，
**題目用跟之前測小的一模一樣然後五個題組都測**，同時用兩台算力。」
Fable 裁決（2026-09-17）：模型＝`qwen/qwen3.8-27b`；**主 run 跑非 thinking**；不加 OFF5。
後端條件存證：`ops/gain/r532/probes/backend_conditions_20260917.json`（已 commit）。

---

## 〇、一句話

**把 worker 從 `gemma-4-12b-it-qat`（稠密 12B、Q4_0）換成 `qwen/qwen3.8-27b`（稠密 27B、Q4_K_M），
題庫、seed、offset 切法、臂、預算、V/GT 紅線、量具、收據全部沿用 R460／R529 的凍結值，
在五個題組共 836 題上重跑 OFF／CONFORM／HMIX，量「閘門與迴圈買到的東西，會不會因為單發變強而縮小」。**

**唯一的變因是模型。** 本檔在 §四 事前寫死：**預期會縮小**；
「若不縮小」與「若縮小到 0」各自代表什麼，也在看到資料之前寫在 §四-4／§四-5。

---

## 一、沿用了哪一份 DECISION 的哪一節（逐項）

**這一節是本 run 的骨幹。** 每一格右欄若與左欄不符，就不是「同一個實驗換模型」。

| 項 | R532 的值 | 沿用自 | 逐字相同？ |
|---|---|---|---|
| 題組 S0 | `lcb2`，120 題 | `DECISION_20260907_R460_HARNESS_PREREG.md` §二；`DECISION_20260911_R460R_FIVE_REPLICATIONS_PREREG.md` §一 | ✓ |
| 題組 S1／S2 | `lcb3` + `--bank-filter difficulty=medium`／`=hard`，135／54 題 | `DECISION_20260911_R529_CROSS_BANK_PREREG.md` §二-2（S1／S2） | ✓ |
| 題組 S3 | `humanevalplus`，156/164 題 | 同上 §二-2（S3）＋`gain_run.GAIN_HUMANEVAL_EXCLUSIONS`（8 題） | ✓ |
| 題組 S4 | `evalplus`，371/378 題 | 同上 §二-2（S4）＋`gain_run.GAIN_EVALPLUS_RESOURCE_EXCLUSIONS`（7 題） | ✓ |
| **offset 切法** | 43 塊，見 §二-2 | R460R §一（lcb2 六塊 ×20）＋ R529 §二-2（其餘 37 塊） | ✓ **逐塊 n 與 offset 與 12B 那輪逐位元相同** |
| seed | 四顆，**沿用不換**，見 §二-3 | R460 `g-r440-lcb2`；R529 `g-r529-lcb3`／`g-r529-he`／`g-r529-mbpp` | ✓ |
| 臂 | `OFF,CONFORM,HMIX` | R529 §二-4（三臂） | ✓ |
| 預算 | `max_calls 5`／`max_tokens 32,000`／`max_wall_s 900`／`sandbox_timeout_s 10`／`truncation_retries 1`／`doom_threshold 2` | `ops/gain/harness_arms.py::HARNESS_BUDGET`（R460 §二起未變） | ✓ |
| `--gauge-scope` | `bank` | R460R §一「與 R460 唯一的三處不同」第 2 列；R529 §二-3 | ✓ |
| `--probe-sample` | `0` | R460R §一；R529 §二-3 | ✓ |
| `--review-timeout-s` | `380` | R529 §二-3 | ✓ |
| `--retries` | `4` | 鐵律 3；R529 §二-3 | ✓ |
| `--record-bank-field` | 給 | R529 §二-3（一個佇列跨多集必須給） | ✓ |
| `--request-timeout-s` | **900** | R529 §二-3（Fable 裁決第 7 點） | ✓ **不動**，理由見 §六-4 |
| `--reasoning-effort` | **`none`** | `gain_run.py` 2026-09-13 起的預設；R529 稽核 §十三-1 授權 | ✓（**本 run 的核心對齊條件**，§五-1） |
| 退避 | `backoff_s 5.0`（5／10／20／40，`retries=4` ⇒ 睡 35 秒） | R529 稽核 §十三-2 | ✓ |
| V/GT 紅線 | `harness_vgt_audit.py --scope v2` 逐塊 CLEAN、violations 0；**另做不呼叫工具判準函式的獨立掃描** | R529 稽核 §六-1 的做法 | ✓ |
| 量具 | `probe_instrument`，兩個方向都要過，`n=0` 也算沒過 | `SPEC_GAIN.md` §5.2；`vacant/suitegauge.py` | ✓ |
| 收據 | 逐塊簽章鏈，收官要驗 | R460R 稽核 §三-3／R529 稽核 §十 | ✓ |
| agent pool | 六 persona、**單一模型**（`--models` 只給一個） | R460／R529 | ✓ |
| 鐵律 1（KS-1）／2（A4）／3（全 I/O 落盤）／4（記憶不跨臂） | 不動 | `CLAUDE.md` | ✓ |
| **worker 模型** | **`qwen3-27b`（`qwen/qwen3.8-27b`）** | — | ✗ **這是唯一改的東西** |
| **每槽 context** | ctx **65,536**／parallel **1** ⇒ **每槽 65,536** | 12B：ctx 262,144／parallel 4 ⇒ **每槽 65,536** | ✓ **逐項相同**（對 `max_tokens 32,000` 的餘裕同為 **2.05 倍**） |
| 總並行 | **2 串**（1003 一串、1004 一串） | 12B 那輪 4–8 串 | ✗ 降低（為了上一列而付的代價，§六、§八-2） |

---

## 二、要跑什麼

### 二-1　題組與釘值

| # | 題組 | `--bank` | `--bank-filter` | n | 檔案 | sha256 |
|---|---|---|---|---:|---|---|
| S0 | LCB v2 | `lcb2` | — | **120** | `ops/gain/data/lcb_bank_v2.jsonl` | `b98f027213e2469a0a41bed813d99f029d3d6e2fac64e0fa18887c42c865b9ba` |
| S1 | LCB v3 medium | `lcb3` | `difficulty=medium` | **135** | `ops/gain/data/lcb_bank_v3.jsonl` | `bd3dffebb1b16bc7c92ead59c82753597a8197f9927d4f758d42e6c28b129293` |
| S2 | LCB v3 hard | `lcb3` | `difficulty=hard` | **54** | 同上 | 同上 |
| S3 | HumanEval+ | `humanevalplus` | — | **156**／164 | `.vacant-private/evalplus/HumanEvalPlus-v0.1.10.jsonl.gz` | `codebench.EVALPLUS_HUMANEVAL_PLUS_SHA256`（`272720b90ac37550…`） |
| S4 | MBPP+ | `evalplus` | — | **371**／378 | `.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz` | `af43697e8791c4c149bdfd6b489d8b5412507551ac20e28a439f650b8225db63` |
| | **合計** | | | **836** | | |

排除規則**由 `gain_run.py` 寫死、本檔不得修改**：`GAIN_HUMANEVAL_EXCLUSIONS` 8 題、
`GAIN_EVALPLUS_RESOURCE_EXCLUSIONS` 7 題。
LCB v2 的已知壞題 `lcb_3613`／`lcb_3763` **照舊留在題庫裡**（與 R460／R460R 相同，
不得為 R532 移除——移了就不是同一批題）。

### 二-2　43 塊的逐塊註冊行（發射器**整組**比對，少一格就發不出去）

**836 題 × 3 臂 ＝ 2,508 格。** 每塊的 `n`／`offset` 與 12B 那輪逐位元相同。

```
R532_BLOCK: g_r532_lcb2_a1 bank=lcb2 filter=- n=20 offset=0 seed=g-r440-lcb2
R532_BLOCK: g_r532_lcb2_a2 bank=lcb2 filter=- n=20 offset=20 seed=g-r440-lcb2
R532_BLOCK: g_r532_lcb2_a3 bank=lcb2 filter=- n=20 offset=40 seed=g-r440-lcb2
R532_BLOCK: g_r532_lcb2_a4 bank=lcb2 filter=- n=20 offset=60 seed=g-r440-lcb2
R532_BLOCK: g_r532_lcb2_a5 bank=lcb2 filter=- n=20 offset=80 seed=g-r440-lcb2
R532_BLOCK: g_r532_lcb2_a6 bank=lcb2 filter=- n=20 offset=100 seed=g-r440-lcb2
R532_BLOCK: g_r532_lcb3m_a1 bank=lcb3 filter=difficulty=medium n=20 offset=0 seed=g-r529-lcb3
R532_BLOCK: g_r532_lcb3m_a2 bank=lcb3 filter=difficulty=medium n=20 offset=20 seed=g-r529-lcb3
R532_BLOCK: g_r532_lcb3m_a3 bank=lcb3 filter=difficulty=medium n=20 offset=40 seed=g-r529-lcb3
R532_BLOCK: g_r532_lcb3m_a4 bank=lcb3 filter=difficulty=medium n=20 offset=60 seed=g-r529-lcb3
R532_BLOCK: g_r532_lcb3m_a5 bank=lcb3 filter=difficulty=medium n=20 offset=80 seed=g-r529-lcb3
R532_BLOCK: g_r532_lcb3m_a6 bank=lcb3 filter=difficulty=medium n=20 offset=100 seed=g-r529-lcb3
R532_BLOCK: g_r532_lcb3m_a7 bank=lcb3 filter=difficulty=medium n=15 offset=120 seed=g-r529-lcb3
R532_BLOCK: g_r532_lcb3h_a1 bank=lcb3 filter=difficulty=hard n=20 offset=0 seed=g-r529-lcb3
R532_BLOCK: g_r532_lcb3h_a2 bank=lcb3 filter=difficulty=hard n=20 offset=20 seed=g-r529-lcb3
R532_BLOCK: g_r532_lcb3h_a3 bank=lcb3 filter=difficulty=hard n=14 offset=40 seed=g-r529-lcb3
R532_BLOCK: g_r532_hep_a1 bank=humanevalplus filter=- n=20 offset=0 seed=g-r529-he
R532_BLOCK: g_r532_hep_a2 bank=humanevalplus filter=- n=20 offset=20 seed=g-r529-he
R532_BLOCK: g_r532_hep_a3 bank=humanevalplus filter=- n=20 offset=40 seed=g-r529-he
R532_BLOCK: g_r532_hep_a4 bank=humanevalplus filter=- n=20 offset=60 seed=g-r529-he
R532_BLOCK: g_r532_hep_a5 bank=humanevalplus filter=- n=20 offset=80 seed=g-r529-he
R532_BLOCK: g_r532_hep_a6 bank=humanevalplus filter=- n=20 offset=100 seed=g-r529-he
R532_BLOCK: g_r532_hep_a7 bank=humanevalplus filter=- n=20 offset=120 seed=g-r529-he
R532_BLOCK: g_r532_hep_a8 bank=humanevalplus filter=- n=16 offset=140 seed=g-r529-he
R532_BLOCK: g_r532_mbpp_a1 bank=evalplus filter=- n=20 offset=0 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a2 bank=evalplus filter=- n=20 offset=20 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a3 bank=evalplus filter=- n=20 offset=40 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a4 bank=evalplus filter=- n=20 offset=60 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a5 bank=evalplus filter=- n=20 offset=80 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a6 bank=evalplus filter=- n=20 offset=100 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a7 bank=evalplus filter=- n=20 offset=120 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a8 bank=evalplus filter=- n=20 offset=140 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a9 bank=evalplus filter=- n=20 offset=160 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a10 bank=evalplus filter=- n=20 offset=180 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a11 bank=evalplus filter=- n=20 offset=200 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a12 bank=evalplus filter=- n=20 offset=220 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a13 bank=evalplus filter=- n=20 offset=240 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a14 bank=evalplus filter=- n=20 offset=260 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a15 bank=evalplus filter=- n=20 offset=280 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a16 bank=evalplus filter=- n=20 offset=300 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a17 bank=evalplus filter=- n=20 offset=320 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a18 bank=evalplus filter=- n=20 offset=340 seed=g-r529-mbpp
R532_BLOCK: g_r532_mbpp_a19 bank=evalplus filter=- n=11 offset=360 seed=g-r529-mbpp
```

**43 個 run 目錄**（R440G 閘門要它們逐字出現在本檔）：
`runs/g_r532_lcb2_a1`、`runs/g_r532_lcb2_a2`、`runs/g_r532_lcb2_a3`、`runs/g_r532_lcb2_a4`、`runs/g_r532_lcb2_a5`、`runs/g_r532_lcb2_a6`、
`runs/g_r532_lcb3m_a1`、`runs/g_r532_lcb3m_a2`、`runs/g_r532_lcb3m_a3`、`runs/g_r532_lcb3m_a4`、`runs/g_r532_lcb3m_a5`、`runs/g_r532_lcb3m_a6`、`runs/g_r532_lcb3m_a7`、
`runs/g_r532_lcb3h_a1`、`runs/g_r532_lcb3h_a2`、`runs/g_r532_lcb3h_a3`、
`runs/g_r532_hep_a1`、`runs/g_r532_hep_a2`、`runs/g_r532_hep_a3`、`runs/g_r532_hep_a4`、`runs/g_r532_hep_a5`、`runs/g_r532_hep_a6`、`runs/g_r532_hep_a7`、`runs/g_r532_hep_a8`、
`runs/g_r532_mbpp_a1`、`runs/g_r532_mbpp_a2`、`runs/g_r532_mbpp_a3`、`runs/g_r532_mbpp_a4`、`runs/g_r532_mbpp_a5`、`runs/g_r532_mbpp_a6`、`runs/g_r532_mbpp_a7`、`runs/g_r532_mbpp_a8`、`runs/g_r532_mbpp_a9`、`runs/g_r532_mbpp_a10`、`runs/g_r532_mbpp_a11`、`runs/g_r532_mbpp_a12`、`runs/g_r532_mbpp_a13`、`runs/g_r532_mbpp_a14`、`runs/g_r532_mbpp_a15`、`runs/g_r532_mbpp_a16`、`runs/g_r532_mbpp_a17`、`runs/g_r532_mbpp_a18`、`runs/g_r532_mbpp_a19`

⚠ **為什麼是 43 塊而不是 12 塊。** 塊的大小不是排程參數，它是**實驗條件**：
`load_tasks` 先依 seed 決定性排序、再 `ts[offset:offset+n]` ⇒ 改 `n` 就改了「哪 20 題被分在一起」，
也就改了「哪一批題落在哪一台後端」。**§一 已把「offset 切法沿用 12B 那輪」寫成不可動的一列**，
所以塊數只能是 43。副作用（preflight 重複 43 次）已計入 §六 的時程。

### 二-3　seed：**四顆全部沿用**（授權重用，不是 `NONE`）

**先講一個容易被寫錯的事實**：五個題組**每一組都是整批取用**
（lcb2 20×6＝120＝全部、lcb3m 135＝全部、lcb3h 54＝全部、HE+ 156＝全部、MBPP+ 371＝全部）
⇒ **seed 不抽樣，只決定題序與分塊**。「題目一模一樣」在任何 seed 下都成立；
沿用 seed 買到的是 §二-4 那條**更嚴格的**不變量。

發射器逐字對釘（**要在 vacant-dev 上掃**，見 §五-4）：

```
SEED_AUTHORIZED_SET: g-r440-lcb2 <- runs/g_r447_conform_lcb2, runs/g_r460_harness_lcb2_a1, runs/g_r460_harness_lcb2_a2, runs/g_r460_harness_lcb2_a3, runs/g_r460_harness_lcb2_b1, runs/g_r460_harness_lcb2_b2, runs/g_r460_harness_lcb2_b3
SEED_AUTHORIZED_SET: g-r529-lcb3 <- runs/g_r529_lcb3h_a1, runs/g_r529_lcb3h_a2, runs/g_r529_lcb3h_a3, runs/g_r529_lcb3m_a1, runs/g_r529_lcb3m_a2, runs/g_r529_lcb3m_a3, runs/g_r529_lcb3m_a4, runs/g_r529_lcb3m_a5, runs/g_r529_lcb3m_a6, runs/g_r529_lcb3m_a7
SEED_AUTHORIZED_SET: g-r529-he <- runs/g_r529_hep_a1, runs/g_r529_hep_a2, runs/g_r529_hep_a3, runs/g_r529_hep_a4, runs/g_r529_hep_a5, runs/g_r529_hep_a6, runs/g_r529_hep_a7, runs/g_r529_hep_a8
SEED_AUTHORIZED_SET: g-r529-mbpp <- runs/g_r529_mbpp_a1, runs/g_r529_mbpp_a2, runs/g_r529_mbpp_a3, runs/g_r529_mbpp_a4, runs/g_r529_mbpp_a5, runs/g_r529_mbpp_a6, runs/g_r529_mbpp_a7, runs/g_r529_mbpp_a8, runs/g_r529_mbpp_a9, runs/g_r529_mbpp_a10, runs/g_r529_mbpp_a11, runs/g_r529_mbpp_a12, runs/g_r529_mbpp_a13, runs/g_r529_mbpp_a14, runs/g_r529_mbpp_a15, runs/g_r529_mbpp_a16, runs/g_r529_mbpp_a17, runs/g_r529_mbpp_a18, runs/g_r529_mbpp_a19
```

（本機 2026-09-17 實掃 117 個 `runs/*/summary.json` 的結果，逐字如上。
本機掃過**不算數**，vacant-dev 上的集合才是閘門讀的那一個。）

### 二-4　**可驗的不變量：persona 指派與 12B 那輪逐格相同**

`gain_run.py:1804` 每一臂各自 `random.Random(f"{seed}:{arm}")`——**不是全域共用**；
三臂的抽樣次數**逐題固定、與模型輸出無關**：

| 臂 | 每題抽幾次 | 位置 |
|---|---:|---|
| `OFF` | 1 | `gain_run.py:434` `a = rng.choice(agents)` |
| `CONFORM` | 5（一次抽滿，不因早停而少抽） | `gain_run.py:728` `assigned = [rng.choice(agents) for _ in range(k)]` |
| `HMIX` | 1（一題一個 worker，整題所有輪次同一個） | `harness_arms.py:811` `worker = rng.choice(agents)` |

⇒ **同 seed ＋ 同 bank ＋ 同 offset ⇒ 每一格 (task, arm) 的 persona 與 R460／R529 逐格相同，
與模型是哪一顆無關，也與臂清單是三臂還是六臂無關**（rng 是 per-arm 的，lcb2 那輪的
OFF5／HPI／HOC 不會污染 OFF／CONFORM／HMIX 的抽樣序列）。

這條是發射前的擋門 E-14（§五-5），**零模型呼叫、可離線重放**。

### 二-5　逐塊指令與**發射方式**（`<...>` 取 §二-2，其餘 43 塊完全相同）

**發射方式（Fable 2026-09-17 裁決）**：不使用 `schedule_queue.py`。理由：其 `QUEUE_SLOTS` 順序與
`PER_HOST_CAP=4` 是 R529 的凍結碼，改它會動到別的實驗；而本輪每台 `parallel=1` ⇒ 全域僅 2 串。
改為**直接發 runner**（與 R530 AMEND2-G 相同的做法）：一支迴圈，**每台同時只跑一塊**，
一塊收完才發下一塊；1003 與 1004 各自一條序列，43 塊依 §二-2 的順序交替分配。
逐塊的 `R532_BLOCK:` 註冊行仍由 `gain_run.py` 對本檔做整組比對，少一格就發不出去。

```
python3 ops/gain/gain_run.py \
  --out runs/<NAME> --n <N> --offset <OFFSET> \
  --decision DECISION_20260917_R532_STRONGER_MODEL_PREREG.md \
  --seed <SEED> --arms OFF,CONFORM,HMIX --bank <BANK> <--bank-filter <FILTER>> \
  --record-bank-field --models qwen3-27b \
  --reasoning-effort none \
  --probe-sample 0 --gauge-scope bank \
  --request-timeout-s 900 --review-timeout-s 380 --retries 4
```

---

## 三、臂

| 臂 | 是什麼 | 為什麼在 |
|---|---|---|
| `OFF` | 單發，1 通呼叫 | 錨。「模型本身有多強」就是這一格 |
| `CONFORM` | 同預算重抽（最多五份，跑可見驗收，不回饋） | **同預算下最強的選擇規則**；Δ_C 的對照物 |
| `HMIX` | 回饋迴圈（把可見驗收的失敗原文貼回去讓它改） | 待測的東西 |

與 R529 逐字相同（`--arms OFF,CONFORM,HMIX`）⇒ S1／S2／S3／S4 可與 R529 **逐臂直接對照**；
S0 與 R460／R460R 對照時只取那三欄。

**OFF5 的成本差（Fable 已裁不加）**：加它 ⇒ 格數 2,508 → 3,344（+33%），
token／題 16.4k → 31.3k（**+91%**，`OFF5` 一臂 14,954 token/題就比其他三臂加起來還貴），
牆鐘約 ×1.9。買到的只有「投票 vs 驗收會不會隨模型變強而反轉」，
而 `harness.majority_vote_loses_to_gate` 已經是 `unresolved`（R460R 5/5 同號、3/5 顯著），
再加一個資料點不會讓它收斂。**不加。**

---

## 四、事前預測——**在看到任何資料之前寫死**

### 四-0　錨（12B 的實測值）

⚠ **錨要用「非 thinking」那一半。** R529 稽核 §十一 已證實 S1–S4 的絕對值是
1003（thinking）與 1004（非 thinking）的混合物。R532 跑非 thinking，
可比的錨是 **1004 那一半**；兩組都列，預測用 1004 那一組。

| 題組 | 對照 | 口徑 | OFF | CONFORM | HMIX | Δ_C | Δ_O |
|---|---|---|---:|---:|---:|---:|---:|
| **S0 LCB v2** | R460 主 run | 1004，非 thinking | 58.33 | 70.83 | 84.17 | **+13.33** | +25.83 |
| S0（複製帶） | R460R r1–r5 | 1004，非 thinking | 51.3–57.5 | 70.8–75.0 | 73.3–77.5 | +0.83～+5.83 | +18.3～+22.5 |
| **S1 LCB v3 med** | R529 | **1004 only**（60 題） | 76.7 | 85.0 | 86.7 | +1.7 | +10.0 |
| S1（混合 135） | R529 | 兩台 | 85.19 | 92.59 | 93.33 | +0.74 | +8.15 |
| **S2 LCB v3 hard** | R529 | **1004 only**（20 題） | 65.0 | 75.0 | 75.0 | 0.0 | +10.0 |
| S2（混合 54） | R529 | 兩台 | 70.37 | 75.93 | 79.63 | +3.70 | +9.26 |
| **S3 HumanEval+** | R529 | **1004 only**（56 題） | 75.0 | 94.6 | 96.4 | +1.8 | +21.4 |
| S3（混合 156） | R529 | 兩台 | 82.69 | 94.23 | 94.87 | +0.64 | +12.18 |
| **S4 MBPP+** | R529 | **1004 only**（140 題） | 73.6 | 79.3 | 80.0 | +0.7 | +6.4 |
| S4（混合 371） | R529 | 兩台 | 74.66 | 79.51 | 80.59 | +1.08 | +5.93 |

（1004-only 那幾列來自 R529 稽核 §十一 的逐後端表，是**描述性** b−c，**不是檢定**。）

### 四-1　核心預測：**增益會縮小**

機制：CONFORM 與 HMIX 的增益都建立在「單發會錯」。單發正確率上升 ⇒ 可被重抽救回的題變少
⇒ 可被迴圈救回的題更少（迴圈只改**可見驗收沒過**的候選——R529 §十 的 D5 歸因：四集 31/0，只救不傷）。
⇒ **Δ_O 與 Δ_C 都應縮小，Δ_C 縮得更多**（它本來就只剩個位數）。

| # | 預測 | 仲裁欄位 |
|---|---|---|
| **P-1** | 五個題組的 OFF 交付率**全部上升**，且至少 4/5 上升 ≥ +5 pp | `per_set.<s>.per_arm.OFF.correct_delivery_rate` |
| **P-2** | 五個題組的 Δ_O（HMIX−OFF）**全部縮小**（小於 §四-0 的 1004-only 值），但**仍全部 > 0** | `per_set.<s>.paired.HMIX_vs_OFF.delta_pp` |
| **P-3** | 五個題組的 Δ_C **全部 ≤ +3.0 pp**（點估計） | `per_set.<s>.paired.HMIX_vs_CONFORM.delta_pp` |
| **P-4** | 合併 Δ_C 的 95% 區間**上界 < +5.0 pp** | `primary.HMIX_vs_CONFORM.ci95_hi_pp` |
| **P-5** | 合併 Δ_C 的 Holm `p_adj` **不顯著**（≥ 0.05） | `primary.HMIX_vs_CONFORM.p_adj` |
| **P-6** | 合併 Δ_O 的 Holm `p_adj` **仍顯著**（< 0.05） | `primary.HMIX_vs_OFF.p_adj` |
| **P-7** | CONFORM−OFF 五集**全部 > 0**，且至少 3/5 小於對照值（閘門的增益也縮小） | `per_set.<s>.paired.CONFORM_vs_OFF.delta_pp` |
| **P-8** | 假交付（accepted 但隱藏測資不過）五集**全部下降** | `per_set.<s>.per_arm.<arm>.false_delivery_pp` |
| **P-9** | `token_per_correct` 五集**全部下降**（分母變大） | `per_set.<s>.tokens.<arm>.tpc_incl_void` |
| **P-10** | **context／預算相關的拒交上升**：至少一個題組的 HMIX `budget_tokens` ＋ context 錯誤合計 ≥ 5 件（12B 那輪每臂 ≤2 件） | `per_set.<s>.per_arm.<arm>.reject_reasons` |
| **P-11** | 逐塊 `infra_void` ≤ 5% | `arms.<arm>.infra_void` |

**逐題組的區間預測**（點估計的 90% 主觀區間；錨＝§四-0 的 1004-only 欄）：

| 題組 | OFF 預期（錨） | CONFORM 預期（錨） | HMIX 預期（錨） | **Δ_C 預期**（錨） | **Δ_O 預期**（錨） |
|---|---|---|---|---|---|
| S0 LCB v2 (120) | 68–82（51–58） | 80–90（71–75） | 82–92（73–78） | **0 ～ +4**（+0.8～+5.8） | **+8 ～ +18**（+18～+23） |
| S1 LCB v3 med (135) | 86–95（77） | 92–98（85） | 93–98（87） | **0 ～ +2**（+1.7） | **+2 ～ +8**（+10） |
| S2 LCB v3 hard (54) | 74–88（65） | 81–93（75） | 83–94（75） | **0 ～ +4**（0.0） | **+3 ～ +12**（+10） |
| S3 HumanEval+ (156) | 88–96（75） | 94–99（95） | 95–99（96） | **−1 ～ +2**（+1.8） | **+2 ～ +8**（+21） |
| S4 MBPP+ (371) | 82–91（74） | 87–94（79） | 88–95（80） | **0 ～ +3**（+0.7） | **+3 ～ +10**（+6） |

⚠ **S1 與 S3 的 Δ_C 幾乎沒有鑑別力，這件事現在就寫下來。**
對照的 CONFORM 已在 85–95%，27B 上去之後預期 92–99% ⇒ **天花板讓「沒縮小」在算術上幾乎不可能發生**。
**Δ_C 這個問題真正有牙齒的只有 S0（lcb2）、S2（lcb3 hard）、S4（MBPP+）三集。**
收官時不准拿 S1／S3 的小數字當「增益消失的證據」。

### 四-2　主指標、家族、Holm、四狀態（沿用 R529 §六 的形狀）

- **主指標（家族 2，Holm）**：跨五個題組**分層合併**的精確配對 McNemar
  ——`HMIX − CONFORM` 與 `HMIX − OFF`。
- **次指標**：逐題組的配對 McNemar（未校正雙尾），**只當描述**，區間不做多重比較調整。
- **Wilcoxon signed-rank**（`vacant/research.py` 的預註冊函式）用在 token／題的逐題配對，
  **不是**交付率的主指標。
- **四狀態**（比照 R529 §三，不可與 R460 §六-(4) 的同名狀態互引——本 run 無 OFF5 臂）：

| 狀態 | 條件 | 可以講的話 |
|---|---|---|
| `INVALID` | §五 任一擋門紅（含 V/GT 有 violation、E-11 事後發現 reasoning ≠ 0、E-13 context 偏斜） | 「這個 run 不當資料用」 |
| `EFFECTIVE` | 兩個主指標 Holm 後**都**成立，**且**合併 `tpc` HMIX ≤ CONFORM | 「在 836 題五個題組上，用 27B 本地模型，迴圈比同預算重抽多交付 N pp」＋**必帶** §八 全部誠實邊界 |
| `RULED_OUT` | `primary.HMIX_vs_CONFORM.ci95_hi_pp` < **+2.0 pp** | 「排除了 ≥+2 pp 的實務增益」。**這是結論不是失敗**（沿用 R445 對 OFF5 的用法） |
| `INCONCLUSIVE` | 其餘 | 「**沒量出來**，不是沒有差異」——必須同時報 `mde_at_n_pp` 與事前檢定力 |

⚠ `RULED_OUT` 的線訂在 **+2.0 pp** 而不是 R460 的 +10 pp：R460R 五次＋R529 四集
九個資料點的 Δ_C 全部落在 +0.6～+5.8，+10 pp 這條線在本輪已經沒有鑑別力。
**這條線在發射前訂死，不准看完資料再改。**

### 四-3　**不得與 12B 併 n**（寫死）

1. **主指標一律是 R532 自己 run 內的配對比較**。
2. **跨模型只做「逐題庫的逐臂對照與差值描述」**：對每一個 (題組, 臂) 並列
   R532 與 12B 對照 run 的交付率，寫差值。**這個差值不是檢定**——它跨 run、跨時間、
   跨後端負載、跨 context 大小，混淆項多到 p 值沒有意義。
   每一**列**必須帶 `not_a_test: true`（R529 §十三-3 的先例：note 寫在區塊層級，
   被複製走的時候會掉）。
3. **不准**把 R532 的 836 題與 12B 的 836 題合併成 1,672 題的 n。
4. **不准**把五個題組的點估計平均成一個數。
5. **不准**只挑對某個結論有利的題組講。
6. **不准**用 R532 的結果去改 R460／R460R／R529 的既有裁決——那是不同的模型、另一個實驗。

### 四-4　**「若增益不縮小」代表什麼**（事前寫死）

判準：**S0／S2／S4 三集裡至少兩集的 Δ_C ≥ +3.0 pp，且合併 Δ_C 的 95% 區間下界 > 0。**

解釋：**迴圈買到的東西與「單發有多準」是正交的。**
迴圈救的不是「模型不會寫」，而是「模型不知道自己寫錯了」——
而「知不知道自己錯」是**校準**問題不是**能力**問題，它不隨模型變強而自動變好
（`CONCLUSION_20260830_G_EXPERIMENT.md` 已經在評審角色上看過同一個形狀：
`qwen3.6-35b-a3b` 解一層包裝後 A=0.667 比 gemma 的 0.531 **更準**，
但它 95.5% 的票投 PASS——準確率高、校準壞掉）。

若成立，**這是本專題到目前為止最強的一個結果**：主張從「小模型需要拐杖」
升級成「可究責層買到的是模型本身買不到的東西」。

⚠ 即使成立，**不准**寫成「迴圈在強模型上也有效」這種一般化句子。
可以寫的是：「在 <那兩集> 上，把 worker 換成單發強 N pp 的模型之後，
迴圈對同預算重抽的優勢仍有 +X pp。」範圍限定在題組與這一顆模型。

### 四-5　**「若縮小到 0」代表什麼**（事前寫死）

判準：**五集的 Δ_C 全部 ≤ +1.0 pp，或合併 Δ_C 的 95% 區間上界 < +2.0 pp（＝`RULED_OUT`）。**

解釋：**迴圈的邊際價值是小模型現象。** 在單發已經夠強的地方，
「跑驗收 → 換一份」就把能救的都救完了，把失敗原文貼回去讓它改**多買不到東西**。

這**不是**「Vacant 沒用」——`CONFORM − OFF`（閘門＋重抽）預期仍是 +5～+15 pp，
機制照樣在。要改的是**展場與官網的措辭**：

- 台上的主角不再是「迴圈」，是**可執行驗收閘門**。
- `harness.hmix_loop_beats_resample_same_budget`：`unresolved` → **`ruled_out_at_this_scale`**
  （「在 12B 與 27B 兩個量級、五個題組上，排除了 ≥+2 pp 的實務增益」）。
- 展件的雙世界對照仍然成立（它演的是閘門與收據，不是迴圈）。

### 四-6　宣稱句規則（逐字，收官照抄）

- **主指標 Holm 後成立** ⇒ 可以寫「在 836 題五個題組上，迴圈對同預算重抽的優勢為 +X pp」，
  **同一段必須寫出**：逐集五個數字、§四-1 的 S1／S3 天花板限制、§八 的全部誠實邊界、
  以及「這是一次 run，不是複製」。
- **未成立** ⇒ **逐集照實列**。不准寫「多數支持」「方向一致」「趨勢明顯」，
  也不准寫「複製失敗」「效果消失」「等價」「打平」「迴圈沒用」。
- 跨模型的差值一律帶「這不是檢定」。
- `R440P` 前提句照舊：整件事建立在「需求可被編譯成可執行的驗收測資」。

---

## 五、發射前擋門（**任何一條紅就不准發射**）

### 五-0　E-11：推理模式（**已通過，證據落盤**）

證據：`ops/gain/r532/probes/backend_conditions_20260917.json`。

| 主機 | 請求 | `reasoning_tokens` | `completion_tokens` |
|---|---|---:|---:|
| 1003 | `reasoning_effort=none`，**不帶 tools** | **0** | 2 |
| 1003 | `reasoning_effort=none`，**帶 tools** | **0** | 30（`finish=tool_calls`） |
| 1003 | **不送旗標（對照組）** | **32** | 36 |
| 1004 | `reasoning_effort=none`，**不帶 tools** | **0** | 2 |
| 1004 | `reasoning_effort=none`，**帶 tools** | **0** | 30（`finish=tool_calls`） |
| 1004 | **不送旗標（對照組）** | **32** | 36 |

**換 context／parallel 之後兩台重驗**（`reasoning_probes.after_context_change`，
2026-09-17T03:12:24Z，即 §五-2 那次重載之後）：

| 主機 | 請求 | `reasoning_tokens` | `completion_tokens` |
|---|---|---:|---:|
| 1003 | `reasoning_effort=none` | **0** | 2 |
| 1003 | 不送旗標（對照組） | **32** | 36 |
| 1004 | `reasoning_effort=none` | **0** | 2 |
| 1004 | 不送旗標（對照組） | **32** | 36 |

**四格與換之前逐格相同** ⇒ 換 context 與 parallel 沒有改變推論模式。

**對照組是這張表的關鍵**：不送旗標時 `reasoning_tokens=32`
⇒ 這顆模型**預設真的會 thinking**，`0` 是旗標起了作用，**不是欄位缺失或後端不回報**。
R529 §十一 的坑（同一顆 gguf 兩種推論條件）在本 run 事前就堵住了。

⚠ **誠實邊界三條，現在就寫**：
1. **本 run 的請求路徑從來不送 `tools`。** `brain_cline.generate()`／`chat()` 的 body key 集合
   恰為 `{model, messages, temperature, stream}`（＋選配 `max_tokens`、`reasoning_effort`）。
   帶 tools 那兩格驗的是「關掉 thinking 這個結論不脆弱」，**不是**「我們驗過 tool 路徑」。
2. **探針是短輸出（2–36 token）。** 它證明不了長輸出時不會中途進 thinking。
   ⇒ **收官必做的事後查核（E-11-post）**：掃全部 `calls.jsonl`，
   `reasoning_tokens > 0` 的呼叫占比**必須是 0.0%**；**任何一通 > 0 ⇒ 狀態 `INVALID`**，
   並逐塊印出來（比照 `analyze_r460r.py` 的 `inference_mode` 欄）。
3. `probe_reasoning_tokens` 是**探針那一通**量到的，不保證整塊同一個推論模式
   （模型中途被重載就可能變）；`ttlMs` 必須是 `null`（§五-3）就是為了堵這一條。

### 五-1　E-12：後端條件逐塊落盤（`backend_meta.json`）

逐塊必須寫下、且**兩台必須逐項相同**：

| 欄位 | 值 |
|---|---|
| `model` / `identifier` | `qwen3-27b`（`modelKey` = `qwen/qwen3.8-27b`） |
| `arch` / `params` / `quantization` | `qwen35` / 27B dense / `Q4_K_M` (4 bit) |
| `sizeBytes` | 17,742,040,464 |
| `gguf_sha256` | **發射前現量，兩台必須逐位元相同**（12B 那輪是 `faff1a63…561f1`） |
| `context_length` / `parallel` / `per_slot_context` | 65,536 / **1** / **65,536**（＝12B 那輪的每槽值） |
| `headroom_vs_max_tokens_32000` | **2.048**（12B 那輪同值） |
| `gpu` / `ttlMs` | `max` / **`null`** |
| `lmstudio_version` + `version_source` | 1003 `0.4.24.0`／1004 `0.4.17.0`，**手動對照表，逐字寫明是人回報的宣稱** |
| `slot_id` / `slot_host` / `endpoint` | 排程器帶入 |
| `reasoning_effort` / `probe_reasoning_tokens` / `probe_reasoning_ok` | `none` / 實測值 / `== 0` |

⚠ `lmstudio_version` **查不到就是 `null`，不猜**（`/v1/models`、HTTP header、`/api/v0/models`
都不帶版本，2026-09-11／09-13 兩次實測）。沒登記的端點兩格都 `null`。

### 五-2　E-13：context 條件對齊（**已於發射前修正，本節記錄原始風險與處置**）

**原始設定的風險（草稿階段）**：曾規劃 `--context-length 65536 --parallel 2` ⇒ 每槽 **32,768**，
而 `max_tokens` 預算 ＝ **32,000**，餘裕僅 **1.02 倍**；12B 那輪是每槽 65,536 對 32,000 ＝ **2.05 倍**。
風險方向**不對稱**：`OFF`（1 通）與 `CONFORM`（5 通各自獨立單輪）每通只有 system＋題目＋一份候選（約 5k），
離上限很遠；**`HMIX` 是唯一的多輪臂**，第 k 輪要帶前面每一輪的候選碼與失敗原文 ⇒ 只有它會逼近上限。
若 HMIX 因撞 context 提早結束，Δ_C 會被系統性壓小，而「Δ_C 變小」正是 §四-1 的事前預測方向
⇒ **這個混淆會偽裝成本 run 的結論。**

**Fable 裁決（2026-09-17，發射前）：消除而非設界。** 兩台重載為
`--context-length 65536 --parallel 1` ⇒ **每槽 65,536**，與 12B 那輪逐項相同
（12B：`262144 / parallel 4 = 65,536`），對 32,000 預算的餘裕回到 **2.048 倍**。
換設定後兩台重驗推論模式：`reasoning_effort=none` ⇒ `reasoning_tokens=0`；不設旗標的對照組 ⇒ 32。
證據：`ops/gain/r532/probes/backend_conditions_20260917.json`（含 `revision_reason`）。

**代價（事前記錄）**：每台由 2 串降為 **1 串**，全域並行由 4 串降為 **2 串**，牆鐘約加倍（見 §六）。
這是為了讓「唯一變因是模型」成立所付的代價。

**仍保留的事後查核（不是擋門，是必印的欄位）**：

| # | 做什麼 | 判準 |
|---|---|---|
| E-13a | 逐臂逐集統計 `reject_reasons` 的 `budget_tokens`、`budget_wall`、`budget_calls`，以及後端回 `Context size has been exceeded` 類錯誤而 `infra_void` 的件數 | 全部落盤，收官必印 |
| E-13b | **偏斜觀察**：任一題組上 `HMIX` 的（context 錯誤 ＋ `budget_tokens`）件數 − `CONFORM` 的同一項 > **5 題** | 觸發 ⇒ 該題組的 Δ_C 附敏感度上下界一起報，並在收官逐字說明；**不再自動判 INVALID**（餘裕已與 12B 相同，觸發代表別的原因，要查不要猜） |
| E-13c | **敏感度界**：把受影響的題全部當成「HMIX 本來會成功」與「本來會失敗」兩種極端各算一次 Δ_C | 兩個界若不變號 ⇒ 結論穩健；變號 ⇒ 該集不得下任何方向性結論 |
| E-13d | 冒煙塊（§七-1）跑完立刻看 E-13a 的數字 | HMIX 有任何一題撞 context ⇒ 停下來報 Fable |

### 五-3　E-15：`ttlMs` 必須是 `null`（兩台）

R529 §十一 的事故：1004 崩潰後被 LM Studio **JIT 以 TTL 1h 重載**，之後每小時 :07 卸載，
retry×4 在 35 秒內打完撐不過 8–10 秒的重載窗 ⇒ `infra_void`（R460R r5 因此掉了 7 列）。
⇒ 發射前 `lms ps --json` 確認兩台 `ttlMs == null`；**跑到一半被 JIT 換掉會在 E-11-post 被抓到**。

### 五-4　E-16：seed 授權集合

§二-3 的四行必須在 **vacant-dev 上**掃過**所有** `runs/*/summary.json`，
實際集合與授權集合**逐字相等**。不相等 ⇒ `abort_seed_set_mismatch`。
⚠ 本機（Mac）只有 117 個 `summary.json`，**本機掃過不算數**。

### 五-5　E-14：persona 不變量（§二-4）

離線重放 `random.Random(f"{seed}:{arm}")` 的抽樣序列，與對照 run 的 `rows.jsonl`
agent 欄位**逐格比對**。**零模型呼叫、發射前可跑。一格不符就停**
——那代表「只換了模型」這句話是假的。

### 五-6　E-17：量具 `probe_instrument`（`--gauge-scope bank`）

逐塊對**整個題庫**驗兩個方向：參考解要過、已知壞樁要被擋。
任一方向沒過（含 `n=0`）⇒ runner 自己拒跑。與 12B 那輪逐字相同。
⚠ 量具是**單邊保證**（`vacant/suitegauge.py` docstring）：擋得住已知壞解 ≠ 涵蓋真需求。

### 五-7　E-18：佇列與塊的 sha 釘死

- DECISION 內要有逐字的 43 行 `R532_BLOCK:`（§二-2），發射器**整組**比對（不是逐項子字串）。
- 全佇列共用的五個條件也要逐字出現在本檔並由發射器 grep：
  `--arms OFF,CONFORM,HMIX`、`--gauge-scope bank`、`--request-timeout-s 900`、
  `--models qwen3-27b`、`--reasoning-effort none`。
- 佇列 JSON（`ops/gain/queues/r532.json`）的 sha256 要記進第一塊的 launch notes。

### 五-8　其餘沿用（不重述）

hub 禁止（`8765` 字面）、目錄／`launch.log` 已存在就停、`ThreadPoolExecutor(` 一出現就停、
`/v1/models` 要回得出模型、三次 chat 探針三次全過、自己人清單每個名字都要寫在 DECISION 裡、
每塊自己的 `flock`／`setsid`。

---

## 六、規模與時程

### 六-1　實測基礎

| 量 | 值 | 來源 |
|---|---|---|
| 27B 單串生成（1004，非 thinking） | completion 94／156／239 token，牆鐘 1.869／2.529／4.909 s ⇒ **48.7–61.7 tok/s** | `backend_conditions_20260917.json` |
| 12B 單串生成（1004） | **68 tok/s**；2 串 98、3 串 105–123、4 串 136–145（aggregate） | 2026-09-11 實測 |
| **12B 每題每串（三臂，非 thinking）** | **113.7 s**（1004 的 276 題／31,394 串秒） | 本檔由 `runs/g_r529_*/summary.json` 的 `arms.*.wall_s` 現算 |
| （對照）12B thinking | 326.4 s（1003 的 440 題／143,630 串秒） | 同上——**thinking 慢 2.9 倍**，這也是為什麼非 thinking 是對的選擇 |

逐集的 12B 非 thinking 每題每串：HumanEval+ **59.2 s**、MBPP+ **71.7 s**、
LCB v3 medium **179.5 s**、LCB v3 hard **363.1 s**。

### 六-2　公式

```
牆鐘 = (Σ_題組 n × T_task × R_speed) / S  +  preflight

T_task  = 113.7 s（12B 非 thinking，三臂，每串每題）
R_speed = 27B 每串速度 ÷ 12B 每串速度（在各自的 parallel 設定下）
S       = 兩台 × parallel 1 = 2 串（見 §五-2：為對齊每槽 context 而由 4 串降為 2 串）
```

`R_speed` 的估法（兩端都寫出來，**不挑對自己有利的**）：
- 27B 在 **parallel 1**：單串實測 48.7–61.7 tok/s ⇒ 取中 **≈ 55 tok/s／串**
  （不與另一槽搶，比 parallel 2 的每串值好）。
- 12B 在 R529 的 1004 上跑的是 1→4 串（佇列逐步擴槽），每串介於 68（1 串）與 35（4 串）。
- ⇒ `R_speed`（12B 每串 ÷ 27B 每串）落在 **0.6（12B 當時多在 4 串、35 tok/s）～ 1.24（12B 1 串、68 tok/s）**。
  **取保守端 `R_speed = 1.4`。**

### 六-3　時程表（**2 串**；原 4 串版本因 §五-2 的 context 對齊作廢）

| 項 | 串秒 | S | 牆鐘 |
|---|---:|---:|---:|
| 純跑：836 × 113.7 × 1.4 | 133,076 s | 2 | **18.5 h** |
| preflight：27 塊 evalplus/HE × ~9 min ＋ 16 塊 LCB × ~1 min | 15,540 s | 2 | **2.2 h** |
| **合計（中心估計）** | | | **≈ 20.7 小時** |
| 樂觀（`R_speed`=0.9、preflight 6 min） | | | ≈ 14 h |
| 悲觀（`R_speed`=1.4、token/題比 12B 多 30%、preflight 12 min） | | | ≈ 28 h |

⚠ 27B 在 **parallel 1** 的每串速度應優於 parallel 2 的每串值（不必與另一槽搶），
所以上表偏保守；實測以收官的 `summary.json` 回填。
**分批門檻 48 小時不變**：跑到第 8 塊做外推，若外推 > 48 h ⇒ 停下來報 Fable。

## 七、發射順序

### 七-1　**冒煙塊先跑一塊**（發射 43 塊之前）

先發 **`g_r532_hep_a1`** 一塊（20 題、三臂、HumanEval+，12B 那輪每題每串只要 59 s ⇒ 最快收官）。
它收完之後**必須先看四件事**才准放後面 42 塊：

1. E-11-post：`calls.jsonl` 的 `reasoning_tokens > 0` 占比 ＝ **0.0%**。
2. E-13a／E-13d：HMIX 有沒有任何一題撞 context 或 `budget_tokens`。
3. 每題每串的實際秒數 ⇒ 回填 §六-3 的 `R_speed`，重算總牆鐘。
4. 量具 2/2、V/GT CLEAN、收據鏈可驗。

四件事任一有問題 ⇒ **報 Fable，不要自己續發**。

### 七-2　佇列（`ops/gain/queues/r532.json`）

發射（**直接發 runner，見 §二-5；不使用排程器**）：

```
（本輪不用排程器；逐塊以 §二-5 的指令直接發，每台同時一塊，一塊收完才發下一塊。）
```

**本輪沒有排程器，所以也沒有槽、沒有擴槽條件、沒有乾跑模式**——「現在誰在跑」＝
`ps` 看得到幾個 `gain_run.py --out runs/g_r532_*`，**每台最多一個**。
逐塊指令見 §二-5；佇列 `ops/gain/queues/r532.json` 只作為塊清單與 sha 釘值的來源，不由排程器讀取。

參數見 §附錄 A。

---

## 八、誠實邊界（**收官必帶，現在就寫**）

1. **兩台 LM Studio 版本不同**（1003 `0.4.24.0`／1004 `0.4.17.0`）⇒ 推論引擎版本不同，
   kernel／取樣實作可能有差。**已驗一致的只有推論模式**（§五-0 的六格探針），
   **不是所有版本差都驗過了**。配對比較在塊內同一台，**跨塊的絕對值可能仍混版本差**
   ⇒ 分析器要有 `per_backend` 的描述欄（比照 `analyze_r529.py`，每格帶 `not_a_test: true`）。
2. **context 從 262,144 降到 65,536，但每槽仍是 65,536**（12B：262144/4；本輪：65536/1）。
   對 `max_tokens = 32,000` 的餘裕**兩輪相同，皆為 2.05 倍**（發射前修正，見 §五-2）。
   代價是全域並行由 4 串降為 2 串、牆鐘約加倍。
   **會逼近上限的只有 HMIX（唯一的多輪臂），也就是本實驗要量的那一臂**——
   草稿階段每槽 32,768 時，這個不對稱會把 Δ_C 系統性壓小，方向與 §四-1 的事前預測相同，
   **混淆會偽裝成結論**；**該設定已於發射前改掉（§五-2），所以本輪不存在這個混淆。**
   E-13a–d 因此**降為事後查核而不是擋門**：逐臂逐集落盤 context／budget 拒交、
   與 12B 並列、超過 5 題之差要逐字寫出並給敏感度上下界，
   但**不再自動把任何一集判 `INVALID`**（條件已對齊 ⇒ 撞上了也不再歸因於設定）。
   **收官不得略過這一節。**
3. **污染，而且這次比 12B 那輪嚴重。**
   - LCB v3 的日期窗是 **≤2024-08-10**；LCB v2 是 2023-08-26 → 2025-04-05。
   - **Qwen3.6／3.8 的訓練資料截止時間查不到**，但它們顯然遠晚於 gemma-4。
   - HumanEval+（2021）／MBPP+（2021）**幾乎確定在所有現代模型的訓練集裡**。
   ⇒ **S1／S2 的交付率上升，無法區分「模型更強」與「這批題進了訓練集」。**
   ⇒ **本 run 的主張只能是「增益如何隨單發強度變化」，不能是「模型 A 比模型 B 強」。**
   這不是免責聲明，它決定了 §四 的預測要怎麼讀。
4. **「更強」只在本專題的五個題組上、這一顆量化（Q4_K_M）、這一個 harness、
   這一組預算、非 thinking 條件下成立。**
   公開評測（Qwen 官方自報 LiveCodeBench v6 = 90.3）是 **thinking 模式＋agentic harness＋avg@3＋256K context**
   量的，與本 run 的**非 thinking、單通 prompt、10 秒沙箱、import 白名單、32k 預算**
   **不是同一件事**，不得引用來預測本 run 的 OFF 交付率。
5. **非 thinking 是一個選擇，不是這顆模型的自然狀態。**
   對照組實測 `reasoning_tokens=32` ⇒ 它預設會 thinking。
   本 run 關掉它是為了與 12B 五題組的條件對齊（Fable 裁決），
   代價是**我們量的不是這顆模型最強的樣子**。
   要比 thinking 版必須另開一輪，**而且 12B 也要開 thinking 跑一次才對稱**
   （R529 §十一 已量到 thinking 讓 12B 的 token 漲 4–5 倍、單發交付率在簡單集上到 87–92%）。
6. **HumanEval+ 156/164**（8 題因沙箱信封排除，含 `HumanEval/15` 的 2× 餘裕門檻）；
   **MBPP+ 371/378**（7 題因資源信封排除）。與 12B 那輪逐字相同。
7. **量具是單邊保證**；`lcb3_hard` 只有 3 題被參考解直接驗過（`gauge_in_filter_n`＝3）。
8. **V/GT 工具只掃 H 臂**，其餘三臂要靠不呼叫工具判準函式的獨立掃描補（R529 §六-1 的做法）。
   `needles_checked` 裡被跳過的瑣碎 needle **不算檢查過**。
9. **一次 run 不是複製。** R460 的 +13.33 → 五次複製 +0.83～+5.83 已經演過一次
   「單次點估計是上偏的」。R532 是**一次** run，每一個點估計都要當單次值讀。
10. **迴圈與展覽夜班會搶同一批 GPU。** `ops/localagent.py` 的 `DEFAULT_MODEL` 是
    `qwen/qwen3.6-35b-a3b`，打 8765 中轉 → 1004；win1003 的 `/d/lock_scene`、`/d/lock_night14`
    存在時 GPU 歸展覽。⇒ 發射前必須確認「迴圈停了或改指別處」「沒有 lock 檔」，
    並在 launch notes 記下來；共租率要像 R460R 的 `co_tenancy` 那樣落盤（描述性、不校正）。
11. **`R_speed` 是估計不是實測。** §六-3 的 20.7 小時（2 串）建立在「27B 的每串速度
    ＝ 單串 × 1.44」這個**借用 12B 併發形狀**的假設上。27B 的 2 串 aggregate **沒有實測**。
    §七-1 的冒煙塊就是為了回填它。

---

## 九、收官必產的東西

| 產物 | 內容 |
|---|---|
| `ops/gain/analyze_r532.py` | 五集 × 三臂；`primary`（家族 2、Holm）、`per_set`、`per_backend`（描述性、每列 `not_a_test`）、`tokens_pooled`、`decision_state`、`inference_mode`（reasoning 占比，判 E-11-post）、`context_pressure`（E-13a 的逐臂逐集計數）、`vs_12b`（跨模型差值，每列 `not_a_test`）；`--selftest`＋`--mutation-check` |
| `ops/gain/replay/r532/r532_analyze.json` | 仲裁值 |
| `vgt_v2_<block>.json` × 43 | V/GT 逐塊 |
| `receipts_verify.json` | 收據鏈逐筆驗 |
| 三方對帳 | 分析器（A）／不讀分析器的獨立重算（B）／第三次直接掃檔（C），仲裁欄位逐位元相同 |
| 稽核檔 | `DECISION_2026xxxx_R532_FABLE_AUDIT.md` |

⚠ 分析器必須在**第一塊收官之前**落地（R529 §六-4 的教訓：首塊在分析器 commit 前收官，
「沒讀 rows」就變成不可查證的宣稱）。

---

## 十、事前檢定力（**發射前算完，凍結**）

方法：`vacant.research.mcnemar_power(n, p_disc, ψ, alpha=0.05)`（精確雙尾，對 K 與 B 全枚舉，無近似）。
`p_disc` 取 **12B 實測**的 HMIX vs CONFORM 不一致對率；ψ 由 `Δ = p_disc × (2ψ − 1)` 反解。
產物：`ops/gain/r532/power_table.json`。

| 題組 | n | p_disc（12B 實測） | ψ@+2pp | 檢定力@+2pp | ψ@+5pp | 檢定力@+5pp |
|---|---:|---:|---:|---:|---:|---:|
| S0 LCB v2 | 120 | 0.192 | 0.552 | **0.050** | 0.630 | **0.176** |
| S1 LCB v3 medium | 135 | 0.082 | 0.623 | **0.072** | 0.807 | **0.429** |
| S2 LCB v3 hard | 54 | 0.148 | 0.568 | **0.027** | 0.669 | **0.079** |
| S3 HumanEval+ | 156 | 0.058 | 0.673 | **0.098** | 0.933 | **0.701** |
| S4 MBPP+ | 371 | 0.070 | 0.643 | **0.237** | 0.857 | **0.961** |

**這張表在資料之前就要被讀懂，否則收官會誤讀**：

1. **+2.0 pp 的真效果在五個題組全部測不出來**（檢定力 0.027–0.237）。
   ⇒ 若收官得到「全部不顯著」，那**與「效果是 0」和「效果是 +2pp」都相容**，
   兩者本檔都區分不了。收官**不得**把不顯著寫成「增益消失」。
2. **+5.0 pp 只有兩集有牙齒**：MBPP+（0.961）與 HumanEval+（0.701）。
   LCB v3 medium 0.429、LCB v2 0.176、LCB v3 hard 0.079。
   ⇒ 真正能回答「增益有沒有縮小到 +5pp 以下」的只有 **S4 MBPP+**，其次 S3。
   §四-1 的預測若要被檢驗，主要證據來自這兩集；S2 hard（n=54）事前即宣告無鑑別力，
   與 §四-2 已寫死的「S1／S3 沒有鑑別力」一起，構成本輪**事前就知道的上限**。
3. 這張表用的是 **12B 的** `p_disc`。27B 的不一致率若更低（更強的模型兩臂更常一致），
   檢定力會**比表上更低**；若更高則更高。收官要用實測 `p_disc` 重算一次並兩張表並列。
4. `RULED_OUT` 的 +2.0 pp 線（§四-2）在這個檢定力下**幾乎不可能達成**——
   這是事前就接受的代價，不是收官時才發現的問題。

## 十一、發射方式的裁決（原本列為「本檔不是唯一的阻擋項」，**已於發射前解除**）

草稿階段列了兩個非本檔的阻擋項，Fable 2026-09-17 的裁決把兩個都解除了，**不改任何既有程式碼**：

| 原阻擋項 | 裁決 |
|---|---|
| `schedule_queue.py` 的 `QUEUE_SLOTS` 順序拿不到 2+2、`PER_HOST_CAP=4` 與 `parallel` 不符 | **不改它**（R529 的凍結碼，改了會動到別的實驗）。本輪每台 `parallel=1` ⇒ 全域 2 串，改為**直接發 runner**（§二-5），每台同時只跑一塊，一塊收完才發下一塊。 |
| 需要新增 `ops/gain/launch_r532_block.sh` | **不需要**。直接發 runner 不經過 `launch_*.sh`；`gain_run.py` 仍對本檔做 `R532_BLOCK:` 的整組比對，少一格就發不出去。 |

⇒ 本檔寫完並凍結之後，**沒有其他阻擋項**。

## 附錄 A、佇列產生器參數（`ops/gain/queues/r532.json`）

**已產出：`ops/gain/queues/r532.json`**（43 塊、836 題、五集交錯順序）。
**已用真的 `ops.gain.schedule_queue.load_queue()` 驗過**：`load_queue OK`，
43 塊、836 題、塊名與 tag 唯一、同 (bank, filter, seed) 之下零重疊、端點集合與槽表相符。

頭部參數（**最外層只准這十個鍵**——`load_queue` 對認不得的鍵一律 `SystemExit`）：

```json
{
  "name": "r532_stronger_model",
  "decision": "DECISION_20260917_R532_STRONGER_MODEL_PREREG.md",
  "launcher": "ops/gain/launch_r532_block.sh",
  "arms": "OFF,CONFORM,HMIX",
  "request_timeout_s": 900,
  "review_timeout_s": 380,
  "gauge_scope": "bank",
  "models": "qwen3-27b",
  "backends": { ... },
  "blocks": [ ... 43 ... ]
}
```

⚠ **`--reasoning-effort none` 與 `--record-bank-field` 不在佇列 JSON 裡**
（那十個鍵是封閉集合）⇒ 本輪**直接寫在 §二-5 的逐塊指令裡**，不經任何 `launch_*.sh`。
⚠ **佇列 JSON 的 `launcher` 欄（`ops/gain/launch_r532_block.sh`）是 schema 的必填欄，
本輪不會被讀到、那支腳本也不存在**——`load_queue` 只驗欄位在不在、不驗檔案在不在。
本檔 §十一 已裁定不需要它；引用佇列 JSON 時不得把那一欄讀成「發射走這支」。

`backends` 兩台**逐項相同**：`context_length 65536`／`parallel 1`／`per_slot_context 65536`／
`gpu max`／`ttlMs null`／`identifier qwen3-27b`／`modelKey qwen/qwen3.8-27b`／
`arch qwen35`／`quantization Q4_K_M (4 bit)`／`sizeBytes 17742040464`／
`reasoning_effort none`／`probe_reasoning_tokens 0`／
`probe_control_no_flag_reasoning_tokens 32`／
`probe_evidence` 指向 `ops/gain/r532/probes/backend_conditions_20260917.json`。
只有 `host`／`lmstudio_version`／`version_source`／`note` 四格兩台不同，
且 `version_source` 逐字寫明**那是人回報的宣稱不是量測**。

**發射順序**＝五集交錯：
`lcb2_a1, lcb3m_a1, lcb3h_a1, hep_a1, mbpp_a1, lcb2_a2, lcb3m_a2, lcb3h_a2, hep_a2, mbpp_a2, lcb2_a3, lcb3m_a3, lcb3h_a3, hep_a3, mbpp_a3, lcb2_a4, lcb3m_a4, hep_a4, mbpp_a4, lcb2_a5, lcb3m_a5, hep_a5, mbpp_a5, lcb2_a6, lcb3m_a6, hep_a6, mbpp_a6, lcb3m_a7, hep_a7, mbpp_a7, hep_a8, mbpp_a8, mbpp_a9, …, mbpp_a19`

⚠ 順序**不在**§二-2 的註冊行裡（註冊行只描述單一塊，不含順序）——
與 R529 §二-2 的 ⚠ 同一條紀律。**§七-1 的冒煙塊 `g_r532_hep_a1` 要先單獨發，
排程器等它綠了才起。**
