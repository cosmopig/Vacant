# R494 判準：R486–R490 預註冊判準的可證偽性普查（結構半邊）

**寫在量測之前，單獨 commit。** 迴圈輪次 round766。作者：Opus 5。

## 〇、為什麼是這一輪、以及為什麼是這個切法

round763／764／765 **連三輪**在交棒裡具名保留「R486–R490 六份還沒被普查掃過」。
前兩次的偏離理由（r718 規則「問收官會引用誰」）本輪**不再成立**：

- 主 run `g_r461_lcb3_three_arm` 開場 rows=326／567（109/189 題），依 round765 實測
  0.48 列/分 ⇒ **收官約在 15:0x UTC，本輪不可能收官**。
- R492（收官合取項）與 R493（附錄散文）**已經把收官引用路徑掃完**。
  ⇒ 「收官會引用誰」這條理由本輪沒有剩下的標的。

⇒ 本輪執行交棒第 2 項。

### 切法：只做結構半邊，不換 loader

交棒寫「框架可重用，但資料是 8766 閘道快照 ⇒ 要換 loader 與判決函式」。
**本輪刻意不換 loader**，改成只問**結構可達性**：R486–R490 的五支工具，
判決全部集中在純函式（`decide` / `verdict_p*`），且每支的 docstring 都自陳
「所有輸入由呼叫端獨立設定」⇒ 可以完全不碰資料就窮舉它們的值域。

⚠ **這個切法的代價，事前寫死，收官不准含糊**：
本輪測的是 R491 詞彙裡的 **IDENTITY 半邊**（邏輯上可不可能為假），
**不是 EMPIRICAL 半邊**（這份閘道快照翻不翻得動）。
⇒ 本輪判 `EVALUABLE` 的條目**只准**讀成「結構上可證偽」，
**不准**讀成「當時那份資料有可能給出相反判決」。EMPIRICAL 半邊本輪 **未掃**，
下輪交棒要照寫「R486–R490 的 EMPIRICAL 半邊仍未掃」。

## 一、母體（掃什麼）

`ops/gain/` 底下五支工具的**判決函式**，以及 R486–R490 六份 PREREG 裡
**指名某個判決字串**的預測：

| 工具 | 判決函式 |
|---|---|
| `r486_longreq_attrib.py` | `VERDICT_KEYS` 對應的判決分支 |
| `r487_concurrency_tax.py` | `verdict_p1` / `verdict_p2` / `verdict_p3` |
| `r487_ts_semantics.py` | `decide` |
| `r488_pointwise_concurrency.py` | `decide` |
| `r489_permutation_placebo.py` | `decide` |
| `r490_leveled_placebo.py` | `decide` |

## 二、分類（不准事後加格）

對每個「判決函式 × 它宣告詞彙表裡的每個判決字串 V」：

- `REACHABLE`　　存在一組輸入使函式回傳 V（具名 witness，逐欄位印出來）
- `UNREACHABLE`　搜尋預算內到不了 ⇒ **死詞彙候選**

對每條「預測 P 指名判決 V_pred」：

- `FORCED_GREEN`　該函式**只有** V_pred 可達 ⇒ P 結構上不可能為假 ⇒ **收官不得當證據**
- `EVALUABLE`　　至少一個 ≠ V_pred 的判決可達
- `UNSCANNED`　　該預測沒有指名判決字串（例如純敘述型）

⚠ `FORCED_GREEN` ≠ 有缺陷（r718 規則）：先標 `intent`
（`evidence` ＝ 收官拿來當佐證，強制綠燈才要警告；`guard` ＝ 防 infra，強制綠燈是設計如此）。

## 三、雙向校準（跑真實函式之前，缺一不可）

- **正對照 `C_POS`**：合成常數函式（永遠回傳同一字串）⇒ 必須判 `FORCED_GREEN`。
- **負對照 `C_NEG`**：合成自由函式（判決由某輸入決定）⇒ 必須判 `EVALUABLE`。

任一方向不符 ⇒ 整份輸出判 `BROKEN`，不准報任何真結果。
（只有正對照時，「什麼都判 FORCED」也會全綠 ⇒ 兩個都要。）

## 四、擋門（先寫死）

1. **G-LIVE**：任何開檔路徑含 `g_r461_lcb3_three_arm` ⇒ `RuntimeError`。報告印 `live_reads`，必須為 0。
   （主 run 還在跑，P-R461-1/2/3 的盲測不得被破壞。）
