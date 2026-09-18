# R455：把可證偽性普查延伸到 R452——收官的**頭條結果**還沒被普查過

（2026-09-04 round722，Opus 5。`runs/g_r447_conform_lcb2` **仍在跑**（本文件寫定時
rows=311/360，`pace_probe` ETA ~15:52 UTC）。本文件在**改任何一行程式碼之前**寫定，
量完不准改分類規則、不准改預測表、不准改 `intent`。本輪**不是**收官輪、
**不改** R440Z／R450／R451／R452 任何條文、**不改**任何 P-Z 或 W 的判決。）

## 一、為什麼是 R452（round722 開場查到的具體缺口）

R453（round715）普查了 **R440Z**，R454（round718）延伸到 **R450**。但歷輪 STATE 寫的
收官仲裁者是：

> R440Z §三／§六 ＋ R450 §四 ＋ **R451** ＋ **R452（含 §九）** ＋ R453 ＋ R454

`ops/gain/data/r454_census.json` 目前 19 筆記錄：14 筆 R440Z ＋ 5 筆 R450。
**R451 與 R452 一筆都沒有。** 而 R452 產出的是收官的**頭條數字**——
「等預算下閘門 vs 多數決在難題庫上的 Δ」，也就是鐵律 1 在 LCB2 上的答案。
R453 自己的教訓是「空綠燈要成群抓」，而目前抓過的兩群裡**不含最會被引用的那一群**。

**開場逐字讀 `ops/gain/r447_eq5_offline.py:180-191` 與 `gain_run.py:arm_off5` 之後**，
先排除掉一個原本最像的懷疑：R452 §四.2 的真資料校準**不是**循環的——
`ci` 取自 rows 自己記的 `involved.index(worker)`，而 `got=(visf[ci],hidf[ci])` 是把
`calls.jsonl` 的候選碼**重新執行**算出來的，兩者出處不同（run 當下的沙箱 vs 離線重執行）。
且用 `ast` 逐字確認 `arm_off5` 寫的是真的 `visible_ok, _ = meets_demand(...)`，
**不是** `arm_conform` 那種 `"visible_ok": accepted` 的自證式寫法。

⇒ 所以本輪的懷疑對象換成**第二層**：校準雖然非循環，但
**若可校準那一群的 `expect` 幾乎都是同一個值，「100% 一致」就接近結構強制**
（記憶鐵律：沒有基準率的「支持」可能結構性不可能有反例＝空洞綠燈）。
R452 §五 W1 是整把尺可不可信的門票，收官會拿它當「重建有效」的憑據。

## 二、量什麼（分類規則，**沿用 R453 §二／R454 §二，不新增格子、不新增旋鈕**）

| 類別 | 條件 | 收官該怎麼寫 |
|---|---|---|
| `FORCED_GREEN` | 寫得出恆等式 **且** witness＝0 | HIT 不帶資訊；要附恆等式與基準率 |
| `EVALUABLE` | witness ≥ 1 | 照常寫，HIT 帶資訊 |
| `UNRESOLVED` | 兩者皆無 | 照實寫「判不出來」，不准往任一邊倒 |

擋門 B1–B5 一併沿用（B1 恆等式成立 ∧ witness>0 ⇒ `CONTRADICTION`；
B4 完整題目 < 20 ⇒ `UNCALIBRATED`；B5 CONTRADICTION／SOURCE_DRIFT 時不吐 FORCED_GREEN）。

**新增的不是格子，是一個非仲裁註記**（與 R454 的 `instrument_resolution_NOT_ARBITER`
同型、同樣不改任何分類）：對 witness＝0 的條目附
`discrimination_baserate_NOT_ARBITER` = 該擋門的輸入在本 run 上的**值分佈**。
比值意義：若 `expect` 兩個值都出現過，「100% 一致」是真的有機會被推翻；
若全部同值，那個 100% 主要來自基準率。**它不改分類，只影響收官怎麼措辭。**

## 三、事前預測（**現在寫，還沒算**；量完照實對帳，**錯了不准回頭改這張表**）

`intent` 是事前判斷：`evidence`＝收官會拿來當佐證（FORCED_GREEN 就要警告）；
`guard`＝只防 infra／半殘資料（FORCED_GREEN 是設計如此，不算缺陷）。

