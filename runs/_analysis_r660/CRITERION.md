# round660 判準（**寫在量測之前**；先 commit 才開始量）

## 問題

round658 把磁碟上的 ON/OFF5 配對資料合併，區間從 UNINFORMATIVE 收窄到
`NON_INFERIOR_BUT_UNRESOLVED`（`[−4.48, +6.73]`pp，N=250），交棒寫「還差約 65 配對題」。

但 round658 只納入 2 個 run，把另外 4 個排除，理由寫成一條：**量具必須是 r393 修好之後的尺**。
磁碟上那 4 個被排除的 run 合計 **593 配對題**——是已納入資料的 2.4 倍，且**早就落盤**。

本輪的問題：**那 4 個被排除的 run，能不能在零 API 之下、以「明確標示方向的保守界」納進頭條？**

round658 自己寫了「被排除的四個 run 不是免費的統計功力，免得下一輪又去撿」。
**本輪不是去撿**：本輪要先把「為什麼不能直接撿」講清楚（下面 §二發現排除理由其實有兩條，
round658 只寫了一條），再問「在什麼受限的方向上它們仍然有效」。

## 一、先報一個 round658 工具的缺陷（本輪要修，且要有牙齒的測試）

`ops/gain/replay/pooled_paired_ci.py::main()` 現行行為：

```python
p_het = fisher_exact_2x2(...) if len(strata) == 2 else None
...
het = "HETEROGENEOUS" if (p_het is not None and p_het < HET_ALPHA) else "HOMOGENEOUS_NOT_REJECTED"
"pooled_usable_as_headline": het != "HETEROGENEOUS",
```

⇒ **層數 ≠ 2 時異質性擋門會安靜失效**：`p_het=None` ⇒ 判 `HOMOGENEOUS_NOT_REJECTED`
⇒ `pooled_usable_as_headline=True`。**六層直接餵進去會拿到「可以當頭條」，而擋門根本沒跑。**

這正是記憶條目寫死的那型：**判一把尺有沒有牙齒要看擋門的鍵，不是看工具存不存在。**

**修法（新增估計量零、新增可調參數零）**：層必須帶 `group` 標籤，Fisher 2×2 跑在
**兩個 group 的加總 (B,C)** 上——與 round658 完全同一個 `fisher_exact_2x2`、同一個 `HET_ALPHA=0.05`。
group 數 ≠ 2 且層數 > 2 ⇒ **判 BROKEN，不准安靜放行**。

**植入缺陷測試（不過就不准報數字）**：
- **P5**：六層、兩 group、兩 group 方向完全相反（`[[20,0],[0,20]]` 型）⇒
  必須 `het_verdict=HETEROGENEOUS` 且 `pooled_usable_as_headline=False`。
- **P6（安靜失效那一型）**：把擋門改回 round658 的 `if len(strata)==2 else None`（突變體 **M5**）
  ⇒ **P5 必須破**。M5 沒讓 P5 破 ⇒ 測試沒牙齒 ⇒ BROKEN。
- **P7**：層沒帶 `group`、或 group 數 ≠2 而層數 >2 ⇒ 必須進 `broken_reasons`（rc≠0）。

## 二、排除理由其實有兩條——round658 只寫了一條

| run | 起跑 | 尺 | worker 池 |
|---|---|---|---|
| `g_onoff5_qwenonly_v3_20260824` | 08-24 | PRE | qwen 單一 |
| `g_onoff5_371_r123_20260825` | 08-25 | PRE | qwen 單一 |
| `g_het3_r278_20260829` | 08-29 | PRE | qwen+gemma 混合 |
| `g_r356_3arm_20260830` | 08-30 | PRE | qwen+gemma 混合 |
| `g_r441_gemma_only_mbpp_b`（E1） | 09-02 | POST | **gemma 單一** |
| `g_r443_gemma_lcb`（E3） | 09-03 | POST | **gemma 單一** |

⇒ 被排除的 4 個**同時**是「舊尺」與「不同的 worker 池」。**池不同是實驗條件不同，不是雜訊**，
單靠離線重放修尺**修不掉**。round658 的納入規則只寫了尺，沒寫池；
若下一輪照它字面去「重放修尺就能撿回來」，會撿到一個**池被偷換過**的合併值。
**這一條要寫進交棒。**

