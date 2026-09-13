# R529 收官稽核（Fable，2026-09-12）：跨題庫之下，H-MIX 贏單發、不贏重抽

預註冊：`DECISION_20260911_R529_CROSS_BANK_PREREG.md`（v2，發射前凍結於 `43a5cbe`）。
資料：`runs/g_r529_*`（37 塊、716 題 × 三臂 OFF／CONFORM／HMIX ＝ 2,148 列，infra_void 0，37 塊 terminal）。
分析器：`ops/gain/analyze_r529.py`（`e7a6b88`，13:12:56Z 落地，早於第二塊收官；首塊 `lcb3m_a1` 在它之前收官，見預註冊 §七-1）。
產物：`ops/gain/replay/r529/r529_analyze.json`、`vgt_v2_<block>.json` × 37。
三方對帳：分析器（A）／不讀分析器的獨立重算（B）／對帳者第三次直接掃檔（C）——**七類仲裁欄位三方逐位元相同**。

## 〇、一句話

**在三個真來源、四個互斥題目集上，H-MIX 對單發的優勢每一集都在（+5.9 到 +12.2 pp，合併 p_adj 2.0e-8），
對同預算重抽 CONFORM 的優勢只剩 +0.6 到 +3.7 pp（合併 31/23，p_adj 0.341）。R460 在 LCB v2 上量到的 +13.33 pp
沒有在任何一集出現。R529 四狀態＝INCONCLUSIVE；R460 的推翻鍵未觸發，但 lcb3_medium 是 6/5，差一題。**

「沒被推翻」與「複製到了」是兩件事，本檔不合寫成一句。

## 一、跑了什麼

| 項目 | 值 |
|---|---|
| 題目集 | LCB v3 medium 135（7 塊）、LCB v3 hard 54（3 塊）、HumanEval+ 156/164（8 塊；§一-2 排除 8 題）、MBPP+ 371（19 塊） |
| 臂 | OFF（單發）、CONFORM（重抽不回饋，最多五份）、HMIX（回饋迴圈）；預算 5 通／32k token／900 秒 |
| 模型／後端 | gemma-4-12b-it-qat Q4_0（兩台 gguf sha256 相同）；1003（LM Studio 0.4.24）四串＋1004（0.4.17）一至四串；`ops/gain/backend/BACKEND_RELOAD_1003_20260911.md` |
| 時間 | 首塊 11:04Z（排程器隨即崩潰，見 §六-4）；重發 13:08Z；全部收官 23:18Z |
| 佇列 | 四集輪流交錯（Fable 於發射前改，理由＝題目集×後端混淆） |

## 二、逐集數字（三方一致）

| 題目集 | n | OFF 交付 | CONFORM 交付 | HMIX 交付 | H−C b/c | Δ_C pp | H−O b/c | Δ_O pp |
|---|---:|---:|---:|---:|:---:|---:|:---:|---:|
| LCB v3 medium | 135 | 115＝85.19% | 125＝92.59% | 126＝93.33% | 6/5 | +0.74（p 1.000） | 17/6 | +8.15（p 0.0347） |
| LCB v3 hard | 54 | 38＝70.37% | 41＝75.93% | 43＝79.63% | 5/3 | +3.70（p 0.727） | 7/2 | +9.26（p 0.180） |
| HumanEval+ | 156 | 129＝82.69% | 147＝94.23% | 148＝94.87% | 5/4 | +0.64（p 1.000） | 24/5 | +12.18（p 0.00055） |
| MBPP+ | 371 | 277＝74.66% | 295＝79.51% | 299＝80.59% | 15/11 | +1.08（p 0.557） | 31/9 | +5.93（p 0.00068） |
| **合併** | **716** | **559＝78.07%** | **608＝84.92%** | **616＝86.03%** | **31/23** | **+1.12** | **79/22** | **+7.96** |

逐集 p 為未校正雙尾精確 McNemar；區間未做多重比較調整；仲裁以 analyzer 為準。

