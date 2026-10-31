# e007/e008 · DABench（資料分析題）A/C 對照——研究封包＋預註冊分析（round 725，2026-10-31 寫定，尚未發射）

> 主軸 4（ASSIGNMENT：通用任務驗證，dabstep/dabench/databench）。e001 已跑 dabstep 26 題
> 子集（§8 結果：無可測影響、機制 25/26 zero_ran）；dabench（30 題）與 databench（30 題）
> 從未跑。本封包先寫定假說與判準，smoke 過才發全盤（ASSIGNMENT「新實驗先 4–8 格 smoke」）。

## 1. 問題與可證偽假說
在真實使用者環境（乾淨 HOME、pi、C 臂只多 `vacant install --agents pi`），
DABench 30 道資料分析題上，裝 Vacant 是否改變通過率？成本多少？若無差異，機制層面的原因是什麼？

- **H0（主假說，由 e001-dabstep §8 外推）**：機制不判內容正確性（H-2 同構），模型用
  workspace 真資料計算 → unsourced 罕發、C 臂機制多 zero_ran=true；**C ≈ A**，且 C 臂
  calls/token/wall 成本 ≥ A。
- **H1（對立）**：模型 L-fake（不寫答案檔／不讀輸入資料／虛構數值）→ missing_output／
  unsourced kickback 使 agent 修正重跑 → **C_only > A_only**，且每個 C_only 對必有機制
  介入記錄（zero_ran=false＋findings＋final_action=allow）；無記錄的對不算。
- 「無用」事先定義：無可歸因機制的 C_only 對、或 C_only ≤ A_only、或 C/A 成本比 > 2
  （calls 或 tokens 任一）→ 記「無可測影響（或不值成本）」，不是「反證無效」。

## 2. 基準與對照
- **基準**：e001-dabstep 26 對（repo FINDINGS 2026-10-29 條：A 13/26 vs C 14/26、唯一分歧
  對 dabstep-24 無任何機制介入、25/26 格 zero_ran=true）——目前唯一既有的通用題 A/C 結果。
- **正向對照（門會動）**：e001-dabstep 9 格 C 臂 missing_output kickback 後 agent 補檔、
  final_action=allow——機制能實際踢回並回收。
- **負對照（故意壞情況）**：C 格 agent 始終不寫出要求的答案檔 → missing_output kickback
  應觸發（補檔或逾時）；若 kickback 不觸發＝機制在此 bank 失效，該格記 UNKNOWN（非 PASS）。
- **跨 bank 對照**：若 e007/e008 再見 C≈A 且無歸因，則「通用題無可測影響」是機制結構限制
  的跨 bank 模式（非單 bank 偶然）；若 C>A 且逐對歸因成立，則推翻「通用題一律無用」外推。

## 3. 代碼改動
- **無（純量測實驗）**：不改產品代碼、不改測試、不碰 scorer/題（scorer 與 hidden/ 為
  root 所有，依規不讀）。
- 產物：2 個 labd 工作檔（smoke／full）＋ REPORT.{json,md} ＋ 機制審計 JSON ＋
  本封包 §5 回填 ＋ FINDINGS.md 新條目。

## 4. 來源（git SHA、題庫、runs）
- 題庫：`/srv/eval/staged/dabench`（30 題：dab_035…dab_732，見 §4.1）。
- agent：pi（與 e001 同，保 A/C 對照可比與跨 bank 外推成立）。
- 模型：1004 gemma-4-12b-it-qat（全實驗室同一模型）。
- vacant_sha（C 臂）：`9071b9f1bdfc25275bb7f1a6502205beaa4d8cad`（現 HEAD；e001 的 C 臂
  用 dd2c6746——**build 差異是跨實驗混淆項**，跨 bank 結論只說「模式」，不說「同 build Δ」）。
- runs：`/srv/vlab/runs/e007_dabench_smoke/`（4 格）、`/srv/vlab/runs/e008_dabench_pi_AC/`（60 格）。
- 發射順序（labd 逐 job 串行，不並行搶 1004）：
  `07_e006_opencode_polyglot`（running，170 格）→ `08_e007_dabench_smoke` →
  e008 full（smoke 過關後，下輪發射）。

### 4.1 smoke 選題規則（確定性、非 cherry-pick）
取字典序前 2：`dab_035`、`dab_039`（30 題 `sort | head -2`）；full e008 覆蓋全部 30 題
且含此 2 題——smoke 對全集無抽樣偏，只作「可測性」關卡（非全部 infra、非全部逾時）。