2. **G-MUT**：突變體旗標一律在**被測函式內部**生效、且**呼叫時**才讀 env（不在 import 時讀）。
3. **G-SCAN**：`n_functions_scanned` 必須 == 6、`n_verdicts_scanned` >= 20，
   否則判 `UNSCANNED` 而**不是** `CENSUS_OK`（「安靜量不到」第三型：掃到 0 個目標）。
4. **G-VOCAB**：詞彙表用 `ast` 從被測檔原始碼取（`VERDICTS` 常數 ∪ 該函式所有 `return` 字串字面），
   **不准自己抄一份**。兩個來源的差集要具名印出來。

## 五、預測（先寫；每條標明「盲」到什麼程度，不准事後改標）

| # | 預測 | intent | 盲的程度 |
|---|---|---|---|
| P-1 | 至少 1 個判決字串判 `UNREACHABLE`（死詞彙存在） | evidence | **半盲**：我讀過 4 支的 `decide` 本體，但沒有窮舉過任何一支 |
| P-2 | R486–R490 的預測裡，`FORCED_GREEN` 的條數 **== 0** | evidence | **盲** |
| P-3 | `r487_ts_semantics.decide` 三個回傳值**全部可達** | evidence | 讀過原始碼，推理得出 ⇒ **不算盲** |
| P-4 | `r490` 的 `PRIMARY_IS_POSITIVE_CONTROL` **可達** | evidence | 讀過原始碼 ⇒ **不算盲** |
| P-5 | 聚合：`1 <= n_unreachable <= 6` | evidence | **盲** |
| P-6 | selftest 全綠、突變體全部照預註冊行為 | guard | **盲** |
| P-7 | `live_reads == 0` | guard | 設計如此（強制綠燈，**不是證據**） |

**自標「最可能錯的一條」：P-2。** 理由：這五支工具的擋門層層前置，
很可能有某支的某個預測其實只剩一個出口。事前標記，收官照實對。

## 六、事前寫下的推翻條件

1. `C_POS`／`C_NEG` 任一不符 ⇒ 全份 `BROKEN`，不報真結果。
2. `n_functions_scanned != 6` ⇒ `UNSCANNED`，不准寫成「掃過了」。
3. 若某個判決字串在**兩種**取法（`VERDICTS` 常數 vs `return` 字面）下不一致 ⇒
   具名印出差集，**不准安靜取聯集就算數**。
4. 若窮舉搜尋預算內到不了某個判決，**不准**直接寫「恆假死碼」——
   只准寫 `UNREACHABLE`（＝搜尋預算內到不了），並附搜尋規模。
   要升級成「恆等式／死碼」必須另外給窮舉證明。
5. 若本尺自己被自我匹配／`--json` 撞 stdout 這兩個 repo 已知坑絆倒 ⇒ 照實記，舊量保留。

## 七、中止準則

主 run 若在本輪內意外結束 ⇒ 立刻停掉本尺、改做收官（收官優先於普查）。

## 八、不做什麼

不改那五支被測工具任何一行；不起／不殺任何 run；不 `git add` 活著的 run 目錄；
不碰 `world/`／`design/`／`vacant_hm`；不對已收官的 r445／r446／r447 下新判斷；
不掃 EMPIRICAL 半邊（見 §〇）。

---

# 附錄 K：結果（round766，量測後追加；判準在 commit `8d64c82`，本節之後）

## K.1 主結果

```
verdict=CENSUS_OK  tools=6  fns=8  verdicts=51  unreachable=0  forced_green=0  live_reads=0
[舊量，非判定] 只靠隨機產生器時 unreachable=4；靠手工構造才找到的判決=4
calibration: {'C_POS': 'FORCED_GREEN', 'C_NEG': 'EVALUABLE'}
突變體 4/4 behaved as prereg'd
```

**R486–R490 的 12 條指名判決的預測，全部 `EVALUABLE`，`FORCED_GREEN` ＝ 0。**
＝ 這六份預註冊在**結構半邊**上沒有強制綠燈。（EMPIRICAL 半邊未掃，見 §〇。）

## K.2 🔴 本尺第一版量錯了，而且是**重犯 R491 的同一個 bug**——舊量保留

