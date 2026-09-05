# R502 結果：組成軸**不是**自由的——它是「等 chat-n ∧ 等跨度」的推論（P1 MISS）

判準 `a97b1e8`（`DECISION_20260905_R502_TRIPLE_CONSTRAINED_LADDER_PREREG.md`），量測在判準之後。
工具 `ops/gain/r502_triple_constrained_ladder.py`（selftest **28/28**）、
`ops/gain/r502_mutation_check.py`。快照 `ops/gain/data/r486_gateway_snapshot_v2.json`（`live_reads=0`）。

## 一 頭條

```
verdict = STAGE2_SKIPPED_COMP_FORCED_BY_OTHERS      blockers=[]  live_reads=0  n_exceptions=0
comp_axis_verdict = COMP_FORCED_BY_OTHERS           M=[364,555]  n_analysable=728  tau=0.10  K=6
tier 364:  n_feasible_bands=155   n_bands_over_upper_bound=0   band_max_spread=0.0753  min_gap_required=37
tier 555:  n_feasible_bands=97    n_bands_over_upper_bound=0   band_max_spread=0.0764  min_gap_required=18
```

**在 155＋97 個可行的等跨度帶裡，沒有任何一個帶的「全帶」組成極差超過 τ=0.10**（最大 0.0753／0.0764）。
全帶極差是帶內任何 K 子集極差的上界 ⇒ **不可能造得出違反等組成的視窗組**
⇒ 「組成也夾住了」這個合取項在這份資料上**不可能為假**。

⛔ **准許的寫法**：組成軸由前兩條約束承重（R492 的 `FORCED_BY_OTHERS`）。
⛔ **不准寫**「我們控制了三個混淆／組成軸已排除」——那會把一個推論記成第三份獨立證據。

## 二 事前預測的帳（照判準 §三 逐條，evidence 與 guard 分開）

| # | intent | 事前 | 實得 | 判 |
|---|---|---|---|---|
| P1 | evidence | `COMP_FREE`（信心中高） | `COMP_FORCED_BY_OTHERS` | **MISS** |
| P2 | evidence | 三重約束下兩支 headline 皆 `POSITION_SURVIVES` | 前件為假（第一段判 FORCED ⇒ 判準 §二 明文跳過第二段） | **NOT_EVALUATED**（⛔ 不准記成 HIT） |
| P3 | evidence | 三重 `disp` **嚴格小於** 雙重（0.6731／0.9827），至少一層 | 事後診斷測得**兩層皆相等** | **MISS**（由事後診斷確立，見 §四） |
| P3′ | IDENTITY | 三重 `disp ≤` 雙重 | 成立（相等） | 窮舉斷言，**不是證據** |
| P4 | guard | `C_POS=NEITHER`／`C_NEG=N_MATTERS` | 第二段沒跑 ⇒ 沒算 | **NOT_EVALUATED** |
| P5 | guard | `live_reads=0`、`n_exceptions=0` | `0` / `0` | HIT（guard，不當佐證） |

**兩條被評估到的 evidence 預測全部 MISS。** 我事前的推理是「R501 釘死那組已經到 τ 的 62%／77%，
全帶數百個候選再撐開 30% 應該做得到」——**錯在把「一個 K 子集的極差」外推成「全帶的極差」**：
全帶極差只比那個子集大 0.0619→0.0753（+21.6%），根本不到 τ。
🆕 **通則：「這個子集已經接近門檻」不蘊含「母集合跨得過門檻」**，兩者差的是分佈的尾巴不是中位數。

## 三 判準 §六.1 的推翻條件觸發了——照實寫，不當場補判準

§六.1 事前就寫了這一格：「⇒ P1 MISS，且 §〇 的整個問題被推翻」。**照它辦**，本輪不改頭條、不放寬 τ、
不換組成量的定義。round770 交棒第 2 項（「三軸等化」）的答案是：**第三軸不存在，不必造。**

## 四 事後診斷（明確標示：**不是證據**，只用來防我自己推錯）

### 4.1 三重約束的選點退化成 R501 的選點（`--posthoc-stage2`）

推導：全帶組成極差 ≤ τ ⇒ 以**最小** share 當錨點的組成子帶＝整個帶 ⇒ 組成過濾砍不掉任何東西。
真資料對過一次（memory：推理推錯、跑一次最小重現才看出來）：

```
tier 364  triple=[0,49,98,147,196,248]  r501=[0,49,98,147,196,248]  identical=true  disp 0.6731 = 0.6731
tier 555  triple=[0,34,68,102,136,170]  r501=[0,34,68,102,136,170]  identical=true  disp 0.9827 = 0.9827
all_identical = true
```

⇒ 就算硬跑第二段，**它會逐字元重現 R501 的視窗**＝一次強制綠燈的複製，沒有新資訊。這也是 P3 MISS 的來源。

### 4.2 `FORCED` 這個判決有多少是 `DISP_MIN` 造成的？——不是它造成的