交錯的成品（accepted 但隱藏測資不過）與拒交：

| 題目集 | OFF 交錯 | CONFORM 交錯／拒交 | HMIX 交錯／拒交 |
|---|---:|---:|---:|
| LCB v3 medium | 20 | 9／1 | 6／3 |
| LCB v3 hard | 16 | 11／2 | 7／4 |
| HumanEval+ | 27 | 6／3 | 6／2 |
| MBPP+ | 94 | 56／20 | 58／14 |

## 三、主指標、四狀態、推翻鍵、宣稱句

| 主指標（家族 2，Holm） | b/c | n_discordant | p | p_adj | 成立 |
|---|:---:|---:|---:|---:|:---:|
| HMIX − CONFORM | 31/23 | 54 | 0.3409 | **0.3409** | 否 |
| HMIX − OFF | 79/22 | 101 | 1.01e-8 | **2.02e-8** | 是 |

分層統計量與「四集不一致對直接相加做一次 McNemar」數值相同（analyzer 的 `pooling_identity_check` 逐位元相等）；
分層買到的是解釋（H0＝每一集都沒有效果、逐集必須照實列、異質性另量），不是更嚴的檢定。異質性（描述性）：
H−C χ² 0.135（df 3，p 0.987）、H−O χ² 0.614（p 0.893），最小期望值 < 5，只當描述。

- **R529 四狀態＝INCONCLUSIVE**。(i) 兩個主指標 Holm 後都成立＝否（H−C 未過）；(ii) 合併 tpc HMIX ≤ CONFORM＝否（5,864.6 > 4,240.9）。
  RULED_OUT 不成立（兩格 b > c）。此狀態與 R460 §六-(4) 的同名狀態**不可互引**（本 run 無 OFF5 臂）。
- **推翻鍵（§六-4）未觸發**：lcb3_hard 5/3、lcb3_medium 6/5，皆 c < b。**lcb3_medium 差一題就觸發**；這是一道很低的門，未觸發≠複製成功。
- **宣稱句（§六-5）＝第三句**：「主指標未成立 ⇒ 逐集照實列，不准寫『多數支持』。」方向雖 4/4 全正，不得寫「四集方向一致且合併顯著」，也不得把四集點估計平均。

## 四、成本

token_per_correct（含 void 版，本 run void＝0 所以與不含 void 相同）：

| 題目集 | OFF | CONFORM | HMIX | HMIX÷CONFORM |
|---|---:|---:|---:|---:|
| LCB v3 medium | 5,262 | 6,001 | 8,128 | 1.35× |
| LCB v3 hard | 11,954 | 17,562 | 17,981 | 1.02× |
| HumanEval+ | 1,941 | 1,964 | 3,301 | 1.68× |
| MBPP+ | 1,969 | 2,778 | 4,437 | 1.60× |
| 合併 | 3,318 | 4,241 | 5,865 | 1.38× |

token／題：OFF 2,591、CONFORM 3,601、HMIX 5,045（合併）。呼叫／題（rows.calls_used）：OFF 1.00、CONFORM 1.30、HMIX 1.12。
**H-MIX 呼叫比 CONFORM 少、token 卻多 1.4 倍**：每通輸出更長。R460 的 tpc 是 HMIX 6,745 < CONFORM 8,195，方向在這四集**反過來**。
⚠ `wire_probe`（38 通、5,094 token）只出現在 HMIX，對 HMIX 成本單邊上偏 0.14%，不改變任何比較方向，引用 tpc 時要指明版本（analyzer 含 probe；rows 的 `harness_tokens_total` 不含）。

## 五、預註冊預測（§四）逐條

