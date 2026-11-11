# G3.1 預註冊假說（H1 成立已記錄；H2 凍結＝H2.0 前置＋H2.1 抓修；候選 manifest 題單）

- 狀態（2026-11-11 r1438 更新）：**H1 成立（已記錄）；H2 凍結；候選題單凍結。
  G3.1 發射須人類核准，核准前不得發射、不佔配額。** 本輪 0 model calls、0 行產品碼。
- 依據（全部 in-repo 數據，本輪實證）：
  - `ops/audits/g3_fire_20261111c_summary.json`（21573 B）＋ raw `~/dev/ops/g3_fire_20261111c/g3_result.json`
    （20660 B、sha256 與 identity pin `bd727b93…` 一致）
  - `ops/audits/g3_fire_20261111c_interpretation.md`（本輪解讀：三發卡點
    「答題通道（a/b）→ 需求/檢查層（c：26/26 claims unverified→UNKNOWN）」）
  - `ops/audits/g3_fire_20261111_summary.json`／`…b_summary.json`／`…b_interpretation.md`
  - 任務庫 `~/dev/ops/ref/bm_tasks/dabench/`（base/tasks/<tid>/workspace 實存
    goal.md／contract.md／data/CSV——**檢查時資料檔在位**，故 c 發 26/26 unverified
    不是「檢查時缺資料檔」；逐條原因 raw 未持久化＝未驗證假設）
  - 代碼（只讀）：g3.py L251/L295/L942/L1002/L1051；checks.py L2777/L2788–2794；
    extract.py L734–779（unverified 標記）／L1039（提示規則）

## 1. c 發實證摘要（凍結依據）

1. **通道層已解**：glm 臂 reqlist_only 4/4 ok＋full_rloop 4/4 ok（a/b 發 0/8）；
   stop_reason=None、12/12 格跑完；vq-kax 的 max_calls 修正生效。
2. **卡點移到需求/檢查層**：full_rloop 4/4 格完成 content_reverify（1 輪、26 claims），
   但 26/26 條目 `unverified=true`（checks.py L2788–2794 → UNKNOWN）→ 已確認缺口 0/4
   → 修復 0/4 → fixed/regressed/unresolved 全 null（非「0 個錯誤被抓到」）。
3. **26/26 unverified 的逐條原因未持久化**（raw 只有 `evidence.unverified=true`；
   extract.py 列出的可能來源＝模型自帶 unverified／verifier 參數問題／資料檔缺失
   （L734–779、L1039）；任務庫資料檔實存，排除「檢查時缺資料檔」）→ G3.1 發射前
   必須先把逐條原因持久化（§3 預檢查第 1 條），否則同條件重發只是重複不可解讀的
   UNKNOWN。
4. **跨臂內容分歧可見**：3/4 題三臂值不同（dab_144 full_rloop 與另兩臂差數十至
   約百倍；dab_176 31.5／35.00／35.5；dab_216 5.36/1.90 vs 5.60/1.96），1/4 題兩
   glm 臂一致（dab_129 32.20/41.42）——「內容錯誤」存在可見，但無確定性檢查器
   裁不出＝R-loop 應抓的對象。
5. **成本**：383921 tokens／27 model calls／1 rep（cells 355734＋extract 28187、
   known_usages=14；2 err 格 tokens=UNKNOWN 不填 0）；hidden_after 12/12 UNKNOWN。

## 2. G3.1 可證偽假說（帶分母與停止規則）

### H1（已記錄）——機制可達性
> （判準同候選版）full_rloop ≥1/4 格完成 ≥1 輪 content_reverify，且該輪 ≥1 條
> claim 由 checks 程式重算（PASS/FAIL/UNKNOWN 任一，非模型自評）。

- **判定：成立（4/4，c 發 20261111c；見解讀檔 §4）。** 誠實標註：確定性裁決
  0/26（全 UNKNOWN）——可達性≠裁決力；後者即 H2.0。H1 不再進 G3.1 判定，本條關閉。

### H2.0（前置，可證偽）——檢查層可達性（新增，基於 c 發實際行為）
> 在 G3.1 發射（§3 題單）的 extract 預跑中，**≥1/4 題存在 ≥1 條 required claim
> 可給確定性裁決（PASS 或 FAIL、程式重算）**——即該題 required claims 不是全數
> unverified→UNKNOWN。
- **否決條件：0/4 題達到 → H2.0 否決** → 依預註冊停止：**不發完整批、不再新增同路徑
  （同題重試／靜態 prompt／錯誤字串 regex）工單，上報人類**（瓶頸在需求/檢查層；
  凍結四檔 extract.py／checks.py 本系列不得改，是否解凍或換路徑＝人類裁決）。
- 理由：c 發 26/26 unverified→已確認缺口結構性 0/4→H2.1 必然 not_applicable；
  在「檢查器能否給確定性裁決」未答之前，重發完整批（≈c 發量級成本）只能重複
  not_applicable。先問 H2.0，再問 H2.1。

