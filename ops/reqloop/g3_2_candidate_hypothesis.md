# G3.2 預註冊假說（H0 確定性裁決門＋H1 抓修；篩選後相容題選題清單）

- 狀態（2026-11-11 r1473）：**H1 已判定（P20261111_2319-2）：`H1_REFUTED`**——
  G3.2 發射（r1472、核准 g3_vq-1zf_fire_20261111 approved=true）：4/4 格 ok、各 1 輪、
  26/26 claims UNKNOWN（PASS 0/26、FAIL 0/26）、0/4 格確定性裁決→**H1(a) 0/4 觸發否決**；
  0/4 格已確認缺口→H1(b) `not_applicable`（不記通過不記否決）。第 2 輪 0/4 未執行＝
  UNKNOWN 非缺口、機制如設計（diff 全 null）。成本 8 calls/128923 tok（日額度 6.45%）；
  hidden_after 4/4 UNKNOWN。
  新發現：H0 門跨獨立呼叫不穩定——dab_725 預跑 2/7 確定性 vs fire 0/6（claim 分解
  7→6）；其餘 3/4 題兩輪一致（0→0）。→ 下一預註冊問題見 §6（G3.3）。
  停止規則：「H1 否決→停止、上報人類」已觸發；「連續 2 發無已確認缺口被消解」
  （G3 c＋G3.2）事實亦觸發。G 系列待人類裁決（§6 G3.3 或終止）。
- 狀態（2026-11-11 r1469）：**H0 預跑門已執行（P20261111_2119-2）：`H0_MET`**——
  4 凍結題各 1 次 extract（4 calls / 29914 tok，報告 `ops/audits/g3_2_h0_prerun_report.json`）：
  dab_725 有 2/7 條確定性 claim（R1/R6，`answer_kv`＋numeric keys，凍結 extract/checks 判定
  unverified=False、可 PASS/FAIL 重算）；dab_587/657/517 均 0 條確定性（全 unverified：
  deliverable_not_in_request／unsupported_recompute_type／model_declared_unverified／unknown_verifier）。
  依票紅線「預跑不擅自點火完整批」：完整批（full_rloop×4 格）待人類核准，不進默認。
  前態（r1468）：預註冊凍結完成（manifest＋tasks 凍結副本＋precheck，0 model calls）；
  r1464：預註冊草擬、未改凍結四檔（repair/extract/checks/run_eval）。
- 依據（全部 in-repo 證據）：
  - G3 c 發：`ops/audits/g3_fire_20261111c_summary.json`＋解讀檔（12/12 格跑完、
    機制可達性 H1 4/4 成立、26/26 claims unverified→UNKNOWN）
  - G3.1 H2.0 extract 預跑：`ops/audits/g3_1_h20_prerun_report.json`（4 題 0/4 具
    確定性 claim，`H2_0_REFUTED`；4 calls / 27240 tok）；verdict 記錄於 r1447a
    （commit `3e45e212`），至今仍有效
  - 題庫：`/home/user1/dev/ops/ref/bm_tasks/dabench/`（30 題）；排除集來源＝
    g3_1 manifest（`ops/reqloop/g3_1/manifest.json`，seen_set_source 欄）
  - 凍結能力集（只讀）：`vacant_network/reqloop/checks.py`
    SUPPORTED_VERIFIERS／KV_RECOMPUTE_TYPES／PLAIN_RECOMPUTE_TYPES；
    `vacant_network/reqloop/extract.py` 重算類型
  - 本輪新工具：`ops/audits/g3_2_bank_screen.py`（≤120 行、--selftest 9 controls PASS、
    輸出 schema `vacant.g3_2_bank_screen/1`）

## 1. G3.1 失敗模式（G3.2 重選題的依據）

G3.1 預跑 0/4 的逐條原因分兩族（見 prerun report `reason_distribution`）：

1. **`deliverable_not_in_request:*`**（dab_035 R1/R2、dab_055 R4、dab_105 R1…）——
   extract 呼叫的請求句沒涵蓋答案項 → claim 結構性 unverified。
2. **`unsupported_recompute_type:mean_col`**（dab_055 5 條中 4 條）——extract 呼叫
   產出的重算類型不在凍結重算集內（該題需求本身對應 `col_stats`）→ G3.1 §3 預檢查
   3「verifier 不在表＝期望 unverified」成真。

**口徑推論**：G3.1 四題的答案項與資料檔俱在、詞彙屬描述統計家族，仍 0/4——
故「題面詞彙相容」只提高確定性裁決的先驗機率，**不替代** extract 預跑門；
G3.2 保留 H0 門作最終裁決，題庫篩選只縮候選集。

