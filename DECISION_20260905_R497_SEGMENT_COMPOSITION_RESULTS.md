# R497 結果：閘道快照前段/後段的組成軸篩除普查

判準：`DECISION_20260905_R497_SEGMENT_COMPOSITION_PREREG.md`（commit `626d300`，量測之前單獨 commit）。
量具：`ops/gain/r497_segment_composition.py`（selftest 22/22）、`ops/gain/r497_mutation_check.py`。
資料：`ops/gain/data/r497_segment_composition.json`。零 API、只讀落盤快照。

## 一 頭條

```
verdict=EXO_AXES_TRACK  n_windows=12  exo=11 endo=3  exc=0  live_reads=0  elapsed_s=0.1
calibration: {'C_POS': 'POSITION_TRACKING', 'C_NEG': 'NOT_TRACKING'}
exo_tracking:     ['share_chat', 'share_model_gemma', 'share_model_null', 'share_other_client']
exo_not_tracking: ['events_in_window', 'mean_prompt_tokens', 'share_error', 'share_status_non200']
endo_tracking:    []
```

| 統計量 | 類 | 分類 | rho(N=1672) | rho(N=2291) |
|---|---|---|---|---|
| `share_chat` | EXO | **POSITION_TRACKING** | −0.9856 | −1.0 |
| `share_other_client` | EXO | **POSITION_TRACKING** | −0.9856 | −1.0 |
| `share_model_gemma` | EXO | **POSITION_TRACKING** | −0.9856 | −1.0 |
| `share_model_null` | EXO | **POSITION_TRACKING** | +0.9856 | +1.0 |
| `events_in_window` | EXO | NOT_TRACKING | −0.8827 | −0.9258 |
| `share_error` | EXO | NOT_TRACKING | +0.4414 | +0.7945 |
| `share_status_non200` | EXO | NOT_TRACKING | +0.4414 | +0.7945 |
| `mean_prompt_tokens` | EXO | NOT_TRACKING | −0.7714 | +0.9429 |
| `n_distinct_client_ip` | EXO | STAT_DEGENERATE（12 個視窗恆為 3） | — | — |
| `share_machine_1004` | EXO | STAT_DEGENERATE（恆為 1.0） | — | — |
| `share_stream` | EXO | STAT_DEGENERATE（恆為 0.0） | — | — |
| `median_latency_ms` | ENDO | NOT_TRACKING | −0.169 | −0.9258 |
| `mean_completion_tokens` | ENDO | NOT_TRACKING | +0.2571 | +0.4857 |
| `median_ms_per_tok` | ENDO | NOT_TRACKING | +0.7714 | +0.2571 |
| `C_POS` | 校準 | POSITION_TRACKING | +1.0 | +1.0 |
| `C_NEG` | 校準 | NOT_TRACKING | −0.4286 | −0.3143 |

## 二 那四條「跟著位置動」的軸其實是**同一條**

值逐格幾乎重合，`share_model_null` 是另外三條的鏡像：

```
share_chat          0.3122 0.3062 0.2990 0.2972 0.2972 0.2416 | 0.2964 0.2911 0.2903 0.2898 0.2763 0.2623
share_other_client  0.3152 0.3092 0.3020 0.3002 0.3002 0.2452 | 0.2994 0.2942 0.2933 0.2929 0.2794 0.2654
share_model_gemma   0.2972 0.2913 0.2841 0.2823 0.2823 0.2237 | 0.2811 0.2759 0.2750 0.2746 0.2610 0.2471
share_model_null    0.6878 0.6938 0.7010 0.7028 0.7028 0.7584 | 0.7036 0.7089 0.7097 0.7102 0.7237 0.7377
```

⇒ **具名 4 條，資訊只有 1 條**：快照裡 chat 請求的佔比從約 31% 單調降到約 24%，
GET 輪詢（`model is None`）的佔比等量上升。「別的 client」與「gemma 模型」都是
同一件事的別名（發 chat 的就是那個 client、打的就是 gemma）。
⛔ **收官不准把它寫成四份獨立證據**（同 R492「合取項互相 FORCED_BY_OTHERS」那一課）。

## 三 🔴 主要發現：R496 的「等 n」等錯了單位