## 5. 預註冊分析（結果出來照此路徑；不許事後挑數）
- 官方數據＝REPORT.json（`report.py <exp> --rescore` 從原始格重算）；成效必隨成本同報
  （ASSIGNMENT 紅線）。
- 主讀（n=30 對、1 rep、低力；McNemar exact 2-sided，描述性為主）：
  配對 A/C 分歧對 A_only=a / C_only=c；a=c=1→p=1.0、a=2,c=0→p=0.5（低力＝預先聲明）。
- 每個 C_only 對逐格驗證（否則不歸因機制）：zero_ran=false ＋ findings(kind+sub) ＋
  final_action=allow；不滿足者記「跨跑隨機差異、非機制歸因」。
- 成本（描述性）：calls/success、tokens/success、mean wall、timeout；C 臂 vacant_home_bytes（主軸 2）。
- 解讀分支（只有這三條，事先寫定）：
  1. **C ≈ A**（分歧對各 ≤1 或對稱）→ 記「無可測影響（機制不判內容正確性）」，
     與 e001-dabstep 同構；**不再發射 databench 同設計複測**（邊際收益递减），資源轉主軸 2。
  2. **C > A**（c>a）→ 逐對驗證後只取歸因子集；任一對不可歸因即不計入結論。
  3. **C < A**（a>c）→ 逐格查：(a) kickback 消耗輪次/逾時（wall/timeout）；(b) 模型被
     kickback 後劣化；(c) unsourced 誤傷 → 若 (c)：BACKLOG P0，誤傷樣本入
     tests/test_noncode_samples.py 回歸。
- 不許把 dabench 與 dabstep/polyglot_py 併成一個 n（ASSIGNMENT 紅線）。
- 不讀 hidden 題內容解釋任何格。
- 無法判定的格是 UNKNOWN，非 PASS、非「不存在」。

## 6. 發射與驗收
- smoke `e007_dabench_smoke`（4 格：dab_035/dab_039 × A/C）：
  過關＝非全 infra、非全逾時、≥1 格出分（pass 或 fail 皆可）→ 發 e008 full；
  不過→不發 full，先修 infra 並記 STATE.md。
- full `e008_dabench_pi_AC`（60 格＝30 題×A/C×1 rep）：完賽 →
  `report.py e008_dabench_pi_AC --rescore` → 回填 §5 結果＋FINDINGS.md（可說/不可說）。

### 6.1 smoke 實測結果（2026-10-31 22:58 完賽，過關）
- 來源：`REPORT.json`（ops/vlab/runs_e007_dabench_smoke/REPORT.json，rescore_checked=true；cost 數字同列）。
- cells_scored=4，0 infra，0 timeout。
- A 臂 2/2（100.0%，calls 16.0，tokens 323,163，mean wall 66.0s）。
- C 臂 2/2（100.0%，calls 124.0，tokens 3,390,335，mean wall 718.0s，vacant_sha=9071b9f1）。
- 配對 A_vs_C：2 題平手（McNemar p=1.0；A_only=0、C_only=0）。
- 判準（§6）：非全 infra、非全逾時、4 格皆出分且全 PASS（高於 ≥1 格出分門檻）→ smoke 判定過關。

## 7. 限制
- 單模型（12B 量化）、單 agent（pi）、1 rep、n=30；數字不遷移到其他模型/預算（H-12 同構）。
- scorer 隱蔽（root）：只见 pass/fail 與 answer_exists，不能解釋格內失敗原因（機制記錄除外）。
- e008 與 e001 C 臂 vacant_sha 不同（dd2c6746 → 9071b9f1）：跨 bank 比較是「模式」不是「同 build Δ」。
- 本實驗量測「裝與不裝」的差異，**不量測 Vacant 各功能各自的效果**（要那個是 e003 設計，
  e001 已判「無可測影響」故未發射）。

## 8. 回滾
- 無產品代碼改動；實驗無效時只留 runs/ 原始格與本封包，無需代碼回滾。
- 若 C 臂 install 路徑壞掉（smoke C 格全 infra）＝產品側問題：開 P0 工單，不記為實驗結論。

## 9. 獨立再驗證
```
python3 /srv/vlab/bin/report.py e007_dabench_smoke --rescore    # smoke（4 格）
python3 /srv/vlab/bin/report.py e008_dabench_pi_AC --rescore    # full（60 格）
# 機制審計：逐 C 格讀 vacant_home.tgz 的 events.jsonl（zero_ran/findings/final_action），
# 做法同 e001 AUDIT_dabstep_mechanism.json；不讀 hidden/、scorer.py。
```