第一版只有隨機產生器，判 `r490_leveled_placebo.decide` 有 **4 條 `UNREACHABLE`**：
`CONCURRENCY_TAXES`／`SCALE_DEPENDENT_TAX`／`SPEEDUP_ANOMALY`／`TAXES_BELOW_MARGIN`。
其中 `SCALE_DEPENDENT_TAX` **正是 R490 自己 P-7 預測的最終判決** ⇒ 若照發，
會得出「R490 的頭條預測結構上不可能為真」這個**錯誤**結論。

照判準 §六.4 不准直接寫「恆假死碼」，先做**刻意構造反例**——四條全部一次就到達：

```
aim SCALE_DEPENDENT_TAX -> SCALE_DEPENDENT_TAX
aim CONCURRENCY_TAXES   -> CONCURRENCY_TAXES
aim TAXES_BELOW_MARGIN  -> TAXES_BELOW_MARGIN   (EQUIV_HI=1.15)
aim SPEEDUP_ANOMALY     -> SPEEDUP_ANOMALY
```

⇒ **`UNREACHABLE` 是我的產生器太窄造成的假象，不是被測檔的缺陷。**
memory 記著的 R491 教訓（「普查第一版把 4 條誤標 IDENTITY，被測檔自己的夾具卻造得出反例」）
**在本輪原封不動地重演，連條數都是 4**。⇒ 這不是意外，是**規則**：
**隨機抽樣抽不到 ≠ 到不了；任何 `UNREACHABLE` 報出來之前一律要先撐過刻意構造反例。**

處置：`constructive_hits()` 進入正式流程（新增可調參數 0 個），
舊量無條件保留成 `unreachable_sampling_only=4`，並釘承重牆
`M4_DROP_CONSTRUCTIVE` ⇒ 必須回到 4（實測 DETECTED）。

## K.3 誠實邊界（事後照實寫）

- **只做 IDENTITY 半邊**。判 `EVALUABLE` ＝「結構上可證偽」，
  **不是**「那份閘道快照有可能給出相反判決」。**EMPIRICAL 半邊仍未掃。**
- **`r486_longreq_attrib` 只掃到 4 個判決字串，且 `R486-P1`／`P1b`／`P2` 預測的那三個
  判決字串本尺沒有到達過**（`predicted_is_reachable=False`）。它們仍判 `EVALUABLE`
  ——因為有 4 個**別的**判決可達，證偽方向存在——但**本尺沒有證明那三條各自的預測值到得了**。
  r486 沒有純判決函式（判決在 `analyze_under` 裡逐行算），本輪用合成 rows 驅動，
  **沒有替它做 K.2 那樣的構造關** ⇒ **r486 的覆蓋是部分的**，下輪要補。
- 判準 §四 G-SCAN 寫 `n_functions_scanned == 6` 有歧義：§一 表格是 **6 列工具、共 8 個函式**。
  兩個數字都報（`tools=6 fns=8`），擋門照「工具數」套用。**這是判準自己的措辭缺陷，照實記。**
- `P-7 live_reads==0` 是 `guard` 且**設計上強制綠燈**（本尺不開主 run 的檔）⇒ **不是證據**。
  它有牙齒的證據是 selftest `C1_glive`：故意打主 run 路徑必須 `RuntimeError`。
- 沒改那六支被測工具任何一行；沒起／沒殺任何 run；沒 `git add` 活著的 run 目錄。

## K.4 預測帳（判準 §五，照實記）

| # | 預測 | intent | 結果 |
|---|---|---|---|
| P-1 | 至少 1 個判決字串 `UNREACHABLE` | evidence | ❌ **MISS**（第一版看似中，但那是 K.2 的量具假象；照修正後的量＝0） |
| P-2 | `FORCED_GREEN == 0` | evidence | ✅ **中**——而且這是我**自標「最可能錯的一條」** |
| P-3 | `r487_ts_semantics.decide` 三個回傳值全可達 | evidence | ✅ 中（reachable=3） |
| P-4 | `r490` 的 `PRIMARY_IS_POSITIVE_CONTROL` 可達 | evidence | ✅ 中 |
| P-5 | `1 <= n_unreachable <= 6` | evidence | ❌ **MISS**（＝0） |
| P-6 | selftest 全綠、突變體全部照預註冊行為 | guard | ✅ 中（4/4） |
| P-7 | `live_reads == 0` | guard | ✅ 中，但**強制綠燈、不是證據**（見 K.3） |

