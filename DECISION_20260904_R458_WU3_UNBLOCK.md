# R458：R451 §五3 的「收官輪才第一次可判」是**寫死的**——重跑兌現不了，要改碼

2026-09-04 round725（Opus 5）。**本文件在改任何一行程式碼、且在讀
`power_conform_vs_off5.n_needed_for_5pp` 之前 commit。**

## 一、觸發本輪的觀測

round723 交棒寫著：「§五3 期中掃不到，**收官那一輪才第一次可判**，
收官輪必須重跑 `r456_r451_census.py`」。

r447 本輪已 terminal（`rows 360/360`、三臂 `complete=true, terminal=true`、
`infra_void=0`、`rows_sha256_16=cfed36ff71b871f0`）。照交棒重跑：

```
python3 ops/gain/r456_r451_census.py --run runs/g_r447_conform_lcb2 \
    --json ops/gain/data/r458_r451_census_terminal_asis.json
→ verdict CENSUSED  counts {FORCED_GREEN: 4, UNRESOLVED: 2}
→ R451-§五3: blocked_by_tripwire=true, identity_holds=false, witnesses=0, class=UNRESOLVED
```

**與 round723 的 `r456_census.json` 逐格相同。** 原因在原始碼裡：
`r456_r451_census.py` 的 §五3 記錄是**無條件寫死**的
（`"identity_holds": False, "witnesses": 0, "blocked_by_tripwire": True`），
不看 run 是否 terminal、不讀任何量。**這條「重跑就能判」的承諾結構上兌現不了。**

⚠ 順帶一個必須寫下的自我指認：R456 的事前預測表把 §五3 預測成 `UNRESOLVED`，
而那一格在當時**被工具寫死成 UNRESOLVED** ⇒ 那個 HIT 本身是**強制命中**，
不帶資訊。R456 的既有記錄（`ops/gain/data/r456_census.json`）**本輪一個位元組都不動**，
這句話只寫在這裡與 STATE 裡（記錄不可改、解讀可以補）。

## 二、R451 §五3 的原文與它的兩件證物

> 3. 若補上之後 `power_conform_vs_off5` 的 `n_needed_for_5pp` 大於 LCB2 題庫規模，
>    那是**結論**不是失敗：照實寫「這個比較在本題庫上不可能有解析度」，
>    而且**不准**因此去放寬 P-Z3 的窗口或改寫 UNINFORMATIVE 的措辭。

- **觸發量** `n_needed_for_5pp` ＝ `analyze_r447.analyze()` 的
  `power_conform_vs_off5.n_needed_for_5pp`（`TRIPWIRE_FORBIDDEN` 成員，
  run terminal 之後才准讀）。
- **題庫規模** ＝ `ops/gain/data/lcb_bank_v2.jsonl` 的列數（bank=`lcb2`，
  由 run 的 `summary.json:sampling.bank` 決定要數哪一個檔；對不上就判 UNSCANNED，
  不准拿另一個題庫的數字頂替）。
- **證物 A（P-Z3 窗口）**：`DECISION_20260904_R440Z_LCB2_PREREG.md` 裡**所有含
  `P-Z3` 的行**，逐字元比對 R451 落地時的版本（commit `113f747`）。
- **證物 B（UNINFORMATIVE 措辭）**：`CRITERION_20260903_R670_DELIV_DIFFERENCE_INTERVAL.md`
  裡**所有含 `UNINFORMATIVE` 的行**，同樣對 `113f747` 逐字元比對。
  （R440Z 本身不含 `UNINFORMATIVE` 字樣，這是本輪 grep 過的事實，
  所以證物 B 必須指向 R670 那張區間位置表，否則這半條判準會是空的。）

## 三、判準（**寫在讀 `n_needed_for_5pp` 之前**）

三格分類沿用 R453 §二／R454／R455／R456，**不新增格子、不新增可調參數**。
§五3 的編碼規則：

- `identity_holds = False`（永遠）。理由：觸發與否是**資料相依**的，
  寫不出結構上的不可達證明。⚠ 依 R454 的規則，**寫不出恆等式就照嚴格規則吐**，
  不准為了讓預測成真去湊一條條件式恆等式。
- `witnesses = 1 if trigger_fired else 0`，其中
  `trigger_fired = (n_needed_for_5pp > bank_size)`。
  理由：這條子句只有在觸發之後才有東西可觀察；沒觸發時它沒有被測試到。
- ⇒ `class = EVALUABLE`（觸發）或 `UNRESOLVED`（沒觸發），由既有 `classify()` 給。
- **證物比對是獨立的一步**：`trigger_fired ∧ (證物 A 或 B 有任何一行不同)`
  ⇒ 往 `broken` 押 `R458_clause_violated:R451-§五3`，且 `verdict != CENSUSED`。
  只有證物變、沒觸發 ⇒ 記 `witness_docs_changed_without_trigger`（不押 broken，
  那不是這條子句的證偽事件）。