| 預測 | 結果 | 依據 |
|---|---|---|
| P-X1 四集 Δ_C > 0 | HIT | +0.74／+3.70／+0.64／+1.08 |
| P-X2 四集 Δ_O > 0 | HIT | +8.15／+9.26／+12.18／+5.93 |
| P-X3 MBPP+ 與 HumanEval+ 的 Δ_C 都小於 LCB v3 兩層最小值（0.74） | **MISS** | HumanEval+ 0.64 <0.74；MBPP+ 1.08 > 0.74 |
| P-X4 假交付 HMIX < CONFORM 四集皆然 | **MISS** | LCB 兩層成立（6<9、7<11）；HumanEval+ 6＝6；MBPP+ 58 > 56 |
| P-X5 token/題 HMIX ≤ 1.2× CONFORM 四集皆然 | **MISS** | 1.37×／1.07×／1.69×／1.62× |
| P-X6 hard 層 Δ_C ≥ medium 層 | HIT | 3.70 ≥ 0.74（但 hard 的 n_discordant 只有 8） |
| P-X7 呼叫/題 HMIX ∈ [1.2, 2.5] 四集皆然 | **MISS** | 1.14／1.24／1.09／1.11 |
| P-X8 每塊 infra_void ≤ 5% | HIT | 全 0 |

四中四錯。錯的四條全在**成本與迴圈形狀**：H-MIX 在這四集幾乎不進迴圈（第一輪就過可見驗收的比例高），呼叫少於預期，
但每通 token 多於預期。這與 §七的解讀一致：可見驗收好過的地方，迴圈沒有用武之地，剩下的只是第一輪 prompt 的差異。

## 六、稽核

### 六-1　V/GT（隱藏測資零洩漏）
`harness_vgt_audit.py --scope v2` 37/37 CLEAN、violations 0、excused 0、needles_checked 181,200（跳過 11,305 個瑣碎 needle，那是量具無鑑別力，不算通過）。
**工具設計上只掃 H 臂（HMIX 844 筆）**。對帳者另寫獨立程序（不呼叫工具的判準函式）掃**三臂全部 2,497 筆**的 system＋user 文字，
needle 直接取自 `hidden_check` 字面值，164,963 個 needle、零命中；正控（把真 needle 接到送出文字後重掃）三塊皆抓到。
負控測試 6 支全綠。⇒ **INVALID 未觸發**（analyzer 自己判不到這一支，見 §六-3）。

### 六-2　三方對帳
七類仲裁欄位（逐集逐臂 deliv 分子分母、逐集與合併 b/c/p/p_adj、token/題、tpc、四狀態）A＝B＝C，p 值逐位元相同。
不一致全在仲裁清單之外：
- `calls_total`（calls.jsonl 行數，含 wire_probe 與失敗重試）與 `calls_per_task`（rows.calls_used）**在 analyzer 同一物件裡不同源**：lcb3m/HMIX 印 162 與 1.1407，但 162÷135＝1.200。要修（§八）。
- 預註冊 §六-6 預算回填只能用一個口徑：實測邏輯呼叫 2,451（A 寫的 2,534 多算了 preflight 37、wire_probe 38、重試 8）。方向不變（低於中心估計 2,850）。

### 六-3　分析器與預註冊的字面不合（口徑對、key 名不對，4 處，未改碼）
§六-3 寫 `tokens.pooled.HMIX.token_per_correct`，實際 `tokens_pooled.HMIX.tpc_incl_void`；§六-1 寫 `primary.per_stratum[k].{b,c,p}`，實際 `primary.<pair>.per_stratum[k].p_unadjusted`；
§六-2 的 `paired.<set>.*`／`tokens.<set>.*`／`per_arm.<set>.*` 全在 `per_set.<set>.` 底下；§六-2 第 5 項指向 §六-5，實為 §六-4。
另：analyzer 只讀 rows/calls/summary，**不讀 V/GT 產物，永遠判不出 INVALID**；INVALID 由本檔 §六-1 補判。
處置＝在預註冊加**勘誤附錄**（不改凍結正文），analyzer 下一版加 `--vgt-dir` 讀稽核產物。