## 2. G3.2 可證偽假說（帶分母與停止規則）

### H0（門，fail-closed）——篩選後題面的確定性可裁決性
> §3 選題（4 題、各 1 次 extract 預跑）中，**≥1/4 題存在 ≥1 條 required claim
> 可給確定性裁決（PASS 或 FAIL、程式重算）**。
- **否決條件：0/4 題 → 不發完整批、G3.2 停止、上報人類**；不再新增同路徑
  （同題重試／靜態 prompt／錯誤字串 regex）工單。
- 口徑：extract／parse 失敗＝空集合，不計 MET（同 G3.1 預跑）；UNKNOWN 既非
  裁決亦非通過（I-4）；若再 0/4，瓶頸判定＝需求／extract 層，是否解凍
  extract.py／checks.py＝人類裁決（凍結四檔本系列不得改）。

### H1（條件於 H0 成立）——full_rloop 達標 H2.0 級裁決並修復內容錯誤（H2.1 級）
> §3 選題的 full_rloop 格中：
> (a) **≥1/4 格**完成 ≥1 輪 content_reverify，且該輪 ≥1 條 claim 由 checks 程式
> 重算給確定性裁決（H2.0 級）；且
> (b) round 1 有已確認缺口（≥1 必需 FAIL 或缺必要答案項）的格中，**所有該等格**
> round 2 diff fixed≥1 且 regressed=0（H2.1 級）。
- **若 0/4 格有已確認缺口，H1(b) 記 `not_applicable`（不得記通過、不得記否決）**。
- **否決條件**：(a) 0/4 格達確定性裁決；或 (b) ≥1 格 round 1 有已確認缺口而
  該格 fixed=0 或 regressed≥1。
- 口徑：diff 只在兩輪都有真實重算結果時才記（g3.py 既有守衛）；單 rep、方向性；
  不宣稱臂 superiority；不外推到其他模型／題（H-12）。
- **明確非目標**：不回答「R-loop 比基線修得多」——需 hidden 打分（人類/vlab 側）
  ＋≥2 rep，屬更後問題，不預註冊、不預先結論。

## 3. 選題清單（前 4 題，凍結）

- **篩選**（`ops/audits/g3_2_bank_screen.py`，9 controls PASS）：bank 30 題，
  排除 g3_1 manifest tasks（dab_035/055/105/218）∪ seen_set（dab_039/057/129/144/
  176/216/378/426/427/507＋bank 外 dabstep）＝15 個 id、14 個在 bank → 候選 16 題；
  分級 6 COMPATIBLE／9 PARTIAL／1 INCOMPATIBLE。
- **選題＝top4**（全 COMPATIBLE：答案項與資料檔俱在，需求詞彙全落在凍結重算家族；
  排序＝分級→凍結家族數→題號，決定性可重算）：

| # | task | 答案項（required） | 對應凍結重算家族 |
|---|---|---|---|
| 1 | dab_725 | @mean1/@median1/@mean2/@median2/@mean3/@median3（6） | col_stats（mean/median）、max_row_first（top3）、unique_count |
| 2 | dab_587 | @correlation_coefficient（1） | pearson2 |
| 3 | dab_657 | @mean_close/@median_close/@std_close（3） | col_stats（mean/median/std）、null_count |
| 4 | dab_517 | @correlation_pclass_fare（1） | pearson2 |

- **發射範圍**：full_rloop（待驗機制臂）× 4 題；基線臂不進默認範圍（同 G3.1 §3；
  如人類核准對照臂，按 c 發成本另計）。
- **發射前預檢查（靜態、0 model calls）**：
  1. 任務庫資料檔在位（本輪腳本已實證 16/16 候選 `data_files` 非空）；
  2. 詞彙→能力映射逐項落在凍結集內（腳本 --selftest C1 控制）；
  3. 篩選輸出（top4＋ranking＋排除集）落 audit、hash 入 manifest（防 cherry-pick）。
- **extract 預跑門（H0 操作化，4 題各 1 次 extract 呼叫）**：0/4 → 不發完整批、
  上報人類；≥1/4 → 發完整批、進 H1。
- **選題口徑**：不讀 hidden/scorer、不靠隱藏分反推；只依可見 goal.md＋凍結能力集；
  同批重發不得當獨立樣本（G3.1 §3 口徑）。

## 4. 成本與停止規則

- **預算門**（同 g3_1 manifest budget 欄，核准後入 manifest）：`max_cells=4`、
  `timeout_s_per_round=300`、`daily_token_cap=2000000`、`quota_fail_closed=true`、
  不 retry；成本從 raw usage 讀、缺值 UNKNOWN 絕不填 0；撞 2M/日 額度即停；
  glm CLI 唯一入口（--enabled-tools none、空暫存目錄）、不准反向代理／轉額度。