`r489_permutation_placebo.analyse` 第 251–253 行只吃 `is_chat(r)` 的列，
再取 `is_analysable(r)` 的子集，而**判準 §二 的三條 ENDOGENOUS 是在全部 2899 列上算的**
——其中約七成是 GET 輪詢（`median_latency_ms` ≈ 4.9 ms 就是輪詢的中位數，不是 chat 的）。
⇒ **母體不符**（memory：母體保真要用被測檔自己的過濾器）。這是本尺自己的缺陷，照實記。

用 R489 自己的過濾器重算（`ops/gain/r497_posthoc_chatonly.py`，**事後、不改頭條**）：

```
全部列=2899  is_chat=786  is_analysable(chat 內)=728

母體 = chat+analysable
  median_latency_ms       NOT_TRACKING       rho={1672: 0.4857, 2291: 0.2}
  mean_completion_tokens  NOT_TRACKING       rho={1672: 0.2571, 2291: 0.4857}
  median_ms_per_tok       NOT_TRACKING       rho={1672: 0.7714, 2291: 0.2571}
  n_chat                  POSITION_TRACKING  rho={1672: -1.0,   2291: -1.0}
    values=[491, 482, 468, 467, 466, 364 | 636, 624, 623, 620, 587, 555]
```

🔴 **R496 固定的是「閘道總列數」，不是「被分析的列數」。**
在總列數固定的視窗裡，**被 R489／R490 真正分析的 chat 列數仍隨起始位置單調下降**
（N=1672 層 491 → 364，−26%；N=2291 層 636 → 555，−13%），rho 兩層都是 **−1.0**。
而 `r489.decide` 與 `r490.decide` 有多道擋門直接比 `n_hi`／`n_lo` 與 `MIN_PER_ARM`
（`r489:193, 211, 253, 512, 517`；`r490:222, 251`）⇒ 分析樣本數就是判決的直接輸入。

⇒ **R496 的結論「翻動不是樣本量造成的」在被分析的單位上沒有被證明。**
⛔ 但**同樣不准反過來寫成「翻動是樣本量造成的」**：本快照裡
「視窗位置」與「被分析的 chat 列數」的 rho ＝ −1.0，**完全共線 ⇒ 本尺一樣分不開**。
唯一能分開的做法是造**等 chat 列數**的視窗（而非等總列數），那要先寫判準再量（見 §七）。

## 四 這把尺的力氣在否定方向（判準三.1 原樣抄回）

k=6 時 `|rho|>=0.9` ⇔ Σd² ∈ {0,2} ⇒ 隨機排列虛無下兩層同號約 `1.4e-4`。
⛔ **這不是 p 值**：12 個視窗高度重疊、統計量高度自相關，真實的偶然單調機率遠高於此，
本尺沒有量它。⇒ 判 `NOT_TRACKING` 的軸可以被**排除**（不可能解釋兩層都近乎單調的翻動）；
判 `POSITION_TRACKING` 只是**進入候選名單**，不是原因。所有隨時間單調變動的東西彼此混淆。

**被排除掉的**（本輪的實質產出）：模型 load/unload 事件、輸入大小、錯誤率、非 200 率。
其中 `events_in_window`（−0.8827／−0.9258）**是擦邊沒過**，兩層都在 0.88–0.93 之間
⇒ 「排除」的強度只有「沒到本判準的門檻」，**不要寫成「和事件完全無關」**。

## 五 預測帳（判準 §六）

| 代號 | 預測 | 結果 |
|---|---|---|
| `P-1` | 頭條 ＝ `EXO_AXES_TRACK` | **HIT** |
| `P-2` | `share_other_client` 是 POSITION_TRACKING（**自標最可能錯**） | **HIT** |
| `P-3` | `events_in_window` 不是 POSITION_TRACKING | **HIT**（但擦邊，見 §四） |
| `P-4` | ≥1 條 ENDOGENOUS 是 POSITION_TRACKING（自評「高」信心） | **MISS** |
| `P-5` | `C_POS` TRACKING、`C_NEG` 不 TRACKING | 成立，但 **guard／校準，不是證據** |
| `P-6` | UNSCANNED＋DEGENERATE ≤ 2 | **MISS**（3 條 DEGENERATE） |
| `P-7` | NOT_TRACKING 的外生軸 ≥ 4 | **HIT**（恰 4，壓線） |

