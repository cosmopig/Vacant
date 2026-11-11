# G3.2 發射結果解讀（P20261111_2319-2；2026-11-11）

- **資料源**：`/home/user1/dev/ops/g3_fire/20261111_g3_2/g3_result.json`
  （sha256 `2a46b5a3…bea7e`、19136 bytes、fired_at 2026-11-11T23:28:45Z、
  核准 `ops/approvals/g3_vq-1zf_fire_20261111.json` approved=true）
- **解析**：`ops/audits/g3_2_fire_summary.py`（--selftest 6 controls PASS）→
  `ops/audits/g3_2_fire_summary.json`（schema `vacant.audit/g3_2_fire_summary/1`）
- **範圍**：4 凍結未見題（dab_725/dab_587/dab_657/dab_517）× full_rloop ＝ 4 格；
  1 rep；**方向性、單 rep、不外推其他模型/題（H-12）、不宣稱臂 superiority**。
- **口徑**：UNKNOWN 既非裁決亦非通過（I-4）；缺值 UNKNOWN 不填 0；不讀 hidden/scorer。

## 1. 總覽（所有數字帶分母）

| 量 | 值（分母） |
|---|---|
| cells status=ok | **4/4**（各 1 輪；error 格 0/4） |
| content_reverify enabled | 4/4 |
| final_verdict | UNKNOWN **4/4**、PASS 0/4、FAIL 0/4 |
| claims 總數 | **26**（6+5+8+7） |
| claims PASS / FAIL / UNKNOWN | **0/26、0/26、26/26** |
| 有確定性裁決的格（H1a） | **0/4** |
| 已確認缺口格（round_1 gap_reason 非 null） | **0/4** |
| round 2 執行格 | **0/4**（diff 全 null） |
| hidden_after | UNKNOWN 4/4（本端不自打分；照 /srv/vlab 慣例由人類/vlab 側） |
| model calls / tokens | 8 / 128923（answer 100324＋extract 28599；日額度 128923/2000000＝6.45%） |

**H1 判定：`H1_REFUTED`**——(a) 0/4 格達確定性裁決，觸發否決條件 (a)；
(b) 因 0/4 格有已確認缺口記 `not_applicable`（依規則：不得記通過、不得記否決；
本輪否決來自 (a)，不來自 (b)）。

**第 2 輪未發生的原因（機制如設計，非故障）**：g3.py 的 `confirmed_gap`＝「≥1 條
必需 claim FAIL」或「缺必要答案項」；UNKNOWN 不是缺口。4/4 格 round 1 全 UNKNOWN
→ 無已確認缺口 → 不觸發第 2 輪 → `diff=null` 4/4。若第 2 輪被觸發而無 diff，
那才是守衛失靈（g3.py 守衛：兩輪都有真實重算結果才記 diff）。

## 2. 逐題分析（4/4）

### dab_725（6 claims；格 tokens 16007＝answer）
- round_1 verdict **UNKNOWN**；gap_reason **null**（無已確認缺口）；round 2 未執行（diff null）；final **UNKNOWN**。
- 6/6 claims UNKNOWN，reason 全為 `deliverable_not_in_request`：extract 輸出把交付物
  寫成描述性短語（如「工作區根目錄的 answer.txt 檔案」「answer.txt 中六個
  @name[value] 項目…」），非原文點名的檔案名 token → 凍結 guard
  （`extract.py:_deliverable_problem`）如設計拒編譯為可重算檢查。
- **H0 預跑 vs fire（同題、同 input_sha256、同模型 glm53、兩次獨立 extract 呼叫）**：
  預跑 7 需求 / 2 條確定性（R1/R6）；fire 6 需求 / 0 條確定性——**claim 分解本身不同
  （7→6）、確定性數不同（2→0）**。見 §4。

### dab_587（5 claims；格 tokens 9969）
- round_1 **UNKNOWN**；gap_reason null；round 2 未執行；final **UNKNOWN**。
- 5/5 claims UNKNOWN，全 `deliverable_not_in_request`（「answer.txt 中包含
  @correlation_coefficient[...] 項目」等描述性交付物名）。
- H0 預跑同題亦 0/5 確定性（3× unknown_verifier:missing＋2× deliverable_not_in_request）
  ——**兩輪一致**（0→0）。

### dab_657（8 claims；格 tokens 37555，4 格中最高）
- round_1 **UNKNOWN**；gap_reason null；round 2 未執行；final **UNKNOWN**。
- 5/8 claims `unsupported_recompute_type`（mean_col×3、median_col×1、std_col×1：
  重算類型不在凍結 PLAIN_RECOMPUTE_TYPES 集）＋3/8 `deliverable_not_in_request`
  （@mean_close/@median_close/@std_close 項格式）。
- H0 預跑同題 0/8 確定性（3× unsupported_recompute_type＋5× deliverable_not_in_request）
  ——**確定性數一致（0→0）**，reason 分布略異（預跑 3×unsupported vs fire 5×）。

### dab_517（7 claims；格 tokens 36793）
- round_1 **UNKNOWN**；gap_reason null；round 2 未執行；final **UNKNOWN**。
- 6/7 claims `deliverable_not_in_request`（correlation_pclass_fare 值、Pearson 方法、
  排除 null、四捨五入、格式、answer.txt 檔案）＋1/7 `missing_param:values`。
