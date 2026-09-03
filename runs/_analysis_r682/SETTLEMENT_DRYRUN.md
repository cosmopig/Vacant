# R682 收官五行指令・合成收官 fixture 上的原始輸出

⚠⚠ 本檔所有實質數字都是 **FIXTURE**（/dev/shm 合成資料：r445 的 290 列真快照 ＋ 286 列
由已跑過的列複製、只換 task_id 補出來的假列）。**一個數字都不准當成 r445 的結果引用。**
特別是 conform_settle 印的 ON_WINS／+11.98pp：複製列會人工放大 discordant 數，
那是造 fixture 的方法造成的，不是資料。本輪報的是**結構事實**：rc、鍵在不在、計數。

## 五行的退出碼（--json 刻意指到不存在的目錄，同時驗本輪的修）
```
0) pool_precheck        rc=0   POOLABLE C1/C3/C4=HIT C2=UNVERIFIABLE_NO_CODE_VERSION（同 round680 真目錄）
1) pooled_paired_ci     rc=0   JSON 落盤，12 個頂層鍵
2) r445_predcheck --final rc=0 **從沒走過的判定分支**：HIT=5 MISS=3 ABORT=0 NOT_EVALUATED=0 BROKEN=0
3) conform_settle       rc=0   terminal=true 的 summary↔逐列 exact 覆算**全數通過**
                               calls 檢查層級 三臂皆 exact；P-C1_ci_verdict 鍵存在
4) power_paired         rc=0   JSON 18 鍵，key='deliv'
```

## 2) r445_predcheck --final 完整 stdout（FIXTURE）
```
=== /dev/shm/r682/fx/g_r445_conform_mbpp_ext  rows=576 sha8=2a77107a terminal=True ===
門檻來源：DECISION_20260903_R445_CONFORM_BANK_EXTENSION.md（每個數字都從該列的 quote parse，工具裡沒有門檻）
  P-E1  MISS             值=  11.9792  帶=[0.0, 6.0]     quote='[0, +6]pp'
  P-E2  MISS             值=   3.9067  帶=≤ 3.0          quote='半寬 ≤ 3.0pp'
  P-E3  MISS             值=  62.0000  帶=[20.0, 40.0]   quote='[20, 40]'
  P-E4  HIT              值=   1.5208  帶=[1.2, 1.6]     quote='[1.2, 1.6]'
          中止線 > 4.5 ⇒ triggered=False
  P-E5  HIT              值=   8.3333  帶=[3.0, 10.0]    quote='[3, 10]%'
  P-E6  HIT              值=   0.0000  帶=< 5.0          quote='<5%'
          中止線 > 20.0 ⇒ triggered=False
  P-E7  HIT              值= 192.0000  帶=== 192/192     quote='192/192'
  P-E8  HIT              值=  29.1667  帶=20.0–60.0      quote='20–60%'
  合計 HIT=5 MISS=3 ABORT=0 NOT_EVALUATED=0 BROKEN=0
  conform_settle 這些鍵對 r445 不適用（r444 口徑）：
    P-C1_band_3_to_6pp: r444 的帶是 [3,6]pp；r445 註冊的 P-E1 是 [0,+6]pp
    P-C1b_band_0.02_to_0.20: r444 的 p 值帶；r445 沒有註冊 p 值的帶
    P-C2_le_2.0: r444 的門檻是 ≤2.0；r445 註冊的 P-E4 是 [1.2,1.6]（≤2.0 會給假綠燈）
    P-C1_settlement_rule: 文字寫死 n=179；r445 是 192（併庫 371），照抄會寫出字面錯誤的句子
```
## 3) conform_settle 完整 stdout（FIXTURE）
```
=== /dev/shm/r682/fx/g_r445_conform_mbpp_ext  rows=576 sha8=2a77107a terminal=True ===
arm          n  acc  refus   deliv%   meets%     d=o%  leak  md&!acc  c/task
OFF5       192  192      0   70.83   70.83    70.83    56        0    5.00
CONFORM    192  176     16   82.81   82.81    90.34    17        0    1.52
OFF        192  192      0   70.83   70.83    70.83    56        0    1.00
paired[deliv       ] n=192 Δ=+11.98pp b=36  c=13  p=0.0014  95%CI=[+4.55,+17.89]pp ON_WINS  <= P-C1 用這個
paired[meets_demand] n=192 Δ=+11.98pp b=36  c=13  p=0.0014  95%CI=[+4.55,+17.89]pp ON_WINS  （analyze_paired 報的是這個）
calls 檢查層級：{'OFF5': 'exact', 'CONFORM': 'exact', 'OFF': 'exact'}  （exact＝逐位相同；bounded＝該臂有 void，改用碼蘊含的上下界）
{
  "P-C1_delta_pp": 11.979166666666666,
  "P-C1_band_3_to_6pp": false,
  "P-C1_ci_pp": [
    4.552041753474323,
    17.891598221544125
  ],
  "P-C1_ci_verdict": "ON_WINS",
  "P-C1_settlement_rule": "可以寫「打贏」；R440R 的 +3~+6pp 帶中不中另外單獨報，不改判定",
  "P-C1b_p": 0.001402688503695515,
  "P-C1b_band_0.02_to_0.20": false,
  "P-C2_calls_per_task": 1.5208333333333333,
  "P-C2_le_2.0": true,
  "P-C2_abort_gt_4.5": false,
  "P-C3a_refusal_rate": 0.08333333333333333,
  "P-C3a_band_3_to_10pct": true,
  "P-C3b_leaked": {
    "OFF5": 56,
    "CONFORM": 17,
    "OFF": 56
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
## 4) power_paired 完整 stdout（FIXTURE）
```
配對數（目前）n = 192
discordant 到達序列（49 個）：cbbbbbcbbbbbbbbbbcccbbbbbbccbbcbbbccbbbbcbcbbcbbb
  b（只有 CONFORM 對）=36   c（只有 OFF5 對）=13
  全序列 McNemar 精確雙尾 p = 0.0014

  最近 5 個 = bcbbb  同向最多 4/5  單尾 p = 0.1875
  最近 8 個 = bcbbcbbb  同向最多 6/8  單尾 p = 0.1445
觸發的推翻條件：['T3']  ⇒ 判定：signal_worth_following

discordant rate = 25.52%
n=371 時預期 discordant≈95，要 p<0.05 最少要 58:37 （|b-c|≥21）⇒ MDE = 5.66 pp
若真實效果＝觀測值（p_b=0.735），80% power 需要 34 個 discordant pair ⇒ 約 134 個配對任務
題庫只有 378 題 ⇒ 可達？ True
```
