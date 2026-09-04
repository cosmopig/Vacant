# R453：收官之前，把 R440Z 每一條預註冊判準逐條問一次「它有可能是假的嗎？」

（2026-09-04 round715，Opus 5。`runs/g_r447_conform_lcb2` **仍在跑**（rows≈262/360，
ETA ~16:1x UTC）。本文件在量測之前寫定，量完不准改窗口。
本輪**不是**收官輪、**不改** R440Z 任何條文、**不改**任何 P-Z 的判決。）

## 一、為什麼現在做

round714（R452 §九）量到 **P-Z6 在這個題庫家族上不可證偽**：`visible_check` 的驗收條
逐條都在 `hidden_check` 裡（lcb2 120/120、evalplus 371/371）⇒「可見沒過但隱藏其實對」
在定義上不可能發生 ⇒ P-Z6 的 HIT 不帶資訊。

**但 round714 只追了 P-Z6 這一條。** R440Z 有 8 條預測、3 條中止準則、2 條推翻條件，
收官輪要拿它們當仲裁者。記憶鐵律兩條指著同一件事：

- 「判準要含基準率——沒有基準率的『支持』可能結構性不可能有反例＝空洞綠燈」
- 「懷疑旗標就掃全庫問『曾經 True 過幾次』＋逐 AND 項拆解」

**空綠燈只有在收官之前抓才有用。** 收官寫完再說「其中兩條是恆真的」，那份結論已經
發出去了。故本輪把這件事做完，做成一支可重跑的尺。

## 二、量什麼（估計量的定義，寫在測量之前）

對 R440Z 的每一條子句，取它的**否定**（＝「證偽事件」），問三件事：

1. **證偽事件在資料裡出現過幾次**（witness 數）；
2. 有沒有一條**與模型行為無關**的恆等式（題庫性質／程式碼恆等式）使它**不可能**發生；
3. 兩者的交叉判決。

分類（三格，事前定義，不准事後加格）：

| 類別 | 條件 | 收官該怎麼寫 |
|---|---|---|
| `FORCED_GREEN` | 寫得出恆等式 **且** 全庫 witness＝0 | HIT 要附「本題庫上不可證偽」＋恆等式＋基準率 |
| `EVALUABLE` | witness ≥ 1（＝候選恆等式被反例推翻，或證偽事件真的出現過） | 照常寫，HIT 帶資訊 |
| `UNRESOLVED` | 既無恆等式也無 witness | **不准**寫成 FORCED，也不准寫成「有帶資訊」；照實寫「本輪判不出來」 |

⚠ `EVALUABLE` **只表示「這條判準有可能為假」**，不表示「這個 n 分得出來」。
後者是解析度問題，仲裁者是 R451 的 MDE／N₈₀，兩者不准互相冒充。

⚠ 區間型判準（P-Z1／P-Z4／P-Z5a 這種「落在 a–b%」）沒有逐列 witness。
對它們用**留一法（jackknife）可及性**：逐題留一重算該統計量，
只要有任一個留一值落到窗外，就記 `EVALUABLE`（reachable_by_jackknife）；
全部落在窗內就記 `UNRESOLVED` 並附「窗寬相對抽樣噪音過寬」。
**留一法沒有可調參數**（新增旋鈕零）；不用 bootstrap，因為那要選 n_boot 與 seed。

## 三、事前預測（本輪的主張，量完照實對帳）

| # | 子句 | 證偽事件 | 預測類別 | 根據 |
|---|---|---|---|---|
| P-Z1 | OFF 失敗率 40–60% | 落在窗外 | `EVALUABLE` | 自由統計量 |
| P-Z2a | CONFORM vs OFF p < 0.01 | p ≥ 0.01 | `EVALUABLE` | 兩臂獨立抽樣 |
| P-Z2b | 差 +12–25pp | 落在窗外 | `EVALUABLE` | 同上 |
| P-Z3 | vs OFF5 +2–8pp | 落在窗外 | `EVALUABLE` | 同上 |
| P-Z4 | calls_per_task 1.5–2.2 | 落在窗外 | `EVALUABLE` | 自由統計量 |
| P-Z5a | 拒交率 5–12% | 落在窗外 | `EVALUABLE` | 自由統計量 |
| **P-Z5b** | **拒交題裡「五份全錯」≥80%** | **某個拒交題有候選 hidden 是對的** | **`FORCED_GREEN`** | **見 §四——與 P-Z6 同一條恆等式，且是它的子事件** |
| P-Z6 | 無 `visible_ok=False ∧ meets_demand=True` 的列 | 出現這種列 | `FORCED_GREEN` | round714 已證（本輪重跑一次，不引用） |
| P-Z7 | 任一臂 void<20%、CONFORM<5% | void 超標 | 預測 `UNRESOLVED` | 本 run void 恆 0；要跨 run 找 witness |
| P-Z8 | 每列有 `receipt_head` ∧ 鏈可驗 | 缺鍵或鏈為假 | 預測 `FORCED_GREEN`（前半） | `arm_conform` 的 return dict 裡 `receipt_head` 是**無條件字面鍵** |
| §六 | P-Z2 推翻條件 `c ≥ b/2` | c 大 | `EVALUABLE` | 待驗：若 CONFORM 首位候選與 OFF 同源，c 會被壓成 0 |