- H0 預跑同題 0/7 確定性（3× deliverable_not_in_request＋2× model_declared_unverified＋
  2× unsupported_recompute_type:pearson）——**確定性數一致（0→0）**。

**reason 家族分佈（26/26）**：`deliverable_not_in_request` **20/26**、
`unsupported_recompute_type` **5/26**、`missing_param` **1/26**。
主因＝extract 層交付物命名不達凍結 guard（描述性短語而非點名檔案）；
次因＝重算類型不在凍結集。兩族皆為 extract→checks 編譯層問題，**非 harness 故障**
（4/4 格跑完、1 輪、無 error），亦非 4 題內容正確性結論（本批 hidden 全 UNKNOWN）。

## 3. H1 判定與假說狀態

- 規則（`ops/reqloop/g3_2_candidate_hypothesis.md` §2 H1）：(a) ≥1/4 格 ≥1 條
  確定性裁決（PASS/FAIL）；(b) 已確認缺口格 round 2 fixed≥1 且 regressed=0。
- 實測：(a) **0/4 不成立**；(b) **not_applicable**（0/4 缺口格）。
- **H1 狀態：`H1_REFUTED`**（否決條件 (a)）。
- **明確非目標（§2 既有口徑）**：本結果不回答「R-loop 比基線修得多」——需 hidden
  打分（人類/vlab 側）＋≥2 rep；本批 26/26 UNKNOWN、hidden_after 4/4 UNKNOWN，
  對 4 題內容正確性不給任何結論。

## 4. 發現：H0 門跨獨立呼叫不穩定（1/4 題）

| 題 | 預跑確定性 | fire 確定性 | 需求數（預跑→fire） | 一致？ |
|---|---|---|---|---|
| dab_725 | 2/7（R1/R6） | 0/6 | 7→6 | **不一致** |
| dab_587 | 0/5 | 0/5 | 5→5 | 一致 |
| dab_657 | 0/8 | 0/8 | 8→8 | 一致 |
| dab_517 | 0/7 | 0/7 | 7→7 | 一致 |

- 同 input_sha256（4/4 匹配）、同 extract 模型（glm53）、兩次獨立 extract 呼叫
  （預跑 r1469 22:21Z；fire r1472 23:28Z）。
- **推論**：extract 層（LLM 輸出）跨呼叫非確定——同一題同一 prompt 的 claim 分解與
  確定性裁決數可不同。H0 預跑門（單次呼叫）對「fire 時同題能否產出確定性重算」
  的保證力弱於預期：門量的是「該次呼叫」，不是「該題」。
- **含義**：這是 extract 層屬性。解凍 `extract.py`／`checks.py`（多呼叫共識門、
  交付物命名強化）＝人類裁決（凍結四檔本系列不得改）。

## 5. 成本與停止規則狀態

- **成本**（fire 單批）：8 calls / 128923 tok；answer 100324＋extract 28599；
  日額度佔 6.45%（128923/2000000）。cost_usd **UNKNOWN**（產物無計價欄；
  glm CLI 計價缺值不填 0、cost_usd=0 不等於免費）。
- 含 H0 預跑之階段累計：12 calls / 158837 tok（29914 預跑＋128923 fire）。
- **停止規則狀態（承接假說 §4 停止規則＋2026-11-06 定案第 3 條）**：
  1. 「H1 否決 → 停止、上報人類」——**本輪觸發**（H1_REFUTED）；本檔＋
     `g3_2_fire_summary.json` 即上報內容。
  2. 「連續 2 發無已確認缺口被消解 → 停止、上報人類」——**事實亦觸發**：
     G3 c 發（26/26 unverified→UNKNOWN、無缺口被消解）＋G3.2（26/26 UNKNOWN、
     0/4 缺口格）。
  3. 「不得對每題未解錯誤加錯誤字串 regex／靜態 prompt／同題重試工單」——遵守；
     下輪候選（§6）是**新問題**（門的穩定性），非同路徑重試。

## 6. 誠實邊界

- 單 rep、本地模型（answer deepseek41／extract glm53）；**H-12：不外推**其他模型、
  其他 harness、其他題集。
- 26/26 UNKNOWN＝extract→checks 編譯層對本 4 題未產出任何確定性重算；**不是**
  「4 題答錯」，也**不是**「機制故障」（4/4 格 ok、如設計 1 輪、無 error）。
- hidden_after 4/4 UNKNOWN：本端不自打分；內容正確性結論只在人類/vlab 側打分後存在。
- 同批重發非獨立樣本；不宣稱臂 superiority；所有數字方向性、帶分母。
- 本解讀只讀機制記錄（claims 狀態、gap_reason、diff、usages）與產物欄位，
  未讀 hidden/scorer。

## 7. 下一預註冊問題

→ `ops/reqloop/g3_2_candidate_hypothesis.md` §6（**G3.3：H0 門跨獨立呼叫穩定性**）；
發射需人類核准（同 G3.2 流程），0 產品碼改動、不碰凍結四檔。
