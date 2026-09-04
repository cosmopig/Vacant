=== LINE 0 ===
```
POOLABLE　C1_disjoint=HIT　C3_config=HIT　C4_void=HIT　C2_code=UNVERIFIABLE_NO_CODE_VERSION
  題目：179+192 = 371 題，兩兩不相交
  處置：mbppplus　seed=g-r212-route-20260828　6 agent／1 模型
  void：spread 0.0pp（門檻 5.0pp，取自判準檔）
  ⚠ 碼版本：UNVERIFIABLE_NO_CODE_VERSION，由 runs/_analysis_r680/CODE_ATTEST.md 背書
```
rc=0

=== LINE 1 ===
```
{
  "key": "deliv",
  "strata": [
    {
      "label": "r444",
      "group": null,
      "dir": "runs/g_r444_conform_mbpp",
      "n": 179,
      "b": 9,
      "c": 4,
      "a_ok": 135,
      "b_ok": 130,
      "key": "deliv",
      "third_category_missing_fields": [],
      "delta_pp": 2.793296089385475,
      "ci95_lo_pp": -1.6596665952616365,
      "ci95_hi_pp": 5.941938402863404,
      "n_discordant": 13,
      "conditions_sha": {
        "pool": "08e36c8e6171cffb",
        "instrument": "c5a917995e70fa21",
        "calibration": "74234e98afe7498f",
        "request_policy": "b009f7f91286d44a"
      },
      "instrument_two_way": {
        "ok": true,
        "n": 179,
        "ref_pass": 179,
        "broken_rejected": 179,
        "why": ""
      },
      "rows_sha256_16": "3f2cb9661f7a080b",
      "rows_lines": 537
    },
    {
      "label": "r445",
      "group": null,
      "dir": "runs/g_r445_conform_mbpp_ext",
      "n": 192,
      "b": 18,
      "c": 9,
      "a_ok": 146,
      "b_ok": 137,
      "key": "deliv",
      "third_category_missing_fields": [],
      "delta_pp": 4.6875,
      "ci95_lo_pp": -1.113954921344764,
      "ci95_hi_pp": 9.41658244629425,
      "n_discordant": 27,
      "conditions_sha": {
        "pool": "08e36c8e6171cffb",
        "instrument": "a58c0330642602f8",
        "calibration": "74234e98afe7498f",
        "request_policy": "b009f7f91286d44a"
      },
      "instrument_two_way": {
        "ok": true,
        "n": 192,
        "ref_pass": 192,
        "broken_rejected": 192,
        "why": ""
      },
      "rows_sha256_16": "14fa9f83bd0643c5",
      "rows_lines": 576
    }
  ],
  "p_het_fisher": 1.0,
  "het_alpha": 0.05,
  "het_verdict": "HOMOGENEOUS_NOT_REJECTED",
  "pooled": {
    "B": 27,
    "C": 13,
    "N": 371,
    "n_discordant": 40,
    "delta_pp": 3.7735849056603774,
    "ci95_lo_pp": 0.18771157997964721,
    "ci95_hi_pp": 6.776733870332081,
    "pi_ci95": [
      0.5087051245215561,
      0.8142710332366503
    ]
  },
  "verdict_pooled": "ON_WINS",
  "pooled_usable_as_headline": true,
  "groups": {
    "r444": {
      "b": 9,
      "c": 4,
      "n": 179,
      "labels": [
        "r444"
      ]
    },
    "r445": {
      "b": 18,
      "c": 9,
      "n": 192,
      "labels": [
        "r445"
      ]
    }
  },
  "opposite_direction_strata": false,
  "practical_pp": 5.0,
  "supplement_n_needed_for_halfwidth_5pp": 371,
  "broken_reasons": []
}
```
rc=0

