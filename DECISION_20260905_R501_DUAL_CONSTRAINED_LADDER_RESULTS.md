# R501 結果：同時等被分析列數 ∧ 等跨度的視窗下，位置**仍然**翻得動梯子判決

判準：`DECISION_20260905_R501_DUAL_CONSTRAINED_LADDER_PREREG.md`（commit `dd3c861`，**量測之前**單獨 commit；原提交 `541c587`，被另一個 session 的 `pull --rebase` 重放成 `dd3c861`，內容逐字相同）。
尺：`ops/gain/r501_dual_constrained_ladder.py`（selftest **21/21**）／`ops/gain/r501_mutation_check.py`。
資料：`ops/gain/data/r501_dual_constrained_ladder.json`、`ops/gain/data/r501_mutation_check.json`。
快照：`ops/gain/data/r486_gateway_snapshot_v2.json`（`n_rows_sorted` 依 ts 排序後、`n_analysable=728`）。

## 一 頭條

```
verdict=DUALWIN_OK   blockers=[]   live_reads=0   n_exceptions=0   elapsed_s=68.1
M=[364, 555]  n_analysable=728  tau=0.10  K=6
pin_match      {"364": true, "555": true}          # G-PINNED 現場重算 == 釘死字面值
disp           {"364": 0.6731, "555": 0.9827}      # min_gap / even_gap（新指標）
span_spread    {"364": 0.0901, "555": 0.0996}      # (max-min)/min，兩層都 <= tau
cells          {r489: BOTH, r490: BOTH}
headlines      {r489: POSITION_SURVIVES, r490: POSITION_SURVIVES}
calibration    {"C_POS": "NEITHER", "C_NEG": "N_MATTERS"}
```

視窗跨度（秒）：

```
tier M=364  [13015.2, 12722.6, 12993.8, 13869.3, 13178.5, 13019.0]
tier M=555  [20649.2, 20918.8, 22541.7, 22148.5, 22207.0, 22705.4]
```

層內判決集合（`R496.classify` 的 `by_tier`）：

```
r489  364: CONCURRENCY_TAXES / EXPOSURE_DEGENERATE / PERIOD_CONFOUNDED / PLACEBO_LADDER_BROKEN / UNRESOLVED
      555: CONCURRENCY_TAXES / PLACEBO_LADDER_BROKEN
r490  364: EXPOSURE_DEGENERATE / PLACEBO_LADDER_BROKEN / PRIMARY_IS_POSITIVE_CONTROL / UNRESOLVED
      555: PLACEBO_LADDER_BROKEN / PRIMARY_IS_POSITIVE_CONTROL
```

⇒ **在被分析列數與跨度同時夾住之後，六個等距鋪開的視窗仍然給出多達五種不同的判決。**

## 二 預測逐條（判準 §三）

| 代號 | 預測 | 實際 | 結果 | intent |
|---|---|---|---|---|
| `P1` | 兩支 probe 都 `POSITION_SURVIVES` | 兩支都 `BOTH → POSITION_SURVIVES` | **HIT** | evidence |
| `P2` | `blockers` 為空 | `DUALWIN_OK`，`blockers=[]` | **HIT** | guard |
| `P3` | `M==(364,555)`、`n_analysable==728` | 完全相同 | **HIT** | guard |
| `P4` | 兩層 `span_spread <= 0.10` | 0.0901／0.0996 | **HIT** | guard |
| `P5` | `disp ≈ 0.6731 / 0.9827` | **逐字相同** 0.6731／0.9827 | **HIT** | guard |
| `P6` | 至少一支 cell 與 R498 的 `BOTH` 不同（低信心的賭注） | 兩支都仍是 `BOTH` | **MISS** | evidence |

`P6` MISS 照實記：**夾住跨度沒有改變任何一格的分類。** 這是本輪唯一一條 evidence 型的賭注，
輸了。它的意思是：R498 的 `BOTH` 不是由跨度差異撐起來的。

⚠ `P2`–`P5` 事前就標 `intent: guard`，**不算證據**（memory：`FORCED_GREEN` ≠ 有缺陷，但 guard 的綠燈不能當佐證）。
真正承重的只有 `P1`（HIT）與 `P6`（MISS）兩條。

## 三 突變表（判準 §五）：**5/5 DETECTED、0 crash**

`clean_direction_ok=true`（判準 §二 的前提成立：乾淨那格確實是 `POSITION_SURVIVES`
⇒ 這張表的偵測方向不會像 R499 那樣集體失效）。