### H2.1（條件於 H2.0 成立）——抓到並修好一類內容錯誤
> 在 round 1 有已確認缺口（≥1 必需 FAIL 或缺必要答案項）的 full_rloop 格中，
> **所有該等格** round 2 diff 有 fixed≥1 且 regressed=0；若 0/4 格有已確認缺口，
> H2.1 記 **not_applicable**（不得記通過、不得記否決）。
- **否決條件：≥1 格 round 1 有已確認缺口，且該格 fixed=0 或 regressed≥1。**
- 口徑：diff 只在兩輪都有真實重算結果時才記（g3.py 既有守衛）；UNKNOWN 既非缺口
  亦非通過（I-4）；方向性、單 rep；不宣稱臂 superiority；不外推到其他模型/題
  （H-12）。
- **明確非目標**：G3.1 不回答「R-loop 比基線修得多」——那需要 hidden 打分
  （人類/vlab 側）＋≥2 rep，屬 G3.2+ 的問題，不預註冊、不預先結論。

## 3. 候選 manifest 題單（核准後才入批；同批重發不得當獨立樣本）

| # | task | 批內狀態 | 答案項（required） | 家族 |
|---|---|---|---|---|
| 1 | dab_055 | 本批 G3 系列未見（任務庫在位） | mean_cases（1） | 描述統計 |
| 2 | dab_035 | 本批 G3 系列未見 | removed_outliers_count（1） | 描述統計（outlier 計數） |
| 3 | dab_105 | 本批 G3 系列未見 | correlation_coefficient（1） | 描述統計 |
| 4 | dab_218 | 本批 G3 系列未見 | correlation_coefficient（1） | 描述統計 |
| 5 | （備選）dab_039 | 核准後可換入 | is_normal／mean／std（3） | 描述統計＋正態檢定（較重） |
| 6–9 | （可選對比組）dab_129／dab_144／dab_176／dab_216 | a/b/c 已發 3 批；**只在全批核准且人類准許預算時入批**，作同批對照，非獨立樣本 | 2／6／1／2 | 描述統計 |

- **發射範圍**：full_rloop（待驗機制臂）× 題單 1–4（備選 5 可換入其一）；
  native_pi／reqlist_only 基線臂**不在 G3.1 默認範圍**（G3.1 問的是「檢查層＋
  修復循環」，基線對照由 c 發數據提供；如人類核准對照臂，按 c 發成本計）。
- **發射前預檢查（靜態、0 model calls，逐題）**：
  1. **持久化逐條 unverified 原因**：在 g3.py 呼叫端（非凍結）把 extract 報告
     （每條 unverified=true／false＋來源）寫入 audit raw——g3.py 未凍結、
     extract.py 邏輯不改；**不做此條不得發射**（否則重複 c 發的不可解讀 UNKNOWN）。
  2. 任務庫 workspace 資料檔在位（dab_055/035/105/218：本輪已實證結構
     instruction.txt＋workspace/{goal.md,contract.md,data/}）；缺資料檔的題
     → 預記期望 UNKNOWN 條目或換題。
  3. verifier 類型在 checks.py 支援表內（answer_kv／tag_format／rowset_filter／
     kv_recomputed 等；不在表內＝期望 unverified，預記）。
- **extract 預跑門（H2.0 的操作化檢查，4 題各 1 次 extract 呼叫，低成本）**：
  預跑產出逐題 claim 表→數「確定性裁決 claim」→**0/4 題 ≥1 → 不發完整批，
  H2.0 記否決、上報人類**；≥1/4 題 → 發完整批，進 H2.1。
- 選題口徑：不讀 hidden/scorer、不靠 hidden 分反推規則；只要求「可見內容檢查
  可給結構性反例」；候選題來自同一 dabench 庫（同源、同家族）。

## 4. 成本與停止規則

- 預算項同 vq-kax 工單：daily_token_cap 2M、quota_fail_closed、不 retry；
  缺值 UNKNOWN 不填 0。預算參考：c 發實測 383921 tok／27 calls／1 rep
  （3 臂×4 題）；G3.1＝1 臂×4 題＋4 次 extract 預跑，實測記錄。
- 停止規則（承接 2026-11-06 定案第 3 條＋c 發教訓）：
  - H2.0 否決（0/4 確定性 claim）→ 停止同路徑工單、上報人類；
  - H2.1 否決，或連續 2 發無已確認缺口被消解 → 停止、上報人類；
  - 不得對每題未解錯誤加「錯誤字串 regex／靜態 prompt／同題重試」工單。

## 5. 核准與凍結流程（G 系列自續）

H1（成立、已記錄）＋H2.0/H2.1（凍結、本檔 §2）→ **人類核准** → manifest 凍結
（題單＋臂＋模型＋預算＋停止規則＋§3 預檢查 1 落地證據入 manifest、hash 入 audit）
→ 發射（新 out_dir，如 g3_fire_G31_*）→ extract 預跑門（H2.0）→ 完整批（僅當
門過）→ audit 摘要（同 c 發腳本口徑）→ 解讀（帶分母、UNKNOWN 不填 0）→ G3.2 候選
假說。

**核准前：不發射、不佔配額、不改凍結四檔。**