=== LINE 2 ===
```
=== runs/g_r445_conform_mbpp_ext  rows=576 sha8=14fa9f83 terminal=True ===
門檻來源：DECISION_20260903_R445_CONFORM_BANK_EXTENSION.md（每個數字都從該列的 quote parse，工具裡沒有門檻）
  P-E1  HIT              值=   4.6875  帶=[0.0, 6.0]     quote='[0, +6]pp'
  P-E2  MISS             值=   3.2945  帶=≤ 3.0          quote='半寬 ≤ 3.0pp'
  P-E3  HIT              值=  40.0000  帶=[20.0, 40.0]   quote='[20, 40]'
  P-E4  HIT              值=   1.5104  帶=[1.2, 1.6]     quote='[1.2, 1.6]'
          中止線 > 4.5 ⇒ triggered=False
  P-E5  HIT              值=   8.3333  帶=[3.0, 10.0]    quote='[3, 10]%'
  P-E6  HIT              值=   0.0000  帶=< 5.0          quote='<5%'
          中止線 > 20.0 ⇒ triggered=False
  P-E7  HIT              值= 192.0000  帶=== 192/192     quote='192/192'
  P-E8  HIT              值=  29.6875  帶=20.0–60.0      quote='20–60%'
  合計 HIT=7 MISS=1 ABORT=0 NOT_EVALUATED=0 BROKEN=0
  conform_settle 這些鍵對 r445 不適用（r444 口徑）：
    P-C1_band_3_to_6pp: r444 的帶是 [3,6]pp；r445 註冊的 P-E1 是 [0,+6]pp
    P-C1b_band_0.02_to_0.20: r444 的 p 值帶；r445 沒有註冊 p 值的帶
    P-C2_le_2.0: r444 的門檻是 ≤2.0；r445 註冊的 P-E4 是 [1.2,1.6]（≤2.0 會給假綠燈）
    P-C1_settlement_rule: 文字寫死 n=179；r445 是 192（併庫 371），照抄會寫出字面錯誤的句子
```
rc=0

=== LINE 3 ===
```
=== runs/g_r445_conform_mbpp_ext  rows=576 sha8=14fa9f83 terminal=True ===
arm          n  acc  refus   deliv%   meets%     d=o%  leak  md&!acc  c/task
OFF5       192  192      0   71.35   71.35    71.35    55        0    5.00
CONFORM    192  176     16   76.04   76.04    82.95    30        0    1.51
OFF        192  192      0   70.31   70.31    70.31    57        0    1.00
paired[deliv       ] n=192 Δ= +4.69pp b=18  c=9   p=0.1221  95%CI=[-1.11,+9.42]pp NON_INFERIOR_BUT_UNRESOLVED  <= P-C1 用這個
paired[meets_demand] n=192 Δ= +4.69pp b=18  c=9   p=0.1221  95%CI=[-1.11,+9.42]pp NON_INFERIOR_BUT_UNRESOLVED  （analyze_paired 報的是這個）
calls 檢查層級：{'OFF5': 'exact', 'CONFORM': 'exact', 'OFF': 'exact'}  （exact＝逐位相同；bounded＝該臂有 void，改用碼蘊含的上下界）
{
  "P-C1_delta_pp": 4.6875,
  "P-C1_band_3_to_6pp": true,
  "P-C1_ci_pp": [
    -1.113954921344764,
    9.41658244629425
  ],
  "P-C1_ci_verdict": "NON_INFERIOR_BUT_UNRESOLVED",
  "P-C1_settlement_rule": "只能寫「沒測出劣化，也沒測出 ≥5pp 的增益」；不准寫成「打贏」或「打不贏」",
  "P-C1b_p": 0.12207812070846558,
  "P-C1b_band_0.02_to_0.20": true,
  "P-C2_calls_per_task": 1.5104166666666667,
  "P-C2_le_2.0": true,
  "P-C2_abort_gt_4.5": false,
  "P-C3a_refusal_rate": 0.08333333333333333,
  "P-C3a_band_3_to_10pct": true,
  "P-C3b_leaked": {
    "OFF5": 55,
    "CONFORM": 30,
    "OFF": 57
  },
  "P-C3b_verdict": "REPORTED_ONLY（R440R 未給門檻，判準 §三 降級）",
  "P-C4": "前半只看 receipt_head 齊備（round666）；鏈為 UNVERIFIABLE，不是中止條件",
  "P-C5_void_ratio": {
    "OFF5": 0.0,
    "CONFORM": 0.0,
    "OFF": 0.0
  },
  "P-C5_any_abort": false
}
```
rc=0