- 範圍：≤4 extract 預跑＋≤4 full_rloop 格（1 臂×4 題）；參考：G3.1 預跑實測
  27240 tok/4 calls；c 發 383921 tok/27 calls（3 臂×4 題、1 rep）。
- **停止規則**（承接 2026-11-06 定案第 3 條＋G3.1 教訓）：
  - H0 否決（0/4 確定性 claim）→ 停止同路徑工單、上報人類；
  - H1 否決，或連續 2 發無已確認缺口被消解 → 停止、上報人類；
  - 不得對每題未解錯誤加「錯誤字串 regex／靜態 prompt／同題重試」工單。

## 5. 核准與凍結流程（G 系列自續）

預註冊（本檔＋篩選輸出 hash）→ **人類核准** → manifest 凍結（選題＋臂＋模型＋
預算＋停止規則＋§3 預檢查 3 條證據入 manifest）→ extract 預跑門（H0）→ 完整批
（僅當門過）→ audit 摘要（同 c 發腳本口徑）→ 解讀（帶分母、UNKNOWN 不填 0）→
下一輪候選假說。

**核准前：不發射、不佔配額、不改凍結四檔。**

## 6. 下一預註冊問題：G3.3——H0 門跨獨立呼叫穩定性（2026-11-11 提出，待人類核准）

### 依據（全部 in-repo 證據）
- G3.2 結果：`ops/audits/g3_2_fire_summary.json`＋`ops/audits/g3_2_interpretation.md`
  （H1_REFUTED；26/26 UNKNOWN；主因 deliverable_not_in_request 20/26）。
- H0 門不穩定證據（§4 解讀）：dab_725 同 input_sha256、同模型 glm53，兩次獨立
  extract 呼叫→確定性 claim 2（預跑 r1469）→0（fire r1472）、claim 分解 7→6；
  dab_587/657/517 兩輪一致（0→0）。
- 機制口徑：H0 門＝單次 extract 呼叫；門量的是「該次呼叫」，不是「該題」。

### H2（G3.3 可證偽假說，帶分母）
> 同題 dab_725（唯一預跑 H0_MET 題）、同模型 glm53、同 input：3 次獨立 extract
> 呼叫（已有 2 次＝預跑＋fire，另 1 次新呼叫）中，**≥2/3 次產出 ≥1 條確定性
> claim（PASS/FAIL、程式重算）**。
- 既有 2 點已含 1 達 1 未達，故 H2 等價於：**第 3 次獨立 extract 呼叫產出
  ≥1 條確定性 claim**。
- **否決條件**：第 3 次呼叫 0 條確定性（即 1/3 達）→ 單呼叫 H0 門為呼叫隨機、
  對「fire 時同題能否產出確定性重算」的保證力弱；修正方向（多呼叫共識門／
  交付物命名強化／解凍 extract.py＋checks.py）＝人類裁決，本系列不改凍結四檔。
- **成立（第 3 次 ≥1 條，即 2/3 達）**：單呼叫 H0 門可重現，G3.2 fire 失靈為
  孤立漂移；G 系列可續（下候選＝多呼叫共識門，見任務單 2）。
- 口徑：UNKNOWN 非裁決非通過（I-4）；extract/parse 失敗＝空集合、不計確定性
  claim（同 H0 門口徑）；單 rep 方向性；不宣稱 superiority；不外推其他模型/題（H-12）。

### 範圍與成本
- 1 次 extract 呼叫（dab_725 單題）、0 answer 呼叫；參考 7313 tok（預跑 dab_725
  實測）；成本從 raw usage 讀、缺值 UNKNOWN 不填 0。
- 不讀 hidden/scorer；不碰 G3.1/G3.2 既有產物；0 產品碼改動。

### 停止規則
- H2 否決 → G 系列停止、上報人類；不得加同題重試／靜態 prompt／錯誤字串 regex 工單。
- H2 成立 → 進 §6 任務單 2（仍需人類核准）。

### 後續任務單（方向，各需獨立人類核准）
1. **G3.3**（本問）：H2 穩定性檢驗（1 呼叫，最便宜否決）。
2. 若 H2 成立 → **G3.4 候選**：3 呼叫共識 H0 門（≥2/3 達才發完整批）——
   機制層改動（g3.py 依核准工單可改），需凍結面重審＋新預註冊。
3. 若 H2 否決 → **人類裁決**：解凍 extract.py／checks.py（交付物命名強化／
   重算集擴充）或終止 G 系列。