| 代號 | 預期看見 | 實際 blockers ／ headline | 結果 |
|---|---|---|---|
| `M1_ONE_POSITION` | `BROKEN_WINDOWS` | `['BROKEN_WINDOWS','BROKEN_DISPERSION']` | **DETECTED** |
| `M2_R498_EDGES` | `BROKEN_EQSPAN` | `['BROKEN_EQSPAN']`，`span_spread` 0.6412／0.2477 | **DETECTED** |
| `M3_PIN_SHIFT` | `BROKEN_PINNED` | `['BROKEN_PINNED','BROKEN_EQSPAN']` | **DETECTED** |
| `M4_FORCE_SAME` | headline 翻成 `POSITION_GONE` | 兩支都 `POSITION_GONE`（另觸 `BROKEN_CALIBRATION`） | **DETECTED** |
| `M5_CLUSTERED` | `BROKEN_DISPERSION` | `['BROKEN_DISPERSION']`，`disp` 0.0137／0.0289 | **DETECTED** |

### 三-A 判準 §五 寫的 `M2` 預期是兩個 blocker，實際只有一個——照實記，並說明為什麼

判準 §五 寫 `M2` 預期 `BROKEN_PINNED ＋ BROKEN_EQSPAN`。實作時把 **G-PINNED 的重算**
與**實際使用的左緣**拆成兩條路徑（`pinned_for()` vs `edges_for()`），所以 `M2` 只動後者
⇒ 只觸 `BROKEN_EQSPAN`。**這是專一性變好，不是漏掉**：`M3` 動前者、`M2`／`M5` 動後者，
三個突變體因此各自對應到不同的擋門。判準寫的是量測前的預期，**原文不改**。

### 三-B 🔴 `M5` 是本輪最有內容的一格：新的 `disp` 門檻在**真資料上**承重

`M5_CLUSTERED` 把左緣換成 R499 舊解法那種「五個幾乎重合＋一個遠端」的形狀。結果：

```
M5   disp = {"364": 0.0137, "555": 0.0289}   span_spread = {"364": 0.005, "555": 0.0996}
乾淨  disp = {"364": 0.6731, "555": 0.9827}   span_spread = {"364": 0.0901, "555": 0.0996}
```

⇒ **群聚左緣的等跨度反而更好（tier 364 的 `span_spread` 0.005 vs 乾淨的 0.0901）。**
R499 舊的 `pos_spread=(max-min)/room` 對這組群聚左緣給的是**滿分**（兩端一樣遠），
所以舊判準會把它當成合格設計收下——而那組視窗在位置軸上根本沒有鋪開。
本尺的 `min_gap/even_gap` 把它壓到 0.0137 ⇒ **`K=6` 這道加嚴從「零承重」（R499 `M4_BAND_K2` MISSED）
變成有牙齒**。這正是 round769 交棒第 2(b) 項要修的東西，**修好了而且被真資料上的突變體看見**。

🆕 **可重複使用的通則：「約束滿足得更好」與「設計更有代表性」是兩回事。**
把樣本擠在一起通常會讓等化型的約束更容易滿足（跨度更接近），
⇒ **任何等化設計都要同時管『約束殘差』與『被等化維度以外的鋪開程度』，只管前者會獎勵退化解。**

## 四 兩個相反的誤讀（判準 §四 事前寫死，逐字檢查）

- ⛔ **不准寫成「已排除跨度混淆、位置效應是真的」。** 本輪同時夾住的是**被分析 n** 與**跨度**兩軸。
  R497 量到的**組成軸**（chat 佔比 31%→24%）**沒有夾**；`r489.analyse:255` 的曝光索引仍用
  **chat 全體**而非 `chat ∧ analysable`（round768／769 都記過，本輪同樣沒動）。
  ✅ 准許的寫法：**「在同時等被分析 n 與等跨度的視窗下，位置仍翻得動判決。」**
- ⛔ **不准寫成「R498／R496 被推翻」或「白做」。** 三輪換的是等化單位，是同一條敏感度曲線上的點；
  本輪的 `P6` MISS 反過來證明 R498 的 `BOTH` 不是跨度造成的。
- ⚠ `span_spread` 的分母本尺用 `min`（判準 §一.7），R498 用 `median`
  ⇒ **0.6412 vs R498 記的 0.5591 不是矛盾，是兩個定義**。要比就比方向，不要比數字。
- ⛔ 本輪**沒有**碰梯子本身（round762 裁決）。`PLACEBO_LADDER_BROKEN` 這個全視窗判決原樣是 R489/R490 的。

## 五 還沒做／已知殘留

1. **組成軸沒夾**（R497 的 chat 佔比）——三軸同時等化還沒有人試過可行性。
2. `r489.analyse:255` 曝光索引母體不一致（chat 全體 vs chat ∧ analysable），連三輪未動。
3. **R495 的承重牆刪除測試仍未做**（R496 的已於 R500 做完）。
4. 判準 §一.6 的 `DISP_MIN=0.5` 是 `intent: guard`：R499 已公布 0.6731／0.9827
   ⇒ 這道門檻在**乾淨資料上必然通過**，它的價值全部來自 `M5`（真的擋下退化解），
   **不准拿它的綠燈當任何結論的佐證**。
