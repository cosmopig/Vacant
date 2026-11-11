# e016_failed_step_ablation（L006 因果測試）——預先登記實驗包

> 2026-11-03（round 903）建立。本檔在出結果前**不得修改**（e015 先例）。
> 對應 L006（round 901 複核版）§3「因果測試＝消融」；前置產品改動＝round 902
> （commit `b8b715af`、TDD 6/6）；量具改動＝`decisions/DECISION_20261103_E016_CNF_MEASUREMENT.md`。
> 紅線：本包不含任何 `/srv/eval/hidden/` 或 `scorer.py` 內容；評審只看公開資訊＋cell 證據。

## 1. 問題與可證偽假設

**問題**：polyglot 題組上 `C > A` 的差異，是否由 `failed_step(test_failed)` 交付前複審
（zerostop kickback）中介？

- **H-L006**（L006 §3）：消融＝「同樣是 C，但 failed_step 預交付複審關掉」。
- **C-nf 臂**＝Vacant `b8b715af`＋`VACANT_FAILED_STEP_REVIEW=0`（只關
  `failed_step(test_failed)` kickback；findings/left_open/觀察模式不變；round 902 docstring 明載）。
- **H0（NO_MECHANISM）**：`C vs C-nf` 差異未過預登記門檻（C-nf ≈ C）⇒ 開關無可測效應 ⇒
  failed_step 複審不是 C 贏的主要機制 ⇒ **不改產品**。
- **H1（MECHANISM_CONFIRMED）**：`A<C` 顯著 ＋ `C>C-nf` 顯著（消融去掉贏）＋ `A≈C-nf` ＋
  目標格 `pg_list_ops`（C 贏、C-nf 掛）⇒ 機制成立（在預登記門檻內）。
- **可證偽路徑**：§4 狀態表五態，互斥、按優先序判定（AMEND1 方向護欄先例）。

**功效聲明（預先登記，防事後敘事）**：34 對、1 rep、McNemar 精確雙邊＋Holm（family=3）。
Holm 首關 α=0.0167 ⇒ 需 **≥7/34（20.6%）單一方向不一致對**；未過 Holm 的 raw α=0.05
需 ≥6/34。先驗：e001 8 C_only（60 對，p=0.109）、e002 7 C_only（34 對，p=0.344）、
e013 1/26 p=1.0、e014 2/26 p=1.0——polyglot 上 C>A 是**弱到中等且各單次 run 均未顯著**。
⇒ 本設計（1 rep）對中等效應大多落在 NO_MECHANISM/UNRESOLVED；讀法＝
「在預登記門檻內未建立」，**不是**「機制無用」（e015 §1 功效聲明先例）。

## 2. 設計

### 2.1 臂（3）
| 臂 | 定義 |
|---|---|
| A | 無 Vacant（同 e002 A） |
| C | Vacant `b8b715af`、預設模式（round 902 不變量：預設未設＝位元組級相同，故 C 與改動前 C 同義） |
| C-nf | Vacant `b8b715af`＋`VACANT_FAILED_STEP_REVIEW=0`（只關 failed_step kickback；其餘行為不變） |

**C-nf 機制鏈（每環可稽核）**：queue 檔 per-cell `env`（§2.5）→ labd `run_cell` 的 `env` dict
→ cell.py 行程環境 → `vacant_env_passthrough()` **明確 `--setenv`** 進 bwrap 沙箱（不依賴預設繼承）
→ pi 及其 hook 子程序 `zerostop.failed_step_review_on()` 讀到 `0`。
**稽核**：C-nf 格 `cell.json` 必含 `agent_env={"VACANT_FAILED_STEP_REVIEW":"0"}`；C 格無該欄位；
C 格 `vacant_sha==b8b715af`、A 格 null（e014 gate-5 先例）。

### 2.2 題組（不新選）
- **polyglot_py 34 題**（＝e002 題組，非新選題）× {A, C, C-nf} × 1 rep ＝ **102 格**。
- **目標格 `pg_list_ops`**：唯一在 e001＋e002＋e006 三個 run 皆 C_only（C 過、A 掛）的題，
  且有機制因果記錄（L006 §2.1：C 格失敗步被複審打回重寫、A 格同類失敗未打回）。
- 各題 C>A 標記（自 e001/e002/e006 的 score.json 原檔重算）：`audits/e016_task_set.json`
  （round 903 生成；C_only：e001 7 題、e002 7 題、e006 5 題；三 run 交集＝pg_list_ops）。
  註：L006 §1 表「pg_pov（e001+e002）」經原檔重算實為 e001+e006（e002 兩臂皆過）；
  目標格 pg_list_ops 不受影響。