### 六-4　事故
排程器 11:04Z 發射首塊後死於 `UnicodeDecodeError`（發射器 `head -c` 按位元組截中文），其餘四塊未發，1003 空轉約 2 小時；
修復 `e14983b`（發射器 iconv 過濾＋兩支排程器 `errors="replace"`＋4 支回歸測試）後 13:08Z 重發。R460R 排程器 07:23Z 的猝死是同一死法。
首塊 `lcb3m_a1` 在分析器 commit 前已收官（預註冊 §七-1 已記）；可查證的是仲裁欄位與門檻在發射前凍結。

### 六-5　`equal_budget_comparison_valid` 為 false 是 legacy
`gain_run.py:1687-1691` 只認 ON／OFF5 兩臂各 5 通；三臂結構上不可能為 true，不能拿它佐證或反證等預算。本 run 的等預算＝上限 5 通相同、實際呼叫/題 1.00／1.30／1.12。

## 七、解讀（能講的與不能講的）

**能講的**
1. **回饋迴圈對單發的增益跨題庫成立**：三個真來源、四集全正、合併 +7.96 pp、p_adj 2.0e-8。
2. **回饋迴圈對同預算重抽的增益，在這四集上小到量不到**：+0.6 到 +3.7 pp，沒有一集接近顯著，合併 p 0.34。
3. **R460 的 +13.33 pp（LCB v2）沒有在任何一集重現**。三種不互斥的解釋，本 run 分不開：
   (a) 天花板——CONFORM 在這四集已到 76–94%，LCB v2 只有 70.8%；
   (b) 題目性質——LCB v2 是「中高難度、可見測資過了卻隱藏測資不過」的那種題（CONFORM 交錯 29/120＝24%），
       R529 只有 LCB v3 hard 接近（11/54＝20%），而它 n 太小；
   (c) R460 本身是上偏的點估計（預註冊已寫的贏家詛咒）。**R460R 三次同題複製會直接檢驗 (c)**，見下一份稽核。
4. 假交付的降低只在 LCB 出現（9→6、11→7），HumanEval+ 持平、MBPP+ 反升（56→58）——迴圈朝可見測資過擬合的方向在簡單題庫上可見。

**不能講的**
- 不能寫「H-MIX 跨題庫贏過重抽」；也不能反過來寫「H-MIX 對重抽無效」（四集方向全正、檢定力在 n=54–156 下只有 0.14–0.55）。
- 不能把四集點估計平均成一個數；不能把 INCONCLUSIVE 講成「沒有差異」（同號未解析≠沒有差異）。
- 不能用 R529 的四狀態去改 R460 的裁決（推翻鍵未觸發）；但 R460 的宣稱句必須加上範圍限定（§八）。
- R440P 前提句照舊：整件事建立在「需求可被編譯成可執行的驗收測資」。

## 八、後續處置

1. **宣稱口徑**（`examples/verdicts.py`、`build_archive_index.py`、官網 results.html／how.html）：
   `harness.hmix_loop_beats_resample_same_budget` 維持 held 但**限定「LCB v2、單次 run」**；新增
   `harness.hmix_beats_single_shot_cross_bank`（held，四集）與 `harness.hmix_vs_resample_cross_bank_inconclusive`（unresolved，四集 +0.6～+3.7 pp）。
   官網「三次複製，正在跑」段落改成 R460R 結果（下一份稽核之後），並加「跨題庫：贏單發、不贏重抽」段。
2. **修碼（Opus）**：analyzer `calls_total` 改用 rows.calls_used 或明確分兩欄；加 `--vgt-dir` 讀 V/GT 產物以判 INVALID；預註冊勘誤附錄對齊 key 名；`runs/INDEX` 重建（+37 R529、+18 R460R）並更新測試釘值。
3. **下一個實驗**（待 R460R 稽核後決定）：若 R460R 複製到 +13 pp，最值得跑的是「LCB v2 那種題」的更大樣本
   ——同來源、同難度標籤、新日期窗（v3 hard 只有 54 題，不夠）；若 R460R 沒複製到，主張本身要降級為「贏單發」。