🔴 **自評最有信心的 `P-4` 錯了，自標最可能錯的 `P-2` 對了。**
且 `P-4` 的 MISS **有一半是我自己的量具母體錯**（§三）——換成正確母體後
三條 ENDOGENOUS 仍全部 NOT_TRACKING，所以**結論方向不變**，但
「事前理由」與「事後理由」不是同一回事，兩者都記。
`P-6` 的 MISS 是三條**真的常數**（單機、無 stream、恆 3 個 client）⇒ 是快照的性質，
不是量具壞掉；`STAT_DEGENERATE` 這一格的存在正是為了不把它們安靜記成「無訊號」。

## 六 承重牆／突變體：**3/4，M3 沒被看見**

```
DETECTED  M1_ONE_WINDOW      verdict==BROKEN_WINDOWS            實際 BROKEN_WINDOWS
DETECTED  M2_CNEG_TIME       BROKEN_CALIBRATION + C_NEG TRACK   實際 兩者皆是
MISSED    M3_RHO_ONE_TIER    exo_tracking 清單必須改變          實際 逐字相同
DETECTED  M4_SWALLOW_NULL    擋門關掉後分類必須改掉             實際 UNSCANNED -> DEGENERATE
```

- **`M3` MISSED 是結構＋資料兩層原因，照實記，不改判準**：
  「只看第一層」的判準是「兩層同號」的**放寬**版 ⇒ 突變只可能**加**名字，不可能減。
  這份資料上它一個都沒加 ⇒ **本快照裡「兩層同號」這道加嚴一條都沒篩掉**。
  ⇒ 那道加嚴在真資料上**沒有承重**；它有牙齒的證據在 selftest 的
  `C3_opposite_sign`／`C3_one_tier_only`／`C4_edge_out`（合成夾具看得見）。
  ⇒ **下輪引用本尺時，「兩層都單調」不是額外的一份證據**（同 §二 那一課）。
- **`M4` 的實際標籤與判準預測不同，照實記，不追認**：判準 §五 預測 guard 關掉後會掉成
  `NOT_TRACKING`，實際掉成 `STAT_DEGENERATE`——因為後面還有一道「12 個視窗零變異」的
  擋門先接住它。⇒ `field_all_null` 這道擋門**只對 share 型統計量承重**
  （把 DEGENERATE 升級成語意更準的 UNSCANNED）；對 mean/median 型它不改變結果。
  突變仍**可見**（分類確實改了），但「該變成哪個字」我事前寫錯了。
- **selftest 自己抓到一次我寫錯的課本值**：`C2_rho_sigd2_4_below` 第一版witness 用
  `[1,2,3,5,4,6]`，那是 Σd²=2 不是 4 ⇒ 修的是**測試**不是**工具**（memory：
  自己現寫的統計小工具要先對課本值自檢）。

## 七 誠實邊界與下一步

1. **本尺不建立因果。** 只做篩除。四條 TRACKING 軸＝一條軸＝「chat 佔比單調下降」。
2. **§三 是本輪最重要的一條，而且它同時削弱 R496 與本尺自己**：
   引用 R496「翻動不是樣本量造成的」從今天起必須連寫
   「那個 n 是閘道總列數，被分析的 chat 列數在同一批視窗裡仍是 rho=−1.0 單調下降」。
   ⛔ 不准反向讀成「R496 錯了／翻動就是樣本量」——共線，本快照分不開。
3. **下一步（要先寫判準再量）**：造**等 chat 列數**的滑動視窗（讓 `n_subset` 固定，
   讓總列數浮動），重跑 R495 的 `probe_r489`／`probe_r490`。
   那是目前唯一能把「位置」與「被分析樣本數」拆開的設計。
   ⚠ 事前要問一句：等 chat 列數之後，**時間跨度**會不會失控（R496 那次跨度只差 ±5%，
   這次不保證）——跨度也要當一條待判量報出來。
4. **仍未做**：R495／R496 的承重牆刪除測試（round767 交棒第 4 項，本輪也沒做）。
   本輪只對 R497 自己做了具名突變體，且其中一個 MISSED。