- **釘死**：每題 `instruction_sha256`＋`workspace_sha256`（與 cell.py 同算法；
  生成腳本 `audits/e016_task_set_build.py`，`sudo -n` 與 labd 同權限讀 stage 樹）。
  發射前（smoke 與 full 前）逐題複驗（gate 6）。

### 2.3 工具/模型/超時
- harness＝`pi`；模型＝`gemma-4-12b-it-qat @1004`（cell.py 預設）；timeout 1800s；
  PAR=2（1004 共 4 slot 留餘量；e014 先例）。

### 2.4 發射階段（小先大後，e013/e014 先例）
- **stage 1（smoke）**：`pg_list_ops × {A, C, C-nf}` ＝ 3 格。
  **Go/No-Go（infra 級，非結果級）**：3/3 格完成且計分；C-nf 格 `agent_env` 正確；
  C 格 `vacant_sha==b8b715af`、A 格 null；0 infra。
  **C-nf 在 pg_list_ops 上輸贏＝資料，不是 gate**（防「先看一格再決定」的事後調整）。
- **stage 2（full）**：102 格（smoke 3 格由 cell.py「已存在，略過」自動保留）。

## 3. 統計（預先登記，事後不得改）
- 單位＝34 題對（同題×同 rep×三臂）；配對 McNemar 精確雙邊（與 report.py 同式）。
- 三配對：`A vs C`、`A vs C-nf`、`C vs C-nf`；**Holm–Bonferroni（family=3，step-down）**，α=0.05。
- 方向護欄：MECHANISM_CONFIRMED 要求 `A<C`（C_only>A_only）且 `C>C-nf`（C_only>C-nf_only）；
  方向反轉無「有害」預登記結論（R532 AMEND1 先例：不寫「kickback 有害」）。
- **成本紅線（優先於機制判定，e014 §5 先例）**：`C/A ≤ 2×` 且 `C-nf/A ≤ 2×`
  （calls_per_success 與 tokens_per_success 皆；A 零通過時該比不判定、記描述性）。
  描述性（不判定）：C-nf vs C 成本（預期 ≤1：無 kickback 應較省輪次；>1 記異常）。
- **refusal 計為失敗**（C/C-nf 拒交＝未交付＝pass=false 入分母）；
  **infra_void**（score.pass=None）剔出分母、不回填（e007/e015 先例）；
- 未顯著 ≠ 等價（NO_MECHANISM 的讀法含此界）；
- 數字不得 cherry-pick（H-0 先例）；成本與結果同報（e006 先例）。

## 4. 狀態表（五態、互斥、按優先序判定）
| 優先 | 狀態 | 條件（皆須成立） | 讀法（預先登記措辭） |
|---|---|---|---|
| 1 | **UNKNOWN** | infra/缺分 > 20%（>20.4 格） | 未測，非負結果（e005/e015 先例） |
| 2 | **COST_BREACH** | C 或 C-nf 任一成本指標 > 2×A | 成本紅線（e014 §5：CB 2.26× ⇒ 不划算）；機制判定不成立 |
| 3 | **MECHANISM_CONFIRMED** | ① A<C Holm 顯著且方向 C 贏；② C>C-nf Holm 顯著且方向 C 贏；③ A vs C-nf Holm 未顯著；④ pg_list_ops：C 過、C-nf 掛 | failed_step 預交付複審是 C 贏 polyglot 的機制（在預登記門檻內、1 rep、H-12 界）；**產品後續＝強化此機制（新 cycle、新 packet、TDD 先）** |
| 4 | **NO_MECHANISM** | C vs C-nf Holm 未顯著 | 開關無可測效應 ⇒ failed_step 複審不是（主）機制（門檻內）；**不改產品**；不寫「kickback 無用」因果結論（1 rep、H-12） |
| 5 | **UNRESOLVED** | 其餘組合（含方向反轉、部分中介） | 未建立（方向/幅度未達）；記為結果（e005 UNKNOWN 先例：非負、非正）；不改產品 |

註：L006 §4 原表四態；UNKNOWN（infra 護欄）為 e007/e015 標準先例之補，不與原表四態衝突
（原表未定義 infra 情形；此處按既有先例補齊並聲明）。

## 5. 邊界（繼承，不可議）
- **H-12**：本地量化模型 gemma-4-12b-it-qat、單一 harness（pi）、1 rep、34 題——
  不推及其他模型/harness/題組/規模；
- **H-1**：前提是題有可執行 scorer（polyglot 有；無 scorer 的題不在本包）；
- **H-2 同構**：pass＝hidden scorer 判定（不讀 scorer 源），非自評；
- refusal 計為失敗；infra_void 剔出分母不回填；
- 未顯著 ≠ 等價；
- C-nf 開關是**實驗工具**：預設行為不變（round 902：未設＝位元組級相同、fail-open）；
  本包不改任何預設、不改產品；
