# R459：`runs/g_r447_conform_lcb2` 收官裁決（Fable 5.1 稽核輪，round726）

（2026-09-04 UTC 17:29–17:5x。裁決輪：**不改任何實驗程式碼、不改任何判準、不動任何普查記錄**。
所有數字取自 terminal 資料：`rows.jsonl` **360 行、sha256 前 16 碼 `cfed36ff71b871f0`**；
三臂 `complete=true, terminal=true, infra_void=0, processed=120`。
仲裁者（round725 交棒）：R440Z §三／§四／§六 ＋ R450 §四／§六 ＋ R451 ＋ R452（含 §九）
＋ R453 ＋ R454 ＋ R455 ＋ R456 ＋ R458 ＋ R447_FABLE_AUDIT §四／§五 ＋ R670 §三（四格表）。
判準文件 `DECISION_20260904_R440Z_LCB2_PREREG.md` sha256 `7150d9db…` 與發射時相同
（`r447_schema_precheck decision_sha256_ok=true`）。）

## 〇、先驗尺再信數字（本輪實跑）

```
r447_mutation_check.py     baseline 5 支 SELFTEST PASS；MUTATION PASS，
                           M1–M11／X1–X14／Y1–Y15 全部 caught=Y（指名捕獲，非 crash）
r447_schema_precheck       SCHEMA_COMPATIBLE  decision_sha256_ok true
                           pz5b_reconstruction_feasible_ok_only true（R457 新旗）
calls_audit                ACCOUNTING_CONSISTENT  pairs 360/360  identity_holds true
                           calls_used 925／logged 931／retry 6  failed 6（全部有原因字串）
receipt_chain_audit        --selftest PASS（1 clean + 5 mutants）
r447_gauge_capability      verdict OK  deliv_contract_drift null
```

## 一、R440Z §三 八條預測逐條對帳

| # | 預測 | terminal 實測 | 判 | 普查類別（R453/R458） | 帶不帶資訊 |
|---|---|---|---|---|---|
| P-Z1 | OFF 失敗率 40–60% | **49.17%**（59/120） | **HIT** | UNRESOLVED（留一法 1/n 擾動搆不到邊界；離邊界／擾動 ≫1） | 帶（自由統計量）；**但書見 §三** |
| P-Z2 | b≫c、p<0.01、Δ +12~+25pp | **b=31 c=8 Δ=+19.17pp CI[+8.80,+26.46] p=0.000294** | **HIT**（兩半都中） | P-Z2a/b UNRESOLVED（同上，留一法解析度）；`overturn_c_ge_b_half` EVALUABLE（witness 8） | 帶；MDE@n=12.5pp，實測 19.17 > MDE |
| P-Z3 | vs OFF5 +2~+8pp，p 很可能 >0.05 | **Δ=+6.67pp CI[−2.13,+13.75] p=0.152**（b=16 c=8） | **HIT**（窗＋p 方向都中） | UNRESOLVED（留一範圍 5.88–7.56 全在窗內） | 帶；**非等預算**（1.71 vs 5.00 通） |
| P-Z4 | `calls_per_task` 1.5–2.2 | **1.708**（205/120） | **HIT** | UNRESOLVED | 帶 |
| P-Z5a | 拒交率 5–12% | **5.83%**（7/120） | **HIT** | UNRESOLVED | 帶 |
| P-Z5b | 拒交題「五份全錯」≥80% | rows 上 UNEVALUABLE；恆等式下恆 100% | **HIT-by-construction** | **FORCED_GREEN** | **不帶**（R453 §四：拒交⇒全 ¬V⇒全 ¬H） |
| P-Z6 | 無 `visible_ok=False ∧ meets_demand=True` 列 | 0 違例（`md&!acc` 三臂皆 0） | **HIT-by-construction** | **FORCED_GREEN**（lcb2 120/120 visible⊆hidden，`forced_zero=True`） | **不帶**（R452 §九） |
| P-Z7 | 任一臂 void<20%、CONFORM<5% | 三臂 void **0.0%** | **HIT** | EVALUABLE（跨 39 個 run 有 30 個 witness） | 帶 |
| P-Z8 | 每列有 `receipt_head`、`receipts_CONFORM.ndjson` 落盤、`verify_chain` 為真 | CONFORM 120/120 有 `receipt_head`；OFF/OFF5 240 列無此鍵；鏈檔在、**`verify_chain=true`**（325 entries、205 attempt hash 唯一、120 head 唯一） | **範圍裁決見 §二；裁定 HIT（限 CONFORM）** | `@CONFORM` FORCED_GREEN（無條件字面鍵）；`@ALL_ROWS` EVALUABLE（照字面已為假） | `verify_chain` 那一半帶資訊，`receipt_head` 那一半不帶 |

