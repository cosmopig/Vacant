# R440W：CONFORM 的**決策量具**（visible_check）雙向驗證——發射前預註冊

（2026-09-03 round648，Opus 5。**判準與預測寫在量測之前並先 commit**，
量完不准改。對象是即將由 `ops/gain/launch_conform.sh` 自動發射的
`runs/g_r444_conform_mbpp`（R440R 預註冊）。）

## 一、為什麼要多這一步——現有的 probe 驗不到 CONFORM 的閘門

`probe_instrument()`（`ops/gain/gain_run.py:180`）是 SPEC_GAIN §5.2 要求的雙向驗證，
但它第 205 行只讀 `t["hidden_check"]["code"]`——**它驗的是計分量具，不是決策量具。**

對 OFF／ON／OFF5 這樣就夠：`visible_check` 在那三條臂裡只是一個落盤欄位
（`arm_off` 的 `visible_ok`），不改變任何選擇。

**CONFORM 不同。** `arm_conform()`（:464）拿 `visible_check` 當**出貨閘門**：
通過就早停、全不通過就拒交。也就是說 `visible_check` 直接決定
P-C1（通過率）、P-C2（`calls_per_task`）、P-C3（拒交率）三個預註冊預測。
**這把尺從來沒有被雙向驗證過**，`--probe-sample 0`（＝全部題目，:1067，
不是「跳過」）也只會把 hidden 那把尺驗得更徹底。

LOOP_PROMPT：「任一方向不滿分就停，不要在壞尺上跑實驗。」本檔補上這一步。

## 二、量什麼（範圍寫死）

對 `--bank evalplus --seed g-r212-route-20260828 --n 179` 載出的**那 179 題**
（與發射指令逐字相同的取樣），零模型呼叫，只跑沙箱：

| # | 量 | 方法 |
|---|---|---|
| M1 正向 | 官方參考解對 `visible_check` **全過** | `meets_demand(ref, visible)` |
| M2 反向 | 空樁 `def f(*a,**k): return None` 對 `visible_check` **全擋** | `meets_demand(stub, visible)` |
| M3 覆蓋 | 179 題裡有幾題**有**官方參考解（M1/M2 的分母） | `_canonical_solutions()` |
| M4 切片器 | `_visible_test_slicer()` 認得幾題的形狀、各有幾條驗收 | 純解析，零執行 |

M3 是分母，**必須單獨報**：沒有參考解的題目在 M1/M2 是「這一格沒量到」，
不是「量到通過」（鐵律 2 同構）。

## 三、事前預測（跑完對答案）

- **P-W1**：M1 ＝ 100%（分母 M3）。根據：MBPP+ 的 hidden ＝ base＋plus、
  visible ⊆ hidden，參考解既然過 hidden 就必過 visible。
- **P-W2**：M2 ＝ 100%。根據：空樁回 None，任何一條 assert 都會擋下它。
- **P-W3**：M4 認得 ≥80% 的題目。根據：MBPP 的 check 多是扁平 assert 串。
- **P-W4**：M4 不會出現 `n_visible_tests == 0` 的題目。**這條是 P-W2 的機制解釋**：
  零條驗收的題目會讓空樁「通過」，那就是「閘門沒有閘」。

## 四、判準（**先寫死，量完不准改**）

- **M2 < 100% ⇒ 硬阻斷。** 閘門會放行空樁 ⇒ CONFORM 的早停是假的，
  P-C2 的「便宜」會是量具假象。**不發射**，寫進 GAIN_STATE 最上面交給人類。
- **M1 < 100% ⇒ 阻斷並回報。** 閘門會誤丟正確解 ⇒ P-C3 的拒交率量到的是量具誤差
  不是機制。**不准為了讓數字好看去放寬閘門**（那是改實驗條件）。
- **M4 覆蓋率低 ⇒ 不阻斷、照實記。** 切片器認不得只影響收據裡「卡在第幾條」
  這個欄位（會是 `check_code_shape_unrecognised`，程式自己會誠實標記），
  不影響 accept/reject。但要把數字寫進 GAIN_STATE，**P-C4 的驗收要照這個數字打折**。
- 三條都滿足 ⇒ 不改任何東西，讓排程器照原計畫發射，把數字記進 STATE。

## 五、推翻條件／預期會多冒出一類

事前聲明：**很可能會冒出「參考解自己就不過 visible」的第三類**（例如 loader 的
`entry_point` 與參考解的函式名不一致）。真的冒出來就**照實寫、人眼確認、
不算進 M1 的分子也不算進分母，另立一欄**——不准當場補判準去救它（R440V 同規則）。

## 六、這一步不做什麼

不改 `gain_run.py`、不改 `launch_conform.sh`、不動 E3、不起任何 run。
純量測。若判準要求阻斷，做法是**寫進 GAIN_STATE 最上面 ＋ 停用排程器**，
而停用排程器屬於「改變已預註冊的計畫」⇒ 要在 STATE 裡寫明理由與證據。