## 三、本輪主張的受限用法：**只在單一方向上有效的保守界**

**A1（事前聲明的假設，非本輪發現）**：r393 的白名單 bug **對 ON 的懲罰大於 OFF5**。
- 機制（R393）：ON 只有 initial+revision 兩次機會，同一漏洞命中率遠高於 OFF5 的 5 樣本多數決。
- 量測（R430，`g_r356` 一個 run）：修正後 ON `flip_to_true=8`；OFF5 `flip_to_true=6, flip_to_false=2`（淨 +4）。

⇒ **未修正的 Δ（=ON−OFF5）低估真值**：`Δ_uncorrected ≤ Δ_corrected`。

**方向的不對稱（本輪的核心，不准對稱地用）**：

| 用法 | 有效嗎 | 為什麼 |
|---|---|---|
| 下界 `L`：主張 `Δ_corrected ≥ L`（**非劣性**） | ✔ **有效** | 低估的界仍是界 |
| 上界 `U`：主張 `Δ_corrected ≤ U`（`RULED_OUT`／「ON 打不贏」） | ✘ **無效** | 真值可能比 U 更高 |

⇒ **Group B 只能用來加固「ON 沒有實務劣化」這一側，不能用來說「ON 打不贏 OFF5」。**
頭條若要寫「打不贏」，**只能引用 Group A（gemma、POST 尺）**。

**A1 的推翻條件（事前寫死）**：日後任何一次對這 4 個 run 的離線重放，若 OFF5 的淨增益
≥ ON 的淨增益，A1 作廢，本輪 Group B 的保守界標籤一併作廢。

## 四、分層與分組（**與結果無關，先訂**）

- **Group A** = `S1`=E1(`g_r441_gemma_only_mbpp_b`, MBPP+)、`S2`=E3(`g_r443_gemma_lcb`, LCB 快照)
- **Group B** = `S3`=`g_onoff5_qwenonly_v3_20260824`、`S4`=`g_onoff5_371_r123_20260825`、
  `S5`=`g_het3_r278_20260829`、`S6`=`g_r356_3arm_20260830`

主指標、`meets_demand` 的取法、合併的加法恆等式、`diff_ci`：**全部沿用 round658，不重訂**。

## 五、判定表（沿用 round656／658 的 ±5pp 表，不重訂），單位 pp

| 條件 | 判定 |
|---|---|
| L > 0 | `ON_WINS` |
| U ≤ +5.0 | `RULED_OUT` |
| U > +5.0 且 L < −5.0 | `UNINFORMATIVE` |
| U > +5.0 且 L ≥ −5.0 | `NON_INFERIOR_BUT_UNRESOLVED` |

**加一條本輪限定的讀法**：Group B 與全體合併的 `RULED_OUT` 判定**一律不得當頭條**（§三），
只有 `L` 可以引用。無論判哪一格，原始 `[L,U]` 照登。

## 六、事前預測（量之前寫死）

- **P-R660-1**：現行工具餵 6 層會回 `p_het=None` 且 `pooled_usable_as_headline=true`（缺陷成立）。
- **P-R660-2**：Group B 單獨的 N≈593，超過 round656 算的 ≈538 ⇒ Group B 的半寬會 <±5pp。
- **P-R660-3**：A 與 B 兩 group 的 `p_het ≥ 0.05`（弱預測；池不同，我不確定，照實登）。
- **P-R660-4**：Group B 的 `L ≥ −5.0`pp（即保守界支持非劣性）。**這是本輪對頭條唯一的新主張。**

**預期會多冒出一類**：某些層 b=c（方向 0）或層間方向相反。冒出來就**照實寫、人眼確認、
不算進判定、不當場補判準**。

## 七、BROKEN（事前寫死的推翻條件）

1. 任一自檢條（P1–P7）沒過，或 M3/M4/M5 沒被**事前指定的那一條**抓到。
2. E3 是活的 run ⇒ 先快照到 `/dev/shm/r660` 再量，量前量後 sha 逐字元相同，不同就 BROKEN。
3. 任一層出現缺 `meets_demand` 的第三類 ⇒ 照實列出，不補判準。
4. 任一層的 `n` 與本判準 §四所列的規模量級不符（差一個數量級）⇒ 先查是不是選錯 arm。