- 評審/稽核只看公開資訊＋cell 證據；不觸 `/srv/eval/hidden/`、不讀 scorer.py。

## 6. 非目標（防誤讀）
- 不測「拿掉複審是否普遍好/壞」（單題組、1 rep）；
- 不碰 e015 路徑（多 agent 已否決、無互動）；
- 不改預設行為（開關 env opt-in；C 臂＝預設）；
- MECHANISM_CONFIRMED 的後續（強化複審）是**新 cycle、新 packet、TDD 先**——不在本包。

## 7. 發射 gates（六 gate 全綠才發射；e014/e015 先例）
1. **senior 正式評審通過**本 packet（ticket `R20261103_1340-1`）；
2. **CI 綠**：auto/qwen27b HEAD ≥ `b8b715af`（b8b715af＝開關＋測試，全量待跑）；
3. **磁碟 ≥ 4G**（round 903 時點 64G）；
4. **queue 空**（labd 無在跑格）；
5. **sha 釘死**：`vacant_sha=b8b715af`（ANCESTOR-OK、含開關）；
   改動後 `sha256(/srv/vlab/bin/cell.py)`＝
   `ee10ca02512b798197efb88cafec8b051adb4d3e32ab21f254e7d1f41d4149af`
   （DECISION_20261103_E016_CNF_MEASUREMENT、T1–T4 ALL OK、備份 cell.py.bak_r903）；
6. **smoke（stage 1 三格）綠**＋full 前逐題複驗：34/34 題 instruction/workspace sha 與
   `audits/e016_task_set.json` 一致（`audits/e016_task_set_build.py` 重算）；
   C-nf 格 `agent_env` 正確、C 格 `vacant_sha==b8b715af`／A 格 null。

## 8. 附錄（全部在案）
- 題組 sha：`audits/e016_task_set.json`＋`audits/e016_task_set_build.py`（round 903）
- 產品改動：`b8b715af`（`zerostop.failed_step_review_on()`＋`tests/test_failed_step_switch.py` 6/6）
- 量具改動：`decisions/DECISION_20261103_E016_CNF_MEASUREMENT.md`＋
  `/srv/vlab/bin/cell.py.bak_r903`＋`audits/vlab_cell_env_passthrough_test.py`（T1–T4 ALL OK）
- 判決管線：`audits/e016_verdict_pipeline.py`（本輪預先登記、selftest 7 組 ALL OK、純 stdlib；
  exit：0＝判定、10＝未完成、20＝UNKNOWN）
- 隊列檔：`staging/16a_e016_smoke.json`（stage 1）、`staging/16_e016_failed_step_ablation.json`（stage 2）
- 參考：L006 §1–§4；e015 packet（狀態表/優先序）；e014 §5（成本紅線）；R532 AMEND1（方向護欄）；
  NOW.md round 901–902

## 9. 完賽回填（round 1441、2026-11-11；§1–§8 預註冊內容未動）

- **通過率**：A 18/34 [0.5294]、C 17/34 [0.5000]、C-nf 16/34 [0.4706]（34 題對、1 rep）。
- **McNemar（精確雙邊、與 report.py 同式）**：A vs C p=1.0（A_only 5 / C_only 4）、
  A vs C-nf p=0.7539（A_only 6 / C-nf_only 4）、C vs C-nf p=1.0（C_only 4 / C-nf_only 3）；
  Holm–Bonferroni（family=3）三對皆未顯著。
- **目標格 pg_list_ops**：三臂皆未過（A/C/C-nf 全 false）——未出現「C 贏、C-nf 掛」的機制指紋。
- **成本（每成功呼叫）**：A 60.2 vs C 80.5 vs C-nf 87.4 calls/success（C/A 1.34×、C-nf/A 1.45×，
  未破 2× 紅線）；tokens/success A 1.43M / C 2.00M / C-nf 2.09M。
- **裁決＝NO_MECHANISM**（§4 狀態表第 4 態）：C vs C-nf 未顯著 ⇒ 開關無可測效應 ⇒ **不改產品**；
  依 §4 預註冊措辭不寫「kickback 無用」因果結論（1 rep、H-12；未顯著 ≠ 等價）。
- **裁決落盤**：`ops/audits/e016_failed_step_ablation_verdict.json`（`e016_verdict_pipeline.py`
  2026-11-11 對 `/srv/vlab/runs` 機械重生成、exit 0、與 round 1018 已入樹版逐位元組一致）。
- **界**：本地量化模型 gemma-4-12b-it-qat、pi、1 rep、34 題之方向性測量（H-12）；
  不推及其他模型/harness/題組/規模。