=== LINE 4 ===
```
配對數（目前）n = 192
discordant 到達序列（27 個）：cbbbbbcbbbbbcbbbbbccbccbcbc
  b（只有 CONFORM 對）=18   c（只有 OFF5 對）=9
  全序列 McNemar 精確雙尾 p = 0.1221

  最近 5 個 = cbcbc  同向最多 3/5  單尾 p = 0.5000
  最近 8 個 = cbccbcbc  同向最多 5/8  單尾 p = 0.3633
觸發的推翻條件：無  ⇒ 判定：noise

discordant rate = 14.06%
n=371 時預期 discordant≈52，要 p<0.05 最少要 34:18 （|b-c|≥16）⇒ MDE = 4.31 pp
若真實效果＝觀測值（p_b=0.667），80% power 需要 69 個 discordant pair ⇒ 約 491 個配對任務
題庫只有 378 題 ⇒ 可達？ False
```
rc=0

---

# round688 裁決（依 CRITERION_20260904_R687_R445_SETTLEMENT.md，規則零自由度）

## 前置閘門

```
G1  rows.jsonl = 576 行，OFF/CONFORM/OFF5 = 192/192/192   ✓
G2  summary.json run_complete=True  run_terminal=True      ✓
G3  ps -eo cmd | grep -c "^python3 ops/gain/gain_run\.py" = 0（行程 01:22:22 UTC 退出）✓
rows.jsonl sha256 前 8 碼 = 14fa9f83
```
三閘門全過 ⇒ 收官。第一件事已做：`git add` r445 run 目錄並 commit（fc32fa6）。

## P-R687-1..8（收官路徑走不走得通）

| # | 判準 | 實際看到的量 | 判定 |
|---|---|---|---|
| P-R687-1 | 五行 rc | 0, 0, 0, 0, 0 | **HIT** |
| P-R687-2 | 第 2 行 NOT_EVALUATED / BROKEN | `NOT_EVALUATED=0 BROKEN=0` | **HIT** |
| P-R687-3 | 第 0 行四個 C | `POOLABLE C1=HIT C3=HIT C4=HIT C2=UNVERIFIABLE_NO_CODE_VERSION`；void spread 0.0pp（新分母 processed） | **HIT** |
| P-R687-4 | 第 3 行 terminal exact 覆算 | `{'OFF5':'exact','CONFORM':'exact','OFF':'exact'}` | **HIT** |
| P-R687-5 | 產物 key 欄位 | `pooled_deliv.json` 的 `"key": "deliv"`（讀產物，不是看指令） | **HIT** |
| P-R687-6 | disc_rate ∈ [0.036, 0.145] | **0.1406**（27/192） | **HIT，但距上緣只剩 0.39pp** |
| P-R687-7 | 三臂 infra_void | OFF 0 / CONFORM 0 / OFF5 0 | **HIT** |
| P-R687-8 | CONFORM c/t 顯著低於 5.00 | **1.5104**（OFF5 = 5.00，OFF = 1.00） | **HIT** |

**8 HIT / 0 MISS。**round682 只在合成 fixture 上證明過的收官路徑，在真目錄上第一次
通電即全綠。P-R687-6 擦邊過關，照實記在這裡：它只要再多 1 個 discordant 對
（28/192 = 0.1458）就會超出上緣、令 round678 的投影作廢。

## P-E1..P-E8（DECISION_20260903_R445 事前註冊，工具逐條判）

`7 HIT / 1 MISS / ABORT=0 / NOT_EVALUATED=0 / BROKEN=0`

唯一的 MISS 是 **P-E2**：併 371 題後 95%CI 半寬 **3.2945pp**，事前預測 ≤3.0pp
（機械外推 3.80×√(179/371)=2.64）。外推假設 discordant 密度與 r444 相同，實際
r445 的 disc_rate（14.06%）高於 r444（7.26%），區間因此比外推寬。**照實記為 MISS，
不追認。**

## P-R687-E：三份區間全報（round682 §六）