## 九、誠實邊界（收官必帶）

1. 四集裡兩集是同來源的難度切片（LCB v3 medium／hard），真來源＝3。
2. LCB v3 的隱藏測資下界只有 5 條、日期窗 ≤2024-08-10（污染風險較高、GT 較弱）。
3. HumanEval+ 156/164：8 題因沙箱信封排除，其中 `HumanEval/15` 是本輪自訂的 2× 餘裕門檻。
4. lcb3_hard 只有 3 題被參考解直接驗過（`gauge_in_filter_n`＝3）；量具是單邊保證。
5. 兩台後端 LM Studio 版本不同（0.4.24／0.4.17）；配對比較在塊內同一台，跨塊絕對值可能混版本差。
6. 首塊在分析器落地前收官；「沒讀 rows」是不可查證的宣稱。
7. 檢定力：n=54–156 的單集對 +10 pp 只有 0.14–0.55；逐集「不顯著」是設計的已知代價，不是證據。

## 十、補記（2026-09-13，Opus 補件後 Fable 核）

- **收據鏈已驗**（`ops/gain/replay/r529/receipts_verify.json`）：37 run、74 條鏈、3,167 筆，逐筆簽章與鏈接全部通過、0 失敗、0 斷鏈。
- **D5 歸因**（`ops/gain/replay/r529/r529_rescore_turn1.json`，零模型呼叫、沙箱重評，不進裁決）：

| 題目集 | 第一稿可見通過 | Δ(第一稿 − OFF) b/c | Δ(最終 − 第一稿) b/c | 迴圈救回題數 |
|---|---:|---|---|---:|
| LCB v3 medium | 88.9% | +0.74 pp（13/12） | +7.41 pp（10/0） | 10 |
| LCB v3 hard | 79.6% | −5.56 pp（2/5） | +14.81 pp（8/0） | 8 |
| HumanEval+ | 94.2% | +7.69 pp（22/10） | +4.49 pp（7/0） | 7 |
| MBPP+ | 94.1% | +4.31 pp（26/10） | +1.62 pp（6/0） | 6 |

  讀法：迴圈確實救回了第一稿沒過的題（四集 31/0，只救不傷——它只改可見驗收沒過的候選），但 CONFORM 的重抽在同樣的題上救回的差不多多；
  所以「迴圈對單發」的增益裡，迴圈這一段是真的，只是重抽也能買到大部分。第一輪 prompt 的效果在四集裡不一致（−5.6 到 +7.7 pp）。
- **analyzer 小修已落地**（`3a2563c`）：`calls_logical_total`／`calls_wire_total` 分欄、`--vgt-dir` 讀稽核產物判 INVALID（本 run 讀入後仍 37/37 CLEAN ⇒ 非 INVALID）；預註冊附錄 B 勘誤對齊 key 名，凍結正文未動。

## 十一、補記 2（2026-09-13 05:50Z，Fable）：兩台後端不是同一個推論條件——1003 是 thinking 模式

發現經過：1004 於 2026-09-13 01:44Z 模型崩潰（`The model has crashed without additional information`）後被 LM Studio JIT 重載，帶上 TTL 1 小時，之後每小時 :07 卸載一次（r5 的 a3／b1／b2／b3 因此各有 1–3 列 infra_void）。05:43Z 以 `lms` 重載為無 TTL 後探針對照兩台：同一「Reply with exactly: OK」請求，1003 回 59 個 completion token（53 個 reasoning），1004 回 2 個（0 reasoning）。回頭掃 R529 的 calls.jsonl：

