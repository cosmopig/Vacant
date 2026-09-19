# R466：對 **R461 §二／§六**（R462 沒掃到的那半）做可證偽性普查

round734（2026-09-04 UTC 21:1x）。主 run `runs/g_r461_lcb3_three_arm` 仍在跑（PID 2895311），
本輪**零 API、零偷看**：不讀主 run 的任何一列。

## 〇、合法性前提（為什麼這輪做這件事）

R462（`1c6452c`）只掃了 R461 的 **§三／§四** 七筆。memory 鐵律：
**「可證偽性普查自己的涵蓋範圍就是盲點」**——r718 就是補掃 R450 當場抓到兩條強制綠燈。
R461 的收官會引用的不只 §三／§四：

- **§六**是量具效度**唯一**的替代證據（§六.3 事前承認 v3 probe 覆蓋率 0/189
  ⇒「參考解全過」照字面不可執行）。
- **§二**的三條 bank 構造預測在**附錄 A.4 被記成 3 HIT／1 MISS**，
  那張表是 R461 預測帳的一部分，收官會引用它的命中率。

**§二／§六 從來沒被任何普查掃過。** 這是本輪要補的洞。

## 一、範圍（**只掃這七筆，不准事後加減**）

| # | 出處 | 內文（逐字要在 R461 找得到） | intent |
|---|---|---|---|
| S2-1 | §二 事前預測 1 | 產出 **恰好 189 題** | evidence |
| S2-2 | §二 事前預測 2 | 189 個 `task_id` 與 v2 的 120 個**零交集** | evidence |
| S2-3 | §二 事前預測 3 | 日期範圍 2023-05-07 → 2024-08-10 | evidence |
| S2-4 | §二 事前預測 1 的分項（A.4 表第 4 列） | medium 152／hard 37 | evidence |
| S6-1 | §六 | **v3 的 probe 覆蓋率預期為 0/189** | evidence |
| S6-2 | §六.2 | 能力下界：有幾題**任一臂通過過一次** | evidence |
| S6-3 | §六.3 | 覆蓋率 0 讓 SPEC 規則不能照字面執行就**照實寫成偏離** | guard |

`intent` 照 r718 規則先標：**evidence＝收官拿來當佐證，強制綠燈才要警告；
guard＝防 infra，強制綠燈是設計如此。**

## 二、分類（四格，**本節寫在量測之前**）

沿用 R453／R462 的三格，**外加一格**（預先宣告，不是事後加）：

- `EVALUABLE`    證偽事件在同一母體裡可能發生（或候選恆等式被反例推翻）⇒ HIT 帶資訊
- `FORCED_GREEN` 寫得出恆等式 **且** 同母體 witness＝0 ⇒ HIT 不帶資訊
- `UNRESOLVED`   兩者皆無 ⇒ 照實寫判不出來
- `NOT_A_PREDICTION` （**新格**）該筆是報告義務／程序規定，本身沒有真值
  ⇒ 不進命中率、也不算強制綠燈

### 二.1 判 forced 的時點是**預測當時**，不是今天

`LCB_BANKS["v3"]` 現在釘死了 sha256 與 count＝189，載入器 count 不符就 raise
⇒ **今天**「v3 恰好 189 題」是恆真的。但那個釘值是**觀測之後**才寫進去的。
**本普查一律以「預測落筆當時的倉庫狀態」判 forced**，並在輸出裡把兩個時點都印出來
（`forced_at_prediction_time` 與 `forced_today`）。兩者不同時，仲裁者是前者。

### 二.2 恆等式與 witness 必須同一個母體（r718 規則）

每一筆要寫出母體定義。例：S6-1 的母體是
**「由與 v2 不相交的來源視窗建出的 bank，用 `verify_lcb_bank` 量 probe 覆蓋率」**，
witness＝該母體中覆蓋率 > 0 的 bank。拿 v1（來源含 probe 那 12 題）當 witness 是**跨母體**，不算。

## 三、事前預測（**盲／確認要標清楚，確認項不計盲測命中率**）

