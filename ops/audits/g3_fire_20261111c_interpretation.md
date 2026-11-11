# G3 重發 c（20261111c）full_rloop content_reverify 逐條差異深度解讀

- 對應：2026-11-11 人類常設定案第 2.a 條與資深審查第四節第 3 條——full_rloop 的
  content_reverify 逐條差異是否支持「需求驅動 R-loop 在未見題上抓到並修好內容錯誤」；
  4 題只出方向性結論、每個數字帶分母、不做普遍宣稱。對應工單 P20261111_0914-2
  （r1438 產出）與其重發 P20261111_1115-1（r1440 獨立重驗，見 §8）。
- 數據來源（本輪實際開啟核驗）：
  - `ops/audits/g3_fire_20261111c_summary.json`（21573 B；identity.result_sha256
    `bd727b930f8e1be5…`；raw `~/dev/ops/g3_fire_20261111c/g3_result.json` 20660 B、
    sha256 與 identity pin 一致；重跑 byte 一致＝確定性（r1437 已驗））
  - `~/dev/ops/g3_fire_20261111c/cells/` 8 工作區（native_pi 4：round_1 含
    goal.md／contract.md／data/*.csv；full_rloop 4：僅 round_1/answer.txt）
  - 任務庫 `~/dev/ops/ref/bm_tasks/dabench/`（base/tasks/<tid>/workspace 實存
    goal.md／contract.md／data/CSV，如 dab_176/workspace/data/titanic.csv 61194 B）
  - 代碼路徑（只讀、未改）：`vacant_network/reqloop/g3.py` L251 `content_recheck`、
    L295 `confirmed_gap`、L942 `tdir = base/"tasks"/tid`、L1002 `task_ws = tdir/"workspace"`、
    L1051 reverify 呼叫點；`vacant_network/reqloop/checks.py` L2777
    `run_requirement_checks`、L2788–2794 `item.unverified → UNKNOWN` 分支；
    `vacant_network/reqloop/extract.py` L734–779 unverified 標記、L1039 提示規則
- 成本（summary totals）：27 model calls、383921 tokens（cells 355734＋extract 28187、
  known_usages=14）；2 個 native_pi err 格 tokens=None（UNKNOWN，不填 0）；
  hidden_after 12/12 UNKNOWN（打分在人類/vlab 側，本輪未做）。

## 0. 總表（12 格）

| 臂 | ok | error | content_reverify 完成輪數 |
|---|---|---|---|
| native_pi（qwen3.8-27b，pi agent） | 2/4 | 2/4（pi timed out after 600s：dab_129、dab_216） | 不適用（`enabled=false`） |
| reqlist_only（deepseek41） | 4/4 | 0/4 | 0/4（`enabled=false`） |
| full_rloop（deepseek41） | 4/4 | 0/4 | **4/4（各 1 輪，claims 7/9/5/5＝26 條）** |

- 12/12 格跑完（stop_reason=None；vq-kax 的 max_calls 修正生效，無 not_run、無
  turn_limit/token_limit/quota 失敗）——a/b 兩發 glm 臂 0/8 格的答題通道停滯在本發消失。
- pi 臂 600s timeout 2/4 再現（b 發為 0/4）＝獨立 infra 失敗模式，不影響 full_rloop 判定。

## 1. full_rloop 4 格 content_reverify 逐格記錄（重發 c）

| task（claims） | status | round 1 verdict | gap_reason | claims（PASS/FAIL/UNKNOWN） | round 2 | diff（fixed/regressed/unresolved） | final_verdict |
|---|---|---|---|---|---|---|---|
| dab_129（7） | ok | UNKNOWN | null | 0/0/7（全 `evidence.unverified=true`） | 未發生（0/1） | null（0/0/0） | UNKNOWN |
| dab_144（9） | ok | UNKNOWN | null | 0/0/9（全 unverified） | 未發生（0/1） | null（0/0/0） | UNKNOWN |
| dab_176（5） | ok | UNKNOWN | null | 0/0/5（全 unverified） | 未發生（0/1） | null（0/0/0） | UNKNOWN |
| dab_216（5） | ok | UNKNOWN | null | 0/0/5（全 unverified） | 未發生（0/1） | null（0/0/0） | UNKNOWN |

- 26/26 claims（7+9+5+5）：**0 PASS、0 FAIL、26/26 UNKNOWN**，detail 全為
  「此條目無可靠程式重算檢查器，依規則標為 UNKNOWN，不准以自評代替」
  ＝checks.py L2793（`item.unverified` 分支、fail-closed）。
- gap_reason 0/4（全 null）；diff 非 null 0/4——**fixed 0/4、regressed 0/4、
  unresolved 0/4，皆為 null，不是「0 個錯誤被抓到」**（diff 只在兩輪都有真實重算
  結果時才記，g3.py 既有守衛）。
- 逐格 verifier 分佈（claim 記錄實值）：dab_129＝answer_kv×5＋tag_format×2；
  dab_144＝answer_kv×9；dab_176＝answer_kv×2＋rowset_filter×2＋tag_format×1；
  dab_216＝kv_recomputed×3＋answer_kv×1＋tag_format×1。

### 代碼路徑（本發控制流實際走完整循環）

1. round 1 答題成功、`cell["answer"]` 落位（full_rloop 4/4）→ 行 1051
   `content_recheck(task_ws, req_set, rd, text)`（g3.py L251）：草稿落 answer.txt →
   `checks.run_requirement_checks(task_ws, …)`（checks.py L2777）程式重算。
2. `task_ws = base/"tasks"/<tid>/"workspace"`（g3.py L942/L1002；base＝任務庫
   `~/dev/ops/ref/bm_tasks/dabench/`）——**檢查時資料檔在位**（4 題 workspace 皆有
   data/CSV，本輪實證）；故 unverified 不是「檢查時缺資料檔」。
3. 26/26 條目帶 `unverified=true`（extract 階段標記；extract.py L734–779 尊重模型
   自帶 unverified＋verifier/參數問題皆 fail-closed 標 unverified；L1039 規則＝
   資料檔缺失才應標）→ checks.py L2788–2794 一律 UNKNOWN。
   **raw 只存 `evidence.unverified=true`，逐條原因未持久化**（extract 報告未入
   g3_result.json）→ 逐題具體原因是未驗證假設，不是本報告可斷言的事實。
4. `content_verdict`（g3.py）：必需條目含 UNKNOWN → UNKNOWN（I-4：未測得≠通過）
   → round 1 verdict 4/4 UNKNOWN。
5. `confirmed_gap`（g3.py L295：必需 FAIL 或缺必要答案項）＝0/4 格
   （0/26 FAIL、0/4 缺答案項——4/4 格 answer 在位）→ 不進 round 2 → diff 全 null。
6. **結論：機制 4/4 格走完整「答題→重驗→裁決→（無已確認缺口→停）」路徑＝H1 達標
   （見 §5）；卡點在需求/檢查層——26/26 條目 unverified，檢查器給不出任何確定性
   裁決，修復循環無從啟動。**

## 2. 逐題方向性結論（4 題、每題帶分母）

問題（2.a）：「需求驅動 R-loop 在該未見題上抓到並修好內容錯誤」？

| task | full_rloop answer | reverify 輪數 | 抓到內容錯誤（已確認缺口） | 修好（fixed） | 方向性結論 |
|---|---|---|---|---|---|
| dab_129（2 答案項） | 1/1（32.20／41.42） | 1/1 | 0/7 條 claim 確定（7/7 UNKNOWN） | 0/1 | **未測得（UNKNOWN），無支持證據** |
| dab_144（6 答案項） | 1/1（45.94／52.02／18.756／16.836／Not Normal×2） | 1/1 | 0/9（9/9 UNKNOWN） | 0/1 | **未測得（UNKNOWN），無支持證據** |
| dab_176（1 答案項） | 1/1（35.5） | 1/1 | 0/5（5/5 UNKNOWN） | 0/1 | **未測得（UNKNOWN），無支持證據** |
| dab_216（2 答案項） | 1/1（5.60／1.96） | 1/1 | 0/5（5/5 UNKNOWN） | 0/1 | **未測得（UNKNOWN），無支持證據** |

- 4/4 題方向一致：**無證據支持**「抓到並修好」；也**無證據反對**——不是「檢查器
  跑完沒有缺口」，而是檢查器對 26/26 條 claim 皆 UNKNOWN（無可靠程式重算檢查器），
  已確認缺口結構性 0/4，修復循環沒有獲得運行機會。
- 口徑：未測得＝UNKNOWN，不是 PASS、不是「沒有內容錯誤」、更不是「R-loop 無效」
  （後者需要 hidden 打分＋≥2 rep；本批 1 rep、hidden_after 12/12 UNKNOWN）。

### 跨臂內容差異（可見、未打分）

| task | native_pi | reqlist_only | full_rloop | 一致性 |
|---|---|---|---|---|
| dab_129 | 無（err） | 32.20／41.42 | 32.20／41.42 | 2/2 項相同 |
| dab_144 | 0.32／0.64／0.153／0.156 | 0.34／0.61／0.164／0.146 | 45.94／52.02／18.756／16.836 | 6/6 項不同（full_rloop 與另兩臂差數十至約百倍；疑似聚合範圍或單位不同——不斷言原因） |
| dab_176 | 31.5 | 35.00 | 35.5 | 3 個不同值 |
| dab_216 | 無（err） | 5.36／1.90 | 5.60／1.96 | 2/2 項不同 |

- 1/4 題跨臂值一致、3/4 題有內容級差異——「內容錯誤」的存在是**可見**的，但誰對誰錯
  無法判定（hidden_after 全 UNKNOWN、無確定性檢查器）＝正是 R-loop 應抓到並修的
  判決，本發它走到了 recheck 但裁決不出（26/26 UNKNOWN）。

## 3. 三發對比（a → b → c）

| 項 | a（05:41Z） | b（07:30Z） | c（10:10Z） |
|---|---|---|---|
| 總 ok | 1/12 | 4/12（native_pi） | 10/12（native_pi 2＋glm 臂 8） |
| full_rloop | 4/4 error（token_limit） | 3/4 error（turn_limit）＋1/4 not_run（quota） | **4/4 ok** |
| full_rloop reverify 輪數 | 0/4 | 0/4 | **4/4（各 1 輪、26 claims）** |
| 卡點 | round 1 答題通道 | round 1 答題通道 | **需求/檢查層（26/26 unverified→UNKNOWN）** |
| pi 臂 | 3/4 timeout（300s） | 4/4 ok | 2/4 ok＋2/4 timeout（600s） |
| tokens（known） | 49744 | 132917 | 383921 |

- **卡點前進：答題通道（a/b 0/8 輪）→ 需求/檢查層（c 4/4 輪、0/26 確定性裁決）**。
  G 系列下一張預註冊問題相應對準檢查層（見 G3.1 凍結檔 §2 H2.0）。

## 4. H1 判定（預註冊判準）

- H1（機制可達性）：「full_rloop ≥1/4 格完成 ≥1 輪 content_reverify，且該輪 ≥1 條
  claim 由 checks 程式重算（PASS/FAIL/UNKNOWN 任一，非模型自評）」。
- c 發：4/4 格各完成 1 輪；26/26 claim 由 checks 程式記錄（UNKNOWN、
  `evidence.unverified=true`、detail 為 checks.py L2793 程式文字——非模型自評）。
- **判定：成立（4/4 ≥ 1/4）。** 誠實標註：「重算深度」＝0/26 確定性裁決（全
  UNKNOWN）——可達性成立，但裁決力為 0；後者是 G3.1 凍結檔的 H2.0 前置問題。

## 5. H2 判定（預註冊判準）

- H2（條件於 H1）：round 1 有已確認缺口（必需 FAIL 或缺必要答案項）的格 → 該格
  round 2 diff 須 fixed≥1 且 regressed=0；若 0 格有已確認缺口 → **not_applicable**
  （不得記通過、不得記否決）。
- c 發：已確認缺口 0/4 格（必需 FAIL 0/26；缺必要答案項 0/4——4/4 格 answer 在位）。
- **判定：not_applicable（依預註冊；非通過、非否決）。**

## 6. 本報告不做的事（紅線複述）

- 不宣稱任何臂 superiority、不宣稱「R-loop 有效/無效」；不填 0、不把 UNKNOWN 當 PASS。
- 未讀 /srv/eval hidden/ 與 scorer.py；未改凍結四檔（repair/extract/checks/run_eval）；
  未改 g3.py；0 model calls（純本地靜態審計＋報告）。
- 同批重發（a/b/c）不得當獨立樣本；本批 1 rep、本地模型（H-12 口徑）。

## 7. 下一步（閉環）

1. G3.1 凍結：`ops/reqloop/g3_1_candidate_hypothesis.md`（H1 成立已記錄；H2 凍結——
   含 H2.0 檢查層可達性前置＋H2.1 抓修；候選 manifest 題單＋發射前預檢查；
   **未經人類核准不得直接發射**）。
2. hidden 打分：10 ok 格 answer（native_pi 2＋reqlist_only 4＋full_rloop 4）——
   人類/vlab 側。
3. 本輪 0 行產品碼，無新 CI 相關改動；CI 裁決照舊不 poll。

## 8. r1440 重發票獨立重驗（P20261111_1115-1）

本票與 0914-2 同範圍重發（票身「目前行為」描述落後於 HEAD：c 解讀與 G3.1 凍結
r1438 已產出、commit 2b0a3c8ad／54d47eaae，0914-2 票尾已收案）。r1440 不信任既有
報告，按本票步驟 1–2 從 raw 逐條重驗：

- raw `~/dev/ops/g3_fire_20261111c/g3_result.json` 20660 B、sha256
  `bd727b930f8e1be5…`＝identity pin（本輪重算一致）；summary 21573 B（重算一致）。
- full_rloop 4/4 格 `content_reverify.enabled=true`、各恰 1 輪：round 1 verdict
  UNKNOWN 4/4、gap_reason null 4/4、`diff` null 4/4（fixed／regressed／unresolved
  皆 null，非「0 個錯誤被抓到」）、round 2 發生 0/4、final_verdict UNKNOWN 4/4
  ——與 §1 表逐一吻合。
- claims 26/26（7/9/5/5）皆 `status=UNKNOWN`、`required=true`、
  `evidence.unverified=true`，detail 全為「此條目無可靠程式重算檢查器，依規則標為
  UNKNOWN，不准以自評代替」；逐格 verifier 分佈重算與 §1 一致（dab_129
  answer_kv×5＋tag_format×2；dab_144 answer_kv×9；dab_176 answer_kv×2＋
  rowset_filter×2＋tag_format×1；dab_216 kv_recomputed×3＋answer_kv×1＋
  tag_format×1）。
- 三臂狀態與 12 格答案值（§0／§2 表）逐格重算一致：native_pi 2ok/2err（dab_129、
  dab_216「pi timed out after 600s」）、reqlist_only 4/4 ok、full_rloop 4/4 ok；
  totals 27 calls／383921 tokens；hidden_after UNKNOWN 12/12。
- 票身「claims 為 None」＝summary 層投影（summary JSON 各 full_rloop 格
  `content_reverify.claims: null`）；raw 層 claims 清單在位（26 條、status
  UNKNOWN）——兩層不矛盾，本報告以 raw 為準。
- 無更正：§1–§5 結論不變（4/4 題未測得（UNKNOWN）、無支持證據；H1 成立 4/4；
  H2 not_applicable；G3.1＝H2.0＋H2.1 凍結不變、核准前不發射、不佔配額）。