| 題目集 | 後端 | 呼叫數 | 平均 completion token | 平均 reasoning token | 帶 reasoning 的呼叫 |
|---|---|---:|---:|---:|---:|
| HumanEval+ | 1003 | 333 | 2,370 | 1,885 | 100% |
| HumanEval+ | 1004 | 208 | 494 | 0 | 0% |
| LCB v3 hard | 1003 | 127 | 12,362 | 11,307 | 100% |
| LCB v3 hard | 1004 | 78 | 2,744 | 0 | 0% |
| LCB v3 medium | 1003 | 236 | 7,280 | 6,676 | 100% |
| LCB v3 medium | 1004 | 225 | 1,589 | 0 | 0% |
| MBPP+ | 1003 | 813 | 2,575 | 2,212 | 100% |
| MBPP+ | 1004 | 505 | 582 | 0 | 0% |

R460、R460R r1–r3（全在 1004）：4,758 通呼叫 reasoning 0%。⇒ **1003 的 LM Studio 0.4.24 對 gemma-4 啟用了 thinking（chat template／預設不同），1004 的 0.4.17 沒有。同一顆模型檔，兩種推論條件。**

逐後端的交付率（同一集內，塊隨機落在兩台）：

| 題目集 | 後端 | 單發 | CONFORM | H-MIX | H−C | H−O |
|---|---|---:|---:|---:|---:|---:|
| HumanEval+ | 1003 | 87/100 | 94/100 | 94/100 | 0 | +7 |
| HumanEval+ | 1004 | 42/56 | 53/56 | 54/56 | +1 | +12 |
| LCB v3 hard | 1003 | 25/34 | 26/34 | 28/34 | +2 | +3 |
| LCB v3 hard | 1004 | 13/20 | 15/20 | 15/20 | 0 | +2 |
| LCB v3 medium | 1003 | 69/75 | 74/75 | 74/75 | 0 | +5 |
| LCB v3 medium | 1004 | 46/60 | 51/60 | 52/60 | +1 | +6 |
| MBPP+ | 1003 | 174/231 | 184/231 | 187/231 | +3 | +13 |
| MBPP+ | 1004 | 103/140 | 111/140 | 112/140 | +1 | +9 |

**影響的裁決**
1. 配對主指標（§三）不受影響：每一塊三臂同一台，b/c 是塊內配對；兩台各自的 H−C 都在 0～+3 題、H−O 都為正，與合併結論同向。
2. **§二的逐集絕對值與 §四的 token／tpc 是兩種推論條件的混合物，不可再單獨引用**；thinking 模式讓單發在簡單集上到 87–92%，同時把 token 拉高 4–5 倍。§四「H-MIX token 是 CONFORM 的 1.02–1.68×」要改成逐後端印（Opus 補進 analyzer 的 `per_backend`）。
3. §七解讀裡「天花板」那一條，有一半是 thinking 模式造成的（1003 上 CONFORM 已到 94–99%）。
4. R529 §八-0 事前寫的「逐後端拆開描述」正是為這種情況準備的；它沒預料到差異來自推論模式而不只是版本號。
5. 前一節誠實邊界第 5 條升級為：**兩台後端＝兩種推論條件（thinking／非 thinking），不只是版本不同。**

**處置**
- 之後任何跨機 run 之前，先用同一探針確認 reasoning token 行為一致；要嘛把 1003 對齊為非 thinking（LM Studio 請求層關 reasoning 或降版），要嘛在預註冊裡把推論模式當一個因子。
- gain_run 的 retry ×4 在幾秒內打完，撐不過 8–10 秒的模型重載；改成退避（5／10／20／40 秒）。
- 監看器用 rows.jsonl 數 infra_void 是錯的（作廢列不寫進 rows.jsonl），改讀 summary.json。

## 十二、補記 3（2026-09-13，Opus）：§十一 處置的落地與**沒能落地的那一條**