**R440Z §四 中止準則**：void 0 ⇒ 未觸發；OFF 失敗率 49.2% < 70% ⇒ 未觸發；P-Z6 未被推翻（結構上也不可能）。
**R440Z §六 推翻條件**：P-Z2 的 `p ≥ 0.05 或 c ≥ b/2`：p=0.0003、c=8 < 15.5 ⇒ **未觸發**
⇒ E3 的 +20.88pp（離線重放，b=19 c=0）**不是重放假象**：真跑循序抽樣拿到 +19.17pp（b=31 c=8），
R440P §三「題目越難早停越值錢」**不必收回**。真跑的 c=8 而重放是 0，那是重放與真跑抽樣不同的正常差異，不是異常。

### 本階「足夠有效」（R440Z §三：P-Z2 ∧ P-Z6）——裁決：**STAGE_EFFECTIVE 成立，但只由 P-Z2 承重**

P-Z6 在 lcb2 上是構造恆真（visible⊆hidden 120/120），**不是證據**。採納 R452 §九 的提案 P-R452-1：
P-Z6 一律寫成「**在本題庫上不可證偽、由構造成立**」。這對「拒交規則不會丟掉隱藏正確的候選」這件事
反而是**比經驗證據更強的保證**（除非候選程式非決定性／逾時，R670 §六），
但它對 CONFORM 是否有效**零貢獻**。合取項的資訊量全部來自 P-Z2。

## 二、P-Z8 的範圍歧義——裁決

R440Z 原文「每列有 `receipt_head`」照字面涵蓋三臂，而 OFF／OFF5 的 240 列從來沒有這個鍵。
裁決：**P-Z8 的範圍限 CONFORM。** 根據（是判斷，不是量測）：預註冊時 `save_receipts` 的 docstring
已寫「空鏈的臂不寫檔（OFF／OFF5／ON 都不用這條路徑）」，且 P-Z8 的來源是 R440R P-C4／R666
「**該臂的鏈** verify_chain 為真」——它從來就是 CONFORM 的收據鏈判準，「每列」是措辭疏漏。
**照字面讀是 MISS，這一行要留著**；往後預註冊寫「每列」要寫清楚是哪一臂的列。
帶資訊的那一半（`verify_chain=true`，P-R666-1 由 UNVERIFIABLE 翻成 YES）成立。

## 三、R450 §四／§六——P-Z1 必須加但書

```
n_complete 120  n_demonstrated 94  n_undemonstrated 26（21.667%）
pz1_raw 49.167   pz1_demonstrated_only 35.106   ⇒ 區間 [35.1, 49.2]
window_doubt_triggered false（21.7% ≤ 50%）
```

區間下端 35.1 **跨出** 40–60 ⇒ 照 R450 §四 原文，收官**必須**寫：
**P-Z1 的 HIT 依賴 108 題未經參考解驗證的量具；若 26 題 undemonstrated 全是量具假象，
OFF 失敗率會是 35.1%（窗外）。** 這不改 P-Z1 的 HIT，只加但書。
undemonstrated 21.7% ≤ 50% ⇒ 「LCB v2 是可用量測窗口」**不被質疑**（§六-1 未觸發）。
§三「覆蓋率不足翻不動配對比較」引用的是 **R454 §四 的證明**（undemonstrated 題對 b/c 各貢獻 0），
**不是**「真資料對照逐數相同」——後者已由 R454 證明是不可達的空綠燈（FORCED_GREEN, intent=evidence）。

## 四、R451／R458——CONFORM vs OFF5 的解析度

```
power_conform_vs_off5   mde_at_n 10.0pp（n_disc 24）   n_needed_for_5pp 332
power_conform_vs_off    mde_at_n 12.5pp（n_disc 39）   n_needed_for_5pp 532
lcb2 題庫 120 題
```

R451 §五3 **已觸發**（332 > 120）：**CONFORM vs OFF5 在 LCB2 上不可能有 5pp 解析度，這是結論不是失敗。**
兩件證物（R440Z 的 P-Z3 三行、R670 的 UNINFORMATIVE 一行）自 R451 起逐字未動（R458 驗過）。
四格判定（R670 §三，`deliv` 差值區間 CONFORM−OFF5 = [−2.13, +13.75]pp）：
lo > −5 且 hi > +5 ⇒ **`NON_INFERIOR_BUT_UNRESOLVED`**。
依 R670 只准寫：「**沒測出劣化，也沒測出 ≥5pp 的增益**」。⛔ 不准寫「打贏」也不准寫「打不贏」。
（期中曾是 UNINFORMATIVE；terminal 區間縮到 lo=−2.13，升到這一格。不是等預算，見 §五。）