| # | R452 子句 | 證偽事件 | 預測類別 | `intent` | 根據 |
|---|---|---|---|---|---|
| R452-W1 | 校準一致率 100% ∧ 可校準 ≥20 | 任一題 rows 與重建不符 | **`UNRESOLVED`** | `evidence` | 非循環（§一）但實測 witness=0；無恆等式 |
| R452-W1-baserate | （非仲裁註記）`expect` 的值分佈 | — | 預測**非退化**（`meets_demand` 兩個值都出現 ≥5 次） | `evidence` | LCB2 是難題庫，OFF5 實測失敗率約半 |
| R452-§四.1 | 每題恰好 5 份候選 | 某題 ≠5 | **`UNRESOLVED`** | `guard` | `arm_off5` 結構上送 5 通；失敗通不落盤⇒理論上可 <5 |
| R452-§四.3型一 | 缺欄位 ⇒ BROKEN | 某列缺 `REQUIRED_ROW` 之一 | **`FORCED_GREEN`** | `guard` | runner 無條件寫這 6 個鍵 |
| R452-§四.3型二 | OFF5 有 rows 但 calls 找不到 ⇒ BROKEN | 某題找不到 | **`UNRESOLVED`** | `guard` | 鐵律 3 落盤，但非恆等式 |
| R452-E3 | 候選順序 == `involved` | 順序不符 | **`UNRESOLVED`** | `guard` | 兩處獨立記錄；`ts_ms` 是結束時刻⇒理論上可亂序 |
| R452-W2 | 規則 A 拒交率 2–14% | 落在窗外 | **`UNRESOLVED`** | `evidence` | 點估計在窗內、留一法擾動遠小於邊界距離 |
| R452-W3 | Δ(A−B) 落在 0..+12pp | 落在窗外 | **`UNRESOLVED`** | `evidence` | 同上 |
| R452-W4 | CI 旁必須有 MDE@n 與 N₈₀ | 這兩個鍵缺席 | **`FORCED_GREEN`** | `guard` | 尺無條件輸出這兩鍵 |

**這張表本身可能錯，錯了就是對帳表上的 MISS，照實記。**

## 四、量具要先有牙齒

1. **雙向校準**（記憶鐵律：只有正對照時「什麼都判 FORCED」也會全綠）：
   - 正對照＝已知恆假死碼（沿用 R454 的正對照）；
   - 負對照＝自由統計量（必須**不**被判成 FORCED_GREEN）。
   任一方向不對 ⇒ 判 `UNCALIBRATED`，不吐分類。
2. **恆等式一律用 `ast.get_source_segment` 逐字取出真運算式再窮舉 eval**，
   不准自己改寫一份；取不出來 ⇒ `SOURCE_DRIFT`，不是「證明成立」。
3. **一致性擋門的恆等式與 witness 必須同一個母體**（否則 CONTRADICTION 誤觸）。
4. **加法性**：本輪只**新增** `ops/gain/data/r455_census.json` 與一支新尺，
   **不改** `prereg_falsifiability_census.py` 既有 19 筆記錄的任何值。

## 五、推翻條件（觸發就照實寫，**不准當場補判準去修**）

1. 若量到 `R452-W1-baserate` **退化**（`expect` 只有單一值）⇒ 收官寫 W1 時
   **必須**同段寫「這個 100% 主要來自基準率」，且**不准**因此改 W1 的判決或窗口。
2. 若任何一條量出 witness>0 而我又寫得出恆等式 ⇒ `CONTRADICTION`，
   本輪不吐該條分類，照實寫進 STATE。
3. 若事前預測表對帳 MISS ≥ 4 條（9 條裡近半），⇒ 照實寫「我對這把尺的結構理解不足」，
   **不准**回頭改表讓它好看。
4. **本輪不對 r447 下任何收官判斷**；r447 未 terminal，收官仍歸 fable 稽核輪。

## 六、還沒被普查的是誰（**交棒必寫**，這是 R453 自己的盲點形狀）

本輪做完之後，收官仲裁者裡**仍未普查**的是：**R451**（§四 A/B/C ＋ §五 1–3）、
**R453 自己**、**R454 自己**。R452 §九 已由它自己做過一次自我普查（`forced_zero`）。