| # | 事前預測的分類 | 盲？ |
|---|---|---|
| S2-1 | `EVALUABLE`（預測當時沒有任何東西保證 189；§二 自己寫「不是 189 就停下來查」＝證偽事件有名字） | 盲 |
| S2-2 | `FORCED_GREEN`（v3 的來源視窗 test/test2/test3 與 v2 的來源不相交 ⇒ 建不出交集） | 盲 |
| S2-3 | `EVALUABLE`（日期是資料自由統計量） | 盲 |
| S2-4 | `EVALUABLE`（**負對照**：它事後被判 MISS，一個被推翻的預測**必然**可證偽；
  普查若把它判成 FORCED 就是「什麼都判 FORCED」） | 盲 |
| S6-1 | `FORCED_GREEN`，且比 S2-2 更硬 | **確認**（落筆前已讀 `verify_lcb_bank.py:36,160`） |
| S6-2 | `EVALUABLE`（r447 上 demonstrated 94／undemonstrated 26，兩個方向都出現過） | **確認**（落筆前已讀 R461 附錄 E.4 Y2） |
| S6-3 | `NOT_A_PREDICTION` | 盲 |

**盲測５筆**（S2-1／S2-2／S2-3／S2-4／S6-3），確認２筆（S6-1／S6-2）。

### 三.1 S6-1 的確認式主張（落筆前已知，照實標）

`ops/gain/verify_lcb_bank.py:36` 的 `PROBE_PATH` **寫死** `data/lcb_probe_solutions.json`，
:160 的 `probe_coverage` 就是拿它算的，**不隨 `--version` 改**。
⇒ 主張：**即使 round728 已經造出 `data/lcb_v3_probe_solutions.json`，
`verify_lcb_bank --version v3` 的 `probe_coverage` 仍然是 `0/189`。**
若成立，這是「旗標／路徑預設值是舊語意」型缺陷（memory 同型：`--key` 預設 `meets_demand`），
且它讓 §六 那條預測**在任何情況下都不可能為假**。

## 四、擋門（判準是 verdict 字串，不是 rc≠0）

- **B1** 恆等式成立 **且** 同母體 witness>0 ⇒ `CONTRADICTION`（優先於本檔任何主張）
- **B2** 被引用的原始碼運算式／字面與釘死的不符 ⇒ `SOURCE_DRIFT`（不是「證明成立」）
- **B3** **不准讀主 run**：任何讀檔路徑含 `g_r461_lcb3_three_arm` ⇒ `BROKEN_PEEKED`
- **B4** bank 檔缺失／sha 不符 ⇒ `UNCALIBRATED`，不吐任何分類
- **B5** **雙向校準**任一方向失敗 ⇒ `UNCALIBRATED`，不吐任何分類：
  - 正對照（已知強制綠燈）：「載入成功的 v3 恰有 `LCB_BANK_V3_COUNT` 列」必須判 `FORCED_GREEN`
  - 負對照（自由統計量）：「v3 的 medium 題數＝135」必須判 `EVALUABLE`
  只有正對照時「什麼都判 FORCED」也會全綠（memory 鐵律）。
- **B6** `CONTRADICTION`／`SOURCE_DRIFT`／`UNCALIBRATED` 之下不准吐任何 `FORCED_GREEN`

## 五、推翻條件（觸發了照實寫，**不准當場補判準去修**）

1. 任一盲測分類與實測不同 ⇒ 記 **MISS**，不改本節。
2. 冒出第五類（四格都不合身）⇒ **照實寫、人眼確認、不算進命中率、不當場補判準**。
3. S6-1 的確認式主張若不成立（覆蓋率不是 0/189）⇒ 三.1 整段記 **REFUTED**，
   且 §六 那條預測改判 `EVALUABLE`。
4. 本輪**不修** `verify_lcb_bank.py`——即使 S6-1 成立。修量具要另開判準，
   而且 R461 的 v3 已經發射，**改量具不會改變 R461 已發生的事**。

## 六、本輪明確不做

不讀主 run 任何一列、不起任何 run、不 `git add` 主 run 目錄、不改 `verify_lcb_bank.py`、
不改 `r447_gauge_capability.py`、不改 R461 §三／§四／附錄 A–E 的正文、
不動任何門檻／窗口／MDE／α／n／seed／worker／端點／bank、不碰展件。

**量測結果另一個 commit。** 本檔在量測之前 commit。