CONFORM vs OFF：區間 [+8.80, +26.46]，lo > 0 ⇒ **`CONFORM_WINS`**（工具印 `ON_WINS`，同一格、兩套詞彙）。

## 五、R452——等預算（閘門 vs 多數決）在難題庫上的離線重建（terminal 重算，可引用的那一份）

```
verdict RECONSTRUCTED   calibration 54/54 = 100%（≥20）
gate 81/120 = 67.5%   vote 76/120 = 63.3%   gate 拒交 11/120 = 9.17%
paired gate−vote  b=14 c=9  Δ=+4.17pp  CI[−4.39, +11.61]  p=0.405
power  mde_at_n 9.17pp   n_needed_for_5pp 320
oracle_any_candidate_correct 94/120 = 78.3%（探索性）
```

W1–W4 **4/4 HIT**（校準 100%、拒交 9.17% ∈ 2–14、Δ ∈ 0..+12 且 p>0.05、MDE/N₈₀ 落地）。
四格（R670）：lo=−4.39 > −5、hi=11.61 > 5 ⇒ **`NON_INFERIOR_BUT_UNRESOLVED`**。
對照 r446 MBPP+ EQ5：+4.04pp CI[+0.80,+6.53] p=0.0135（n=371）。
**點估計同號同量級（+4.04 vs +4.17），但 n=120 的 MDE 是 9.17pp ⇒ r446 的外推在難題庫上
既沒有被反證（R452 §六-2 的 Δ<−5 未觸發）、也沒有被獨立確認。** 要確認需 ≈320 配對題。
R452 §七-2 序貫揭露照抄：這個估計量是看過期中數字後才提出的；本段是 terminal 重算。

## 六、鐵律三條

1. **OFF5 分水嶺（等預算）**：在 LCB2 上，等預算的答案是 §五 那一格——UNRESOLVED
   家族的 `NON_INFERIOR_BUT_UNRESOLVED`，且題庫規模（120）使它**在本題庫上不可能升格**
   （需 320–332 題）。唯一解析出的等預算答案仍是 r446（MBPP+）。
   P-Z3 那一格（CONFORM 1.71 通 vs OFF5 5.00 通）**不是等預算**，不准拿來答鐵律 1。
2. **infra_void**：三臂 0／120，分母全部 processed=120。6 通失敗全部重試成功、原因逐字落盤。
3. **評審準確率**：**不適用**——CONFORM 是執行閘門、沒有評審（`reviewer_accuracy=null`、
   `reviewer_votes=0`）。本 run 沒有任何結論依賴評審。

## 七、R447_FABLE_AUDIT §四 五條具名（terminal 版）與 §五 推翻條件

| 臂 | 失敗通 | 原因（逐字節錄） | 死時間 | 佔該臂牆鐘 |
|---|---|---|---|---|
| OFF | 1 | lcb_3794 `HTTP 500 Internal Server Error`（10 ms） | 0.0 s | 0% |
| CONFORM | 3 | lcb_3762 `TimeoutError`(600 s)；lcb_3584 `HTTP 400 Context size has been exceeded`(341 s) → 重試 `TimeoutError`(600 s) → 第三次成功 | 1541.3 s | 13.2%（/11653.8 s） |
| OFF5 | 2 | lcb_3776 `TimeoutError`(600 s)；lcb_3779 `HTTP 400 Context size has been exceeded`(293 s) | 892.6 s | 3.9%（/22726.3 s） |

- 重試＝重抽：OFF5 2/600 候選（0.33%）、CONFORM 2/120 題（3 通）是第二或第三次抽樣。
  lcb_3762／lcb_3584／lcb_3776 三題都在 undemonstrated 名單裡（三臂全錯）⇒ 這三題的重抽沒有改變任何交付格；
  lcb_3779（OFF5 一通 400 後重抽）不在名單裡，重抽那一份候選有沒有影響 OFF5 該格，rows 上分不出來（1/600 候選，量級太小不修正、照實寫）。
