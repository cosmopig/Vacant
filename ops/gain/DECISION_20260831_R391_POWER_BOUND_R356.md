# DECISION round391 — `g_r356_3arm_20260830` 的 ON vs OFF5 主判準：套用 round83 的 power 分解，結論同型重現

日期 2026-08-31 09:22–09:33 UTC　模型 Sonnet 5　作者 round391

> **一句話**：round83（見 `DECISION_20260825_ROUND83_POWER_DECOMPOSITION.md`）
> 在舊 run（`g_off371`/`g_onoff5_v3`）發現「ON vs OFF5 換再難的題也答不出來」，
> 那是配對 power 的結構性上界，不是那一批資料的偶然。本輪把同一支已驗證的
> 工具（`analyze_power_decomposition.py`，round83 新增、附 self-test）套到
> 現在真正在跑、預定要當最終結論依據的 run（`g_r356_3arm_20260830`，
> target n=179/arm）——**同一個結論重現**：在目前 n 與觀測 accuracy
> 水準下，即使跑滿 179/arm、甚至整個 378 題庫，這個主判準都解析不出
> observed 差距（1.5pp）這麼小的效應。這件事之前從未在 r356 這支 run 上
> 算過，是本輪新增的判斷，不是重複舊結論。

---

## 1. 為什麼要做這件事

round388-390 三輪都在監看 off5v 的 `(b,c)=(0,5)` 卡住不動，但沒有人回頭問
「主判準 ON vs OFF5 本身，在這個 run 的目標 n=179 下，統計上到底有沒有機會
解析出目前觀測到的效應量」。round83 已經在舊 run 上建立過這套方法論，
本輪只是把它**套用到當前 run**——這是應用已驗證工具到新資料，不是重新發明。

## 2. 量測（`analyze_power_decomposition.py`，self-test 已在 round83 驗證，本輪未改工具本身）

```
$ python3 ops/gain/analyze_power_decomposition.py \
    --pair ON=runs/g_r356_3arm_20260830 OFF5=runs/g_r356_3arm_20260830 \
    --bank-capacity 179

n_common=65  b(ON only)=3  c(OFF5 only)=4  p_disc=0.1077  psi=0.4286
acc_ON=73.85%  acc_OFF5=75.38%  diff=-1.538pp  exact_mcnemar_p=1.0

required_n_at_observed_effect = 3682   answerable_within_capacity(179) = False
resolvable_floor_at_capacity(179):  min_abs_diff_pp = 7.108pp
feasibility_bound: required_n_at_max_p_disc(理论上限p_disc=0.5) = 793
                    still_impossible_at_capacity(179) = True
```

把 `--bank-capacity` 換成 MBPP+ 的全庫上限 378（不是只到 179 的既定目標）
重算一次，看「就算不設 179 的門檻、把整個題庫都拿來跑」還能不能解析：

```
$ python3 ops/gain/analyze_power_decomposition.py \
    --pair ON=runs/g_r356_3arm_20260830 OFF5=runs/g_r356_3arm_20260830 \
    --bank-capacity 378

resolvable_floor_at_capacity(378):  min_abs_diff_pp = 4.954pp
feasibility_bound: required_n_at_max_p_disc = 793
                    still_impossible_at_capacity(378) = True   ← 793 > 378
```

`ON vs OFF`（次要對照，只是拿來對照 p_disc 量級，不是主判準）：

```
n_common=68  b=5 c=5  psi=0.5（完全打平）  diff=0.0pp
resolvable_floor_at_capacity(179): min_abs_diff_pp = 8.382pp
```

## 3. 讀法（沿用 round83 §5-6 的寫法，不重新發明判準）

- `required_n_at_observed_effect=3682` 遠超過 179，也遠超過整個題庫 378。
- `feasibility_bound.still_impossible_at_capacity=True`——這一項用的是
  **理論上可能達到的最大 `p_disc`**（兩臂 accuracy 固定在觀測水準
  ~74-75% 時，`p_disc` 的數學上界 `2a(1-a)`），不是觀測到的 `p_disc`。
  即使把難度旋鈕轉到理論極限，所需 N（793）仍然超過整個 378 題庫。
  ⇒ **這不是「還沒跑夠」，是「題庫容量的硬上界」**——與 round83 §5 的
  同一個結構性結論（那時是 371 題庫、`required_N=1144`；這次是
  378 題庫、`required_N=3682`，量級不同但性質相同：都遠超容量）。
