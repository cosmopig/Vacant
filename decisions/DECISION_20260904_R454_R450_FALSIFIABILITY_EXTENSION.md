# R454：把可證偽性普查延伸到 R450——收官輪的仲裁者不只 R440Z

（2026-09-04 round718，Opus 5。`runs/g_r447_conform_lcb2` **仍在跑**（本文件寫定時
rows=294/360，`pace_probe` ETA ~15:45 UTC）。本文件在**改任何一行程式碼之前**寫定，
量完不准改分類規則、不准改預測表。本輪**不是**收官輪、**不改** R440Z／R450 任何條文、
**不改**任何 P-Z 的判決。）

## 一、為什麼現在做（round718 開場查到的具體缺口）

round715 的 R453 對 **R440Z** 的 12 條預註冊判準做了可證偽性普查，抓到 4 條結構強制
綠燈（含 round714 誤寫成 HIT 的 P-Z5b）。但收官輪的仲裁者**不只 R440Z**——
R451 §六 與歷輪 STATE 都寫著：

> 收官輪的仲裁者：R440Z §三／§六 ＋ **R450 §四** ＋ R451 ＋ R452（含 §九）＋ R453

`prereg_falsifiability_census.py` 的 `WINDOWS` 只有 `P-Z1/P-Z2b/P-Z3/P-Z4/P-Z5a`，
**R450 的條文一條都沒進去**。也就是說：R453 證明了「空綠燈要成群抓」，然後只抓了一群。

開場逐字讀 `ops/gain/r447_gauge_capability.py` 之後，具體懷疑對象是 R450 §三 的
**真資料對照**（第 119–137 行）：

```python
full = _mcnemar_bc(by_arm[x], by_arm[y], set())
excl = _mcnemar_bc(by_arm[x], by_arm[y], skip)      # skip = undemonstrated
if full[:2] != excl[:2]:
    mismatch.append(f"{x}_vs_{y}")
```

R450 §三 說這個對照「兩者必須逐數相同；**不同就是 BROKEN**」，§六-2 又說
「若對照不相同，§三 那句結構性結論**立即作廢**」。**如果這個對照結構上不可能不同，
那條推翻條件就永遠不會觸發，而收官輪會把「已在真資料上對照過、逐數相同」
當成 §三 的獨立佐證來引用——那是循環論證。** 這正是 R453 在 P-Z5b 上抓到的形狀。

**空綠燈只有在收官之前抓才有用。** r447 距 terminal 還有約 1.7 小時，現在做完得及。

## 二、量什麼（分類規則，**沿用 R453 §二，不新增格子、不新增旋鈕**）

| 類別 | 條件 | 收官該怎麼寫 |
|---|---|---|
| `FORCED_GREEN` | 寫得出恆等式 **且** witness＝0 | HIT 不帶資訊；要附恆等式與基準率 |
| `EVALUABLE` | witness ≥ 1 | 照常寫，HIT 帶資訊 |
| `UNRESOLVED` | 兩者皆無 | 照實寫「判不出來」，不准往任一邊倒 |

擋門 B1–B5 一併沿用（witness>0 ∧ 恆等式 ⇒ `CONTRADICTION`；B5 時不吐 FORCED_GREEN）。

⚠ **`FORCED_GREEN` 不等於「這條判準有缺陷」。** 一條「run 剛起步時別吐空洞綠燈」的
啟動擋門，在一個已經有 294 列的 run 上本來就不可能觸發——那是設計如此，不是缺陷。
**能不能拿來當結論的佐證，才是收官輪在意的事。** 故每一條**在量測之前**先標一個
`intent` 欄位（下表最右欄），只有 `evidence` 那些會影響收官文字：

- `evidence`：收官輪會拿它當某個結論的佐證 ⇒ FORCED_GREEN 就是要警告的對象。
- `guard`：只是防 infra／防半殘資料 ⇒ FORCED_GREEN 是正常的，照實記、不當缺陷。

`intent` 是**事前判斷**，寫在這裡，不准量完再改。

## 三、事前預測（本輪的主張，量完照實對帳；**錯了不准回頭改這張表**）

| # | R450 子句 | 證偽事件 | 預測類別 | `intent` | 根據 |
|---|---|---|---|---|---|
| R450-§三-bc | 排除 undemonstrated 後 b/c 與全量逐數相同 | 某一對臂的 b 或 c 改變 | **`FORCED_GREEN`** | `evidence` | §四 的恆等式 |
| R450-§六-2 | 「若對照不相同 ⇒ §三 作廢」 | 同上（同一事件） | **`FORCED_GREEN`** | `evidence` | 是 §三-bc 的同一事件，不是獨立證據 |
| R450-§六-1 | undemonstrated ≤ 50%（超過就質疑窗口） | 佔比 > 50% | `EVALUABLE` | `evidence` | 自由統計量；但要附「離邊界／留一擾動」比值 |
| R450-§五-2 | 三臂齊的題數 > 0 | 題數＝0 | `FORCED_GREEN` | **`guard`** | run 已有 294 列 ⇒ 啟動擋門在此不可能觸發 |
| R450-§四 | 區間 `[pz1_demonstrated_only, pz1_raw]` 整段落在 40–60 | 區間跨出窗口 | `EVALUABLE` | `evidence` | 兩端都是自由統計量 |