§十一 的四條處置各自的實作、以及每一條的誠實邊界。**這一節不改任何仲裁值**——
`ops/gain/replay/r529/r529_analyze.json` 重跑之後，除了新增的 `per_backend`／
`per_backend_note` 兩個鍵之外，既有的每一個鍵逐位元不變（`primary`／
`decision_state`／`refutation`／`aggregate`／`per_set`／`tokens_pooled`／`vgt` 全等）。

**1. analyzer 逐後端（已落地）**
`analyze_r529.py` 新增 `per_backend`（描述性）：逐集 × 逐後端印三臂 deliv 分子分母、
b/c（H−C、H−O）、token/題、tpc、reasoning token 平均與帶 reasoning 的呼叫占比、
LM Studio 版本。後端身分只讀落盤 sidecar（`<block>.backend_meta.json` 的
`slot_host`；沒有就用 `<block>.endpoint` 的 IP 兜底；版本再兜底到 §十一 的對照表
1003=0.4.24／1004=0.4.17），**查不到就是 `unknown`，不猜**。
重跑出來的八列與 §十一 的兩張表逐格相同（87/100、42/56、25/34、13/20、69/75、
46/60、174/231、103/140；H−C 0/+1/+2/0/0/+1/+3/+1）。
`analyze_r460r.py` 在 `co_tenancy` 旁新增 `inference_mode`：逐塊 reasoning 占比。
實跑 r1–r3 共 18 塊、4,758 通成功呼叫、**0.0%**、`modes_seen=["non_thinking"]`
——與 §十一「R460／R460R 全在 1004」一致。
兩支的 `--selftest` 各補了案例；`analyze_r529.py --mutation-check` 從 7 個突變加到
9 個（`M8_per_backend_merges_hosts` 把兩台併成一台、`M9_reasoning_ignored` 把
reasoning 一律讀成 0），9/9 全部抓到。

**2. 退避（已落地，但有一個必須講清楚的取捨）**
`brain_cline.DEFAULT_BACKOFF_S` 由 2.0 改為 5.0 ⇒ 退避表 5／10／20／40；
`gain_run.py --retry-backoff-s` 的預設直接指向那個常數。
⚠ **`retries=4`（鐵律 3 的 ×4，本次不動）只會睡前三次＝35 秒**，第四格 40 秒要
`retries=5` 才輪得到。35 秒涵蓋實測的 8–10 秒重載窗，但它不是「保證撐得過任何
重載」，只是把上界從 14 秒抬到 35 秒。
⚠ **`ClineBrain.generate()` 的原始碼被 T12（`tests/test_gain_harness_arms.py::
GENERATE_SHA`）釘死**，所以退避是換**建構子預設值**而不是改那一行；
`generate()` 與 `chat()` 的退避公式本來就是同一條（`backoff_s * 2**(attempt-1)`），
換底數＝同時換兩邊的表，而 `generate()` 的 sha 逐位元不變（已驗）。
**這件事要被看見**：既有五臂的等待時間確實變了（實驗條件），它落盤在
`summary.json.request_policy.backoff_s`。
可重試的判準抽成具名純函式 `is_retryable()`／`has_reload_marker()`：5xx 一律可重試；
400 的 body 帶 `Model unloaded`／`Failed to load model`／`crashed` 視為重載窗；
401/402/403 維持不重試，**除非** body 帶重載字樣（代理層改了狀態碼不改變事實）。
`chat()` 逐次落盤 `retryable`／`reload_window`／`backoff_s`。
測試：假後端前 3 次回 400 `Model unloaded`、第 4 次成功 ⇒ `generate()` 與 `chat()`
**都不得** infra_void，且等待序列恰為 5／10／20。