- `resolvable_floor_at_capacity`：在 179 題目標下，80% power 能分辨的
  最小差距是 **7.1pp**；就算跑滿整個 378 題庫也只降到 **4.95pp**。
  觀測到的差距只有 **1.5pp**，落在解析度以下**兩種容量設定下都一樣**。

## 4. 結論（上界，不是「量不到」——round83 §6 的同一個寫法）

> 在目標 n=179（甚至整個 378 題庫）下，80% power 能分辨的最小差距是
> 4.95–7.1pp。觀測到的差距是 1.5pp（方向對 ON 不利，OFF5 微幅領先），
> 落在解析度以下。
> ⇒ **|ON − OFF5| < 7.1pp（179 題時）／< 4.95pp（378 題時）**，
> 且點估計方向對 ON 不利。

這回答的正是 loop prompt 「打不贏也是結論，照實寫」——**在等呼叫預算下，
Vacant 完整機制相對 self-consistency 的增益，若存在，小於這個題庫能解析的
最小刻度，且目前的點估計方向甚至不利於 ON。**

## 5. 這不代表停止累積 n——但要誠實預告最終結果會是什麼形狀

繼續跑到 n=179 仍然值得：(a) 收斂 CI 寬度、把「上界」這個數字算得更精確；
(b) `psi`（目前 0.4286，只靠 7 個 discordant pair 撐著，round83 §7 講過
這種小樣本 ψ 估計極不穩定）有可能在更大 n 下顯著偏離 0.5——**這是唯一
能推翻本節結論的方向**，見下面推翻條件。但**要先寫死預期**：
除非 ψ 大幅偏離目前的 0.43，否則跑滿 n=179 時，主判準 ON vs OFF5
**大概率仍會是「不顯著、差距在解析度以下」**，不是某一輪之後突然
p<0.05 跳出來的東西。之後的監看輪次不應該把「還沒顯著」讀成
「再等等就會顯著」——除非 `required_n_at_observed_effect` 這個數字
本身開始大幅下降（代表 ψ 正在往極端移動）。

## 6. 對照：off5v/off5va 這條輔助線比主判準更接近可解析

`analyze_off5v.py` 量到的 off5v gap 是 **7.81pp**（discordant `(b,c)=(0,5)`，
p=0.0625），比主判準的觀測差距（1.5pp）大得多，也比 179 題下的解析度
下限（7.1pp）還要略高——**這條線本來就比主判準更有機會達到顯著**。
且它的結構很脆弱：`(b,c)=(0,5)` 時 exact 二項 p=0.0625；只要**再出現
一個**方向不變的 discordant pair（c: 5→6，b 仍是 0），p 就會降到
`2×0.5^6=0.03125`，跨過 0.05。**這比主判準的「需要再跑 3600+ 題」
便宜到不是同一個量級的問題。**

## 7. 推翻條件

1. 若 `required_n_at_observed_effect`（目前 3682）在後續檢查點大幅下降
   （例如 <500），代表 ψ 正在往遠離 0.5 的方向移動，本節「無法解析」的
   結論作廢，應該重新評估目標 n。
2. 若 off5v 的 `(b,c)` 首度偏離 `(0,5)`（不論往哪個方向動），第 6 節的
   「一步之遙」判讀需要重新計算（p 值不再是 0.0625 的下一步）。
3. 若 n=179 跑滿後 `feasibility_bound.still_impossible_at_capacity`
   翻轉為 False（代表兩臂 accuracy 水準本身系統性偏離目前的 ~74-75%），
   第 3-4 節的數字要整批重算，不能沿用本輪算出的 7.1pp/4.95pp。

## 8. 本輪沒做的事（照實寫）

- 沒有修改 `analyze_power_decomposition.py`、`gain_run.py` 或任何既有
  參數／判準——本輪只是把既有工具套到一支新 run 上讀數字。
- 沒有 kill 或重啟 PID 2266603（decisive run，全程存活，本輪監看時
  elapsed 55726s → 56378s，rows 237 → 242）。
- 沒有因為「主判準解析不出來」就提早結束這支 run 或改目標 n——
  第 5 節已說明為什麼繼續累積仍有價值。
- 沒有去對 off5v 的 discordant task 做任何新的逐題檢查——round388
  已經做過，本輪只是引用既有結論算一個新的「還差多遠」數字。