## 四、R450-§三-bc 的恆等式（證明寫在量測之前）

設 `U`＝undemonstrated 題集，定義（`r447_gauge_capability.census`，逐字）：

- `demonstrated` ＝ 存在某臂 `meets_demand` 為真的題；`U = complete − demonstrated`。
- `_deliv(r) ≡ bool(r["accepted"]) and bool(r["meets_demand"])`（R667 凍結口徑）。
- `_mcnemar_bc` 只數**不一致對**：`b = #{t : A[t] ∧ ¬B[t]}`、`c = #{t : B[t] ∧ ¬A[t]}`。

**證明**：取 `t ∈ U`。依 `U` 的定義，`t` 的**每一臂**都有 `meets_demand` 為假。
故對每一臂 `_deliv(t) = accepted ∧ False = False`，與 `accepted` 的取值無關
（**兩種取值窮舉**，不是抽樣）。於是任一對臂上 `(A[t], B[t]) = (False, False)`，
既不滿足 `A[t] ∧ ¬B[t]` 也不滿足 `B[t] ∧ ¬A[t]` ⇒ `t` 對 `b` 與 `c` **各貢獻 0**。
從 `common` 移除一群對 b/c 各貢獻 0 的題，b 與 c 逐數不變。∎

⇒ `full[:2] != excl[:2]` 對**任何**資料為假 ⇒ `BROKEN_BC_MISMATCH` 不可達 ⇒
§六-2 的推翻條件不可觸發。**witness 預測為 0，且這個 0 是恆等式強制的，不是資料碰巧。**

⚠ 此證明**不推翻 R450 §三 本身**。§三 那句「量具覆蓋率翻不動配對比較」仍然成立——
它本來就是推導，R450 §三 自己也寫了「這是推導不是量測」。本輪推翻的是**比它弱的那一句**：
「已在真資料上對照過」不是獨立佐證。收官輪引用 §三 要引**證明**，不准引**對照**。

## 五、怎麼驗（判準寫死在改碼之前）

- **A（加法性）**：對同一份凍結的 `rows.jsonl` 快照，加這 5 筆記錄前後，
  **R453 原有 12 筆記錄的 `class` 與 `witnesses` 逐一相同**，差異恰好只有新增的鍵。
  比對用 `git show HEAD:<path>`（⛔ 不准 `git stash`，即使限定 pathspec）。
- **B（有牙齒）**：每一條新記錄都要有一個**指名**捕獲它的突變體，
  且**判準是「那個會變的量」**（class 或 witnesses），不是 `rc≠0`、不是 crash。
- **C（校準：正對照）**：R450 §五-3 那條**已知**的恆假死碼（R450 §八 已證並刪除）
  餵進同一個分類器要吐 `FORCED_GREEN`。它是已知答案的樣本，分不出來就是尺沒牙齒。
  該條已被刪，故用**窮舉四種 `(meets_demand, accepted)` 組合**重建其運算式再分類。
- **D（校準：負對照）**：R453 既有的 `P-Z1`（自由統計量）必須仍是 `EVALUABLE`——
  分類器不能把什麼都判成 FORCED。
- **E（不回歸）**：`r447_mutation_check.py` 原有 33 個突變體仍全部 `:Y`，
  `--selftest` 仍 PASS，六支例行尺輸出不變。

## 六、推翻條件（觸發就照實寫，**不准當場補判準去修**）

1. 若 §四 的證明在真資料上被推翻——`bc_cross_check` 真的出現 mismatch，
   或某個 `t ∈ U` 的某臂 `_deliv` 為真——那是 `CONTRADICTION`（B1），
   本文件 §四 **立即作廢**，且要回頭查 `_deliv`／`U` 其中之一的語意。
   **不准**改分類規則讓它變綠。
2. 若 A 對不上（R453 任何一筆既有記錄的 `class` 或 `witnesses` 變了）⇒
   **回退這個改動**，在 STATE 寫「加法式宣稱不成立」，不靠調整比對方式讓它變綠。
3. 若 C 做不到（已知的恆假死碼分不出來）⇒ 記 `校準失敗`，
   **本輪所有 FORCED_GREEN 判決一律降級成 UNRESOLVED**，不准當結論用。
4. 若 R450-§六-1 的預測錯（實際是 UNRESOLVED 而非 EVALUABLE）⇒ 照實寫，
   並附「離邊界距離／留一擾動幅度」比值（記憶鐵律：留一法只是 1/n 擾動，
   對寬窗口沒有解析度，UNRESOLVED 要附這個比值才誠實）。
5. 若冒出**第六類**本表沒預期的條文 ⇒ 照實寫、人眼確認、**不算進計數、
   不當場補判準**（R528 紀律）。

## 七、這份文件不做的事

- 不對 r447 下任何收官判斷；收官仍歸 fable 稽核輪。
- 不改 `analyze_r447.py`、`r447_gauge_capability.py`、`gain_run.py`，
  不改任何 P-Z 判準、不改任何窗口、不放寬任何門檻。
- 不新開 run（SPEC_GAIN §7，8765 被 r447 佔用）。
- run 活著 ⇒ 全程不 `git add runs/g_r447_conform_lcb2/`（r671 鐵律）。