```
tier 364   disp>=0.5: FORCED 155 帶 max=0.0753 | disp>=0(全拿掉): FORCED 357 帶 max=0.0755 | tau=0.05: FORCED 51 帶 max=0.0410
tier 555   disp>=0.5: FORCED  97 帶 max=0.0764 | disp>=0(全拿掉): FORCED 168 帶 max=0.0764 | tau=0.05: FORCED 50 帶 max=0.0381
```

把分散度過濾整個拿掉（候選帶 155→357／97→168）上界幾乎不動；**連 τ 收緊成 0.05 都仍是 FORCED**。

### 4.3 機制：夾住組成的是**跨度**那一條，不是 chat-n 那一條

完全不夾跨度時，同一批左緣的組成極差是：

```
tier 364   share 0.2203 – 0.3227   spread = 0.4645
tier 555   share 0.2445 – 0.2900   spread = 0.1860
```

⇒ **R497 量到的 31%→24% 是真的、而且比 R497 報的更大（tier 364 極差 46.5%）**；
是**等跨度**那一條把它壓到 ≤0.076。機制清楚：M 固定 ⇒ `share = M / n_total`，
而等跨度視窗裡的閘道總列數由總吞吐決定，總吞吐與 chat 吞吐幾乎同步 ⇒ 組成被鎖死。

🆕 **這同時說明了「三重約束」的另一個身分**：M 固定時夾組成 ≡ 夾閘道總列數，
而閘道總列數正是 **R496** 夾的單位 ⇒ R501 的雙重約束**其實已經同時滿足 R496 與 R498 的單位**。

## 五 突變表：在真資料上**零承重**，照實記

```
counts = {DETECTED: 0, MISSED: 1, UNREACHABLE: 5, BROKEN_CRASH: 0}
clean: verdict=STAGE2_SKIPPED_COMP_FORCED_BY_OTHERS  comp_axis=COMP_FORCED_BY_OTHERS  stage2_ran=false
M1_COMP_TAU_HUGE  UNREACHABLE   M2_COMP_IGNORE  UNREACHABLE   M3_SHARE_CONST  MISSED
M4_FORCE_SAME     UNREACHABLE   M5_DISP_IGNORE  UNREACHABLE   M6_ONE_POSITION UNREACHABLE
```

- **M1／M2／M4／M5／M6 `UNREACHABLE`**：乾淨執行沒走到第二段 ⇒ 那五個偵測器**沒有任何真資料在守**。
  它們的牙齒全部只在合成夾具上（selftest 的 `triple_M*` 六條，兩個方向都有對照）。
- **M3 `MISSED`**：判準 §四 事前寫的偵測器是「comp_axis_verdict 翻成 FORCED」，
  而乾淨那格**本來就是** FORCED ⇒ 偵測器結構上不可能翻。這是強制綠燈的鏡像。
  事後附記（**不是**判準，不追認）：M3 底下 `band_max_spread` 由 `0.0753/0.0764` 掉到 `0.0/0.0`
  ⇒ **會變的量是 `band_max_spread`，不是 verdict**。下一輪若要再用這支尺，偵測器應該釘那個量。
- ⛔ **不准為了讓突變表好看去改 τ 或 DISP_MIN**（判準 §四 明文）。

🆕 **通則：突變表的承重與「乾淨判決落在哪一格」是綁在一起的**——乾淨判決一旦落進「提前 return」
的分支，所有下游突變體同時變成 `UNREACHABLE`，而它的外觀（全部沒紅）跟「偵測器沒牙齒」一模一樣。
⇒ **突變表要報三個數字（DETECTED／MISSED／UNREACHABLE），只報「幾個紅」會把這件事藏起來。**

## 六 對上游結論的影響

1. **R501 結果檔那句「⛔ 不准寫『已排除跨度混淆／混淆已控制』，因為組成軸沒夾」——
   前半仍然對（不准寫已控制），但理由要改**：組成軸不是「沒夾」，是「夾不動，因為它不是自由的」。
2. R501 的 `POSITION_SURVIVES` 不會因為本輪而改變，本輪也沒有重跑它（第二段沒跑）。
3. 交棒第 2 項（三軸等化）**收官**：不必造。剩下的殘留混淆要另找軸，
   而且下一個候選軸在提出時就要先跑本輪這種 `FORCED_BY_OTHERS` 上界檢查，再花力氣造設計。

## 七 誠實邊界

- 本輪**沒有**重跑梯子（判準明文跳過），所以本輪對「位置翻不翻得動判決」**沒有新證據**。
- `COMP_FORCED_BY_OTHERS` 是**這份快照 ∧ 這個母體 ∧ 這組 (τ, K, DISP_MIN)** 下的陳述；
  正對照（合成資料判 `COMP_FREE`、附 witness）在 selftest 裡，證明這支尺**判得出**另一格。
- §四 全部是事後診斷，**不進預測帳**。