| 資料 | n | Δdeliv (CONFORM−OFF5) | b / c | n_d | 95% CI | 四格判定（R670 §三 逐列比對） |
|---|---|---|---|---|---|---|
| **r445 新 192 題（乾淨複製）** | 192 | **+4.69pp** | 18 / 9 | 27 | **[−1.11, +9.42]pp** | `lo>0`✗；`hi≤5`✗；`lo<−5`✗ ⇒ **NON_INFERIOR_BUT_UNRESOLVED** |
| r444 原始 179 題（已凍結） | 179 | +2.79pp | 9 / 4 | 13 | [−1.66, +5.94]pp | **NON_INFERIOR_BUT_UNRESOLVED** |
| **併庫 371 題（最佳精度）** | 371 | **+3.77pp** | 27 / 13 | 40 | **[+0.19, +6.78]pp** | `lo = +0.188 > 0` ⇒ **CONFORM_WINS** |

異質性：`p_het_fisher = 1.0`，`HOMOGENEOUS_NOT_REJECTED`，`opposite_direction_strata = false`，
`pooled_usable_as_headline = true`。兩層 rows sha16：r444 `3f2cb9661f7a080b`(537 行)、
r445 `14fa9f83bd0643c5`(576 行)。

**併庫那一列的強制附註（DECISION §「主結論用哪一份資料」事前寫死）**：
擴充的決定是在看過 r444 之後做的＝**序貫加樣本，名目 p 偏樂觀**，不准當成乾淨的檢定。
乾淨的那一份是新 192 題，而它單獨算是 **UNRESOLVED**。兩份都在上表，沒有挑。

## 四格 × 成本不對稱（R684 §二 事前寫死，逐格照抄）

- 併庫 371 題落 `CONFORM_WINS` ⇒ 准寫「**用約 1/3 的呼叫打贏 OFF5**」
  （c/t 1.51 vs 5.00；每正確交付呼叫數 1.99 vs 7.01 = **3.53 倍**）；
  **不准**寫「等預算下打贏」。
- 新 192 題落 `NON_INFERIOR_BUT_UNRESOLVED` ⇒ 只能寫「沒測出劣化，也沒測出
  ≥5pp 的增益，而 CONFORM 只花約 1/3 呼叫」；**不准**寫「打贏」或「打不贏」。
- **四格全部都要附的那一句**：**本比較不是等預算；等預算版本（CONFORM 也花
  5 次呼叫）沒有跑過。**LOOP_PROMPT 鐵律 1 的字面問題，r445 的設計答不了。

## 三臂原始數字（deliv 口徑＝accepted ∧ meets_demand，R667 :40 凍結）

```
arm          n  acc  refus   deliv%   meets%     d=o%  leak  c/task  calls/correct
OFF5       192  192      0   71.35    71.35    71.35    55    5.00      7.01
CONFORM    192  176     16   76.04    76.04    82.95    30    1.51      1.99
OFF        192  192      0   70.31    70.31    70.31    57    1.00      1.42
```
兩個分母都列在上表（`deliv% = 76.04` 用 processed=192；`d=o% = 82.95` 用
accepted=176）。**仲裁者是 R667 :40 的事前定義 `deliv`**，本輪沒有選分母。

## Q4（round678 推翻條件）與投影

disc_rate = 0.1406 落在 [0.036, 0.145] 內 ⇒ **Q4 未觸發，round678 的投影未作廢**：
事前那兩句照寫——**MDE 3.50pp、N₈₀≈703 題**（且 round678 自己記了 Clopper-Pearson
九角敏感度 **75–3773**、MDE@371 的三角 2.43/3.50/4.04pp）。

收官後用 r445 自己的資料重跑投影（第 4 行，已非期中）：
**MDE@371 = 4.31pp**、若真實效果＝觀測值則 80% power 需 **69 個 discordant pair
≈ 491 個配對任務**、題庫只有 378 題 ⇒ `可達？ False`。
序列推翻檢定：`觸發的推翻條件：無 ⇒ 判定：noise`（最近 5 個 `cbcbc` p=0.5000、
最近 8 個 `cbccbcbc` p=0.3633）。

⇒ **兩份投影並列**：事前的 703 與收官後的 491 都是小 n_d 的點估計，方向一致
（都超過或逼近題庫上限）。UNRESOLVED 的那一份是「**沒量出來**」，不是「沒有差異」。