**預測會錯是正常的**；錯了照實寫，不准回頭改這張表。

## 四、P-Z5b 的恆等式（本輪的主張，證明寫在量測之前）

設 V(c)＝候選 c 通過 `visible_check`，H(c)＝通過 `hidden_check`。
round714 已量到：`visible_check` 的驗收條**逐條**都在 `hidden_check` 裡（lcb2 120/120）。
⇒ **H(c) → V(c)**，等價地 **¬V(c) → ¬H(c)**。

`r447_reject_reconstruct.py` 的定義（`ast.get_source_segment` 逐字取出，不得改寫）：

- 拒交：`not r.get("accepted")`，而 `arm_conform` 回傳 `"visible_ok": accepted`，
  `accepted` ⟺ 某個候選 V ⇒ **拒交 ⟺ 全部候選 ¬V**；
- 「五份全錯」：`not any(hid)` ⟺ 全部候選 ¬H。

拒交 ⇒ 全部 ¬V ⇒（恆等式）全部 ¬H ⇒ `not any(hid)` 為真。
**⇒ `all_candidates_wrong == rejected_tasks` 恆成立 ⇒ P-Z5b 的比例恆為 100%，
窗口 ≥80% 不可能不中。**

且它是 P-Z6／候選層無損性的**子事件**：P-Z5b 的分子要少一個，
必須存在候選滿足 `¬V ∧ H`，那正是 `candidates_visible_fail_hidden_ok` 計的東西
（round714 量到 0/390，`forced_zero=True`）。
⇒ round714 的提案 P-R452-1 只涵蓋 P-Z6 與無損性那兩個 0，**漏了 P-Z5b**，
而 round714 自己在 GAIN_STATE 裡把 `P-Z5b = 6/6 = 100% ⇒ HIT` 寫成了成立的證據。

**這個主張怎麼來的**（序貫誠實）：不是看 r447 的數字挑出來的，是讀
`r447_reject_reconstruct.py` 的**原始碼**時，把 round714 的恆等式套上去推出來的；
資料（6/6＝100%）只當一致性檢查，不是證據來源。若資料與恆等式牴觸（出現
`rej_all_wrong < rej_tasks`），那是**恆等式被推翻**，見 §六。

## 五、量具與它的牙齒（做之前寫死）

`ops/gain/prereg_falsifiability_census.py`，零 API、純本機。

- 恆等式那一半重用 `r447_eq5_offline.bank_gate_headroom`（round714 已 24/24 突變體驗過），
  **不另寫一份**；
- `receipt_head` 的「無條件字面鍵」用 `ast` 對 `gain_run.py` 的 `arm_*` 逐個 `Return`
  檢查（記憶鐵律：不得自己改寫一份運算式）；
- witness 那一半直接掃 `rows.jsonl` 與重建出來的候選；
- 接進 `ops/gain/r447_mutation_check.py`，**原有突變體一個都不准退步**。

驗收（三條，缺一不可）：

1. `--selftest` PASS（0 failed），含「夾具裡 V 與 H 不是互相導出的」前置尺
   （r695：夾具若把 B 從 A 導出，一致性擋門結構上沒有夾具看得見）；
2. 每個新突變體都有**指名**它的自檢條，且突變在**被測函式內部**生效
   （r695/r706：寫在模組層的突變體永遠不生效，長得跟「沒牙齒」一模一樣）；
3. 判準要挑「那個會變的量」——不准只寫 `rc≠0`，也不准只寫「verdict 必須改判」。

## 六、推翻條件（觸發了照實寫，不准當場補判準去修）

1. §四 的恆等式若被資料推翻（真的出現 `¬V ∧ H` 的候選，或 `rej_all_wrong < rej_tasks`）
   ⇒ **P-Z5b 與 P-Z6 都回到 `EVALUABLE`**，且 R440P 的拒交規則要按 R440Z §四 改寫。
   這一條比本文件的主張更優先。
2. `bank_gate_headroom` 的 `n_unparsed_shape > 0` ⇒ 子集關係只在認得出的那些題上成立，
   `FORCED_GREEN` 要降級成「在 n_parsed 題上 forced」，並把認不出的題數列出來。
3. 任一預測類別與量到的不同 ⇒ 照實寫在 GAIN_STATE，**不改 §三 那張表**。
4. 本尺**不是**任何 P-Z 的仲裁者，只是給收官輪的註腳；
   若收官輪認為某一條的分類會改變結論本身，那是 fable 輪的裁決，不是本輪的。