⚠ **P-1 與 P-5 不獨立**（同一件事：unreachable 的條數）⇒ 收官不得記成兩份獨立的失手。

## K.5 推翻條件對照

1. 校準雙向皆符（`C_POS=FORCED_GREEN`／`C_NEG=EVALUABLE`）⇒ 未觸發。
2. `n_tools_scanned=6` ⇒ 未觸發。
3. 詞彙表兩種取法的差集已具名輸出（`vocab_diffs`）⇒ 未觸發。
4. **觸發了**：四條 `UNREACHABLE` 沒撐過構造反例 ⇒ 照 §六.4 不寫「恆假死碼」，改記假象（K.2）。
5. **觸發了**：本尺被自己的產生器窄度絆倒 ⇒ 照實記、舊量保留（K.2）。

---

# 附錄 L：修正（同一輪內，round766 後半）——K.3 那個洞是**我的量具壞掉**，不只是覆蓋不足

K.3 老實寫了「r486 只掃到 4 個判決字串、三條預測值沒到達過」，但**沒有問為什麼**。
問了之後發現不是「產生器太窄」，是**兩個欄位漏掉，讓整份 r486 普查是空的**：

1. 被測檔 `analyze_under` 用 `o["id"] != r["id"]` 排除自己 ⇒ 我的合成 rows **沒有 `id`** ⇒ `KeyError`。
2. 被測檔開頭 `events_scanned == 0` 直接判 `BROKEN` ⇒ 我的產生器有一半機率給空 events。
3. 重載事件要 `machine == "1004"` ⇒ 我的合成 events **沒有 `machine`** ⇒ 永遠 0 筆在範圍內。

而 `reachable()` 裡的 `except Exception: continue` **把 (1) 整片吞掉**
⇒ 外觀與「這些判決到不了」**一模一樣**。r486 原本「可達 4 個」其實全是早退路徑
（`BROKEN`／`UNSCANNED`／`SERIAL_NO_QUEUE`／`CONCURRENT_OBSERVED`）。

⇒ **這是 memory 記的「安靜量不到」第四型：夾具造出被測檔吃不下的輸入，
例外被吞 ⇒ 長得跟「判決不可達」一樣。**

## L.1 處置

- 產生器補 `id`／`machine`，events 不再給空。
- **`reachable()` 開始計例外**，`exc_rate` 進報告，selftest 釘 `E6_exc_rate <= 0.50`。
  （新增可調參數 1 個：例外率上限。它是**擋門**不是判別量。）
- 補 r486 的構造關 8 組，承重牆 `E5_r486`：四條被預測的判決必須真的到得了。
- **語意修正**：`PREDICTIONS` 表把 R486-P1b 的預測值寫成 `FORCED_GREEN_FLAG`，
  但被測檔 `r486_longreq_attrib.py:150` 吐的字面是 `FORCED_GREEN`／`BASERATE_OK`，
  **從來沒有 `FORCED_GREEN_FLAG`**。理由是**語意**（逐字比對被測檔原始碼），不是結果數字；
  且**分類格兩版都是 `EVALUABLE`**，判決沒有因此改變。

## L.2 修正後

```
verdict=CENSUS_OK  tools=6  fns=8  verdicts=62  unreachable=0  forced_green=0  live_reads=0
[舊量，非判定] 只靠隨機產生器時 unreachable=4；靠手工構造才找到的判決=7
r486_longreq_attrib.analyze_under: reachable=15（修正前 4）
12 條預測全部 EVALUABLE，且 predicted_is_reachable 全部 True（修正前 4 條 False）
突變體 4/4 behaved as prereg'd；exc_rate 最高 0.0065
```

⇒ **K.1 的主結論（`FORCED_GREEN=0`）不變，但 K.3 的「r486 覆蓋是部分的」這句話作廢**
——它現在掃到 15 個判決字串，四條被預測的判決都有具名 witness。
**K.3 那段原文無條件保留**（它是當時的誠實邊界，也是找到 L 節這個 bug 的線索）。

## L.3 通則（值得記進 memory）

**夾具／產生器造出被測檔吃不下的輸入時，`except: continue` 會讓它安靜地長得跟
「這個判決結構上到不了」一模一樣。** ⇒ 任何「窮舉／抽樣找不到」的宣稱，
除了要撐過刻意構造反例（K.2），還要**同時報例外率**；例外率沒報 = 這個宣稱沒被驗過。