**3. `reasoning_effort`（部分落地——這是本節最重要的一條）**
2026-09-13 Fable 實測：兩台都吃 OpenAI 相容的頂層 `"reasoning_effort":"none"`，
1003 加上之後與 1004 完全一致（prompt 18 token、completion 2、reasoning 0）；
其他寫法（`reasoning.effort`、`chat_template_kwargs.enable_thinking`、`thinking.type`）
在 1003 都無效。
已落地：`ClineBrain.chat()` 送這個欄位、`gain_run.py --reasoning-effort
{none,default,low,medium,high}`（**預設 none**；`default`＝不送這個欄位＝舊行為）、
值落盤在 `summary.json.request_policy.reasoning_effort`、每一列 `rows.jsonl`、
以及發射器寫的 `<run>.backend_meta.json`。
⚠ **`generate()` 送不出去**（T12 釘死）⇒ **OFF／OFF5／CONFORM／EQ5／ON 五臂在
1003 上仍然是 thinking 模式**。`--reasoning-effort` 目前只作用在 H 臂（`chat()`）。
`request_policy.reasoning_effort_applies_to` 逐字寫著這件事，
`tests/test_backend_inference_mode.py::test_generate_is_pinned_so_it_cannot_send_the_flag`
把這個缺口釘在明面上（哪天 T12 被解除或 `generate()` 被改寫，它會紅）。
⇒ **跨機比較之前必須先裁決：要嘛授權改 `generate()`＋更新 T12 的 sha（像 round460e
那次牆鐘護欄的先例），要嘛在預註冊裡把推論模式當一個因子。這是人類／Fable 的決定，
不是 runner 的。**
runner 的預檢（走 `generate()`）現在會把探針那一通的 `reasoning_tokens` 印在
launch.log 上，>0 就印一行 WARN 說明「這條路仍是 thinking」——**不擋**。

**4. 發射器探針（已落地，只記錄不擋）**
`launch_r529_block.sh` 與 `launch_harness_rep_block.sh` 的三次探針都送
`reasoning_effort`（預設 none），把 `usage.completion_tokens_details.reasoning_tokens`
與 `completion_tokens` 印進 launch.log，並寫進 `<run>.backend_meta.json` 的
`reasoning_effort`／`probe_reasoning_tokens`／`probe_reasoning_ok`／
`lmstudio_version_probed`（後者試 `/api/v0/models`，問不到記 `null` 不猜）。
`≠0` 只印 WARN，**通過判準一個字沒改**（HTTP 200 ＋ content 非空 ＋ 三次全過）。
⚠ `probe_reasoning_tokens` 是**探針那一通**量到的，不保證整塊都在同一個推論模式
（模型中途被重載就可能變）；「沒回報 reasoning」寫成 `null` 而**不是** 0。
`launch_harness_rep_block.sh` 以前完全沒有寫 `backend_meta.json`（只有 `.endpoint`
與 `.backend.json`）⇒ R460R 那 30 塊事後只查得到 IP。本次補上，形狀與 R529 那一支相同。

**5. 排程器的 infra_void 計數（查核結果：本來就是對的，補上防止回歸的牙齒）**
`schedule_harness_reps.py` 與 `schedule_queue.py` 的完成判定**從來沒有**數過
`rows.jsonl` 的行數——兩支都走 `classify_summary()`，讀的是 `run_terminal` 與
`arms.<arm>.{processed, infra_void}`（`processed` 含 void）。§十一 那一條講的
「監看器」若指的是人在終端機下的 `wc -l`，那不在 repo 裡。
本次做的是把規則**寫進 docstring**（「作廢列不寫進 `rows.jsonl`」⇒
`len(rows) ＝ processed − infra_void`，用行數當進度會讓有 void 的塊永遠到不了
「跑完」、用行數當分母會把 void 率系統性算小），並加一條測試禁止那兩支出現
`"rows.jsonl"` 這個字串字面值。

**沒有做的（刻意）**：沒有碰 `harness_arms.py`、沒有碰遠端、沒有動 `retries=4`、
沒有重跑任何 run、沒有改 `r460r_analyze.json`（那一份是在 vacant-dev 帶
`--rescore-turn1` 產的，本機沙箱重跑會把 D5 那幾格變成 `null`＝資料倒退）。