- 結論只在 600 s × 4 次重試的研究 deadline 下成立；短 deadline 下這 6 通會變 void（**不可移植到產品設定**）。
- §五 推翻條件逐條：OFF5 失敗 2 < 15 ✗；`infra_void` 全 0 ✗；沒有任一題在兩臂都失敗 ✗；
  Q1 端點 STABLE（round725 pace_probe，tok/s 中位 72.44）✗ ⇒ **該裁決不升級**。
- CTX400（R447_CTX400 §九）：三通 400 屬「短群」無解釋；對 P-Z1..P-Z8 無影響（皆重試成功）。

## 八、成本（每正確交付的呼叫數；獨立結算，不受四格判定影響）

| 臂 | 呼叫 | 交付對 | 每題呼叫 | 每正確交付呼叫 |
|---|---|---|---|---|
| OFF | 120 | 61 | 1.00 | 1.97 |
| CONFORM | 205 | 84 | 1.71 | **2.44** |
| OFF5 | 600 | 76 | 5.00 | 7.89 |

CONFORM 用 OFF5 **34% 的呼叫**交付了**比 OFF5 多 8 題**（84 vs 76；配對 b=16 c=8）。
依 R670 措辭：**CONFORM 在難題庫上買到的是成本，準確率面對 OFF5 只能寫「沒測出劣化」。**

## 九、事後（非預註冊）的一個觀察，標明是探索性

OFF5 vs OFF 在 LCB2：**b=22 c=7 Δ=+12.5pp CI[+3.12,+19.19] p=0.0081**。
在 MBPP+（r445，n=371）同一比較是 +0.81pp CI[−2.78,+4.28]＝`RULED_OUT`。
⇒ 「5 倍預算沒買到準確率」是**題庫相依**的：難題庫上 self-consistency 有買到。
這**不在** R440Z 的預測清單裡、是看過數字才寫的，不當結論用，只當下一份預註冊的假說來源。

## 十、「有成效」三條（LOOP_PROMPT 事前定義）在 LCB2 上

1. 量測有訊號：OFF 失敗 49.2% ∈ 20–60 ✓（附 §三 但書）。
2. 三臂有差異：CONFORM vs OFF p=0.0003、OFF5 vs OFF p=0.008 ✓。
3. 等預算答案：**本題庫答不出來，而且已量出答不出來的原因是題庫規模**（需 320–332 題，只有 120）。
   這是「沒量出來」不是「沒有差異」。

## 十一、誠實邊界（收官不准漏）

1. 12/120 有參考解；P-Z1 的但書（§三）。
2. lcb2 與 E3 的 91 題共用，**不是獨立複製**；lcb_3026 早於污染定界（R440Z §五-3）。
3. lcb_3763／lcb_3613（KNOWN_BAD）都在 undemonstrated 名單（三臂全滅）⇒ 照 R440Z §五-4 先怪量具：
   它們最多讓 OFF 失敗率多算 2/120=1.67pp，落在 §三 的區間內，不改任何判決。
4. 普查 UNRESOLVED 那 9 條（P-Z1/2a/2b/3/4/5a、P-Z3_pvalue、R450-§六-1、R450-§五-2）的意思是
   「留一法搆不到窗邊」，**不是**「不可證偽」；它們的 HIT 仍是自由統計量的命中。
5. 本輪讀了全部 `TRIPWIRE_FORBIDDEN` 鍵；合法性＝run terminal ＋ 本輪是指定的裁決輪。
6. 沒有被普查過的仲裁者：R453／R454／R455／R456／R458 自己（round725 誠實邊界 4 原樣留著）；
   R454 的校準仍是單向（只有正對照）。這些不影響本裁決引用的任何 EVALUABLE 條目。
7. 本裁決**沒有**改任何條文、門檻、窗口、記錄檔；`r45x_census*.json` 一個位元組沒動。

## 十二、下一個問題（提案，給 opus 輪拍板；本輪不動手）

等預算比較在 LCB2 上的天花板是題庫規模。三條路，建議第一條：
- **P-R459-1** 造更大的難題庫（≥330 題、OFF 失敗率 40–60%），要先過 `check_bank_precision`／
  污染定界／`--arms probe`，並在發射前預註冊「等預算 EQ5 臂（線上）＋離線重建」兩份答案的一致性。
- P-R459-2 把 §九 的「OFF5−OFF 題庫相依」寫成預註冊假說，在新題庫上一起答。
- P-R459-3 不再加 n，把資源轉去 CTX400 短群的機制（與實驗結論無關的 infra 問題）。
推翻本提案的條件：若找不到 ≥330 題且通過污染定界的難題來源，第一條作廢，改走 P-R459-3。