- run 沒給、run 非 terminal、bank 對不上 ⇒ `UNRESOLVED_UNSCANNED`，
  照 R454 的第三型「安靜量不到」記 `scanned:false` 與理由，
  **不准報成 witness=0**。

## 四、加法式邊界（既有記錄一個位元組不動）

- 不動 `r453_census_round715.json`／`r454_census.json`／`r455_census.json`／
  `r456_census.json`；本輪所有輸出寫**新檔** `ops/gain/data/r458_*.json`。
- `census()` 只新增一個**有預設值**的參數 `run_dir=None`。
  **`run_dir=None` 時輸出必須與改動前逐鍵逐值相同**（由自檢 C13 用改動前的
  `git show HEAD:` 版本現場跑一次比對；不是比 sha 而是比字典）。
- §五3 底下既有的 5 個鍵（`clause`／`falsifier`／`identity`／`identity_holds`／
  `witnesses`）語意不變；新增的只有 `w3_*` 與頂層 `wu3_evaluation`。
  `blocked_by_tripwire` 在有評估時變 `false`——這是**唯一**一個既有鍵會變值的地方，
  且只在 `run_dir` 有給且 terminal 時；`run_dir=None` 時它仍是 `true`。
  （這一條例外明寫在這裡，不是量完才補。）

## 五、事前預測（量之前寫死，量完不准改）

寫這幾行時**已知**：`b/c(CONFORM_vs_OFF5)=[16,8]`、`n=120`、
`bank_size=120`（`wc -l lcb_bank_v2.jsonl`）、`r447_eq5_offline` 裡另一個量
（gate-vs-vote 的 `n_needed_for_5pp=320`）。**未讀** `power_conform_vs_off5` 的任何值。

- **P-R458-1**：`trigger_fired = True`（`n_needed_for_5pp > 120`）⇒ §五3 判 `EVALUABLE`。
  依據：24 個 discordant／120 題的量級，要壓到 5pp 需要數百個配對題，
  而題庫只有 120。（這是**推測**不是量測。）
- **P-R458-2**：證物 A、B 都**沒有**改動 ⇒ `broken` 為空、`verdict=CENSUSED`。
- **P-R458-3**：`run_dir=None` 的輸出與改動前版本**逐鍵逐值相同**（加法性成立）。

## 六、推翻條件（觸發就照實寫，不准當場補判準去修）

1. 若 `trigger_fired=False`（`n_needed_for_5pp ≤ 120`）：P-R458-1 記 **MISS**，
   §五3 照實判 `UNRESOLVED`，**不准**改觸發量的定義（例如改成比 n=120 的樣本數、
   或改成比 MDE）去讓預測成真。
2. 若 P-R458-3 不成立（`run_dir=None` 也變了值）：**回退整個改動**，
   在 STATE 寫「加法式宣稱不成立」，不靠調整比對方式讓它變綠。
3. 若證物 A 或 B 真的有差異：**不在本輪判定是誰改的、也不改回去**，
   照實押 `broken` 並在 STATE 最上面寫給 fable 裁決輪。
4. 若 Y1–Y3 任一突變體只能靠 crash 或靠**沒指名**的自檢條抓到，
   照實記 `Yn:N`，不准把判準降級成 `rc≠0`。

## 七、突變體（每一個都要有指名的自檢條看著它）

| 突變體 | 改什麼 | 指名的自檢條 |
|---|---|---|
| `Y1_w3_trigger_ignores_bank` | `trigger_fired` 恆 True（不比題庫規模） | C14（合成：n_needed ≤ bank ⇒ 必須 UNRESOLVED） |
| `Y2_w3_ignores_doc_drift` | 跳過證物 A／B 比對 | C15（合成：證物被改過 ⇒ 必須押 broken） |
| `Y3_w3_blocked_even_when_terminal` | terminal 也照樣 blocked | C16（terminal ⇒ `blocked_by_tripwire` 必須 False） |

## 八、這份文件不做的事

**不對 r447 下任何收官判斷。** 本輪不寫 CONCLUSION、不判四格、不引用
`delta`／`p_mcnemar`／交付率。§五3 的評估只讀 `n_needed_for_5pp` 一個純檢定力量，
且它是 R451 明文要求「陪著 UNINFORMATIVE 一起落地」的那個量。
收官仍歸 fable 稽核輪，仲裁者：R440Z §三／§六 ＋ R450 §四 ＋ R451 ＋ R452（含 §九）
＋ R453 ＋ R454 ＋ R455 ＋ R456 ＋ **R458**。
