# DECISION AMEND-1（2026-09-04 round692）：`same_choice` 在「閘門拒交」時量錯了東西

**適用 run**：`runs/g_r446_eq5_mbpp`（發射於 round689，本輪仍在跑，rows ~40/371）。
**這份文件修的是實作，不是判準的意思**——`DECISION_20260904_R446_EQUAL_BUDGET_ARM.md`
（65171d1，早於本輪）一個字都不改，它仍是所有窗口數字的仲裁者。

## 一、缺陷

`gain_run.py:arm_eq5` 在閘門**全部候選都沒通過**時，走這一行：

```python
accepted = chosen is not None
gate_code, gate_worker = chosen if accepted else cands[-1]      # ← fallback，不是「選擇」
...
"same_choice": gate_code == vote_code,
```

`cands[-1]` 是「row 裡總得塞一份碼」的 fallback。閘門在這一格**什麼都沒交**。
但只要多數決剛好也挑到最後那一份，`same_choice` 就回報 `True`——
把「閘門拒交、多數決交了東西」記成「兩條規則選到同一份」。

## 二、怎麼確認的（先寫判準、再跑）

判準寫在跑之前：**找到任何一顆 seed 使 `accepted=False ∧ same_choice=True` ⇒ 缺陷成立；
掃完 200 顆都找不到 ⇒ 缺陷不成立，照實寫。** 夾具＝5 份候選全部驗收失敗。

```
掃過的 seed 數=7  accepted=False 且 same_choice=True 的 seed=[0, 1, 6]
  seed=0  accepted=False  same_choice=True  gate_sha=6bc48a13  vote_sha=6bc48a13
          vote_accepted=True  calls=5
```

**這是合成復現，不是從 run 的數字倒推出來的**（記憶鐵律：挑樣本驗假說要記自己照什麼挑的）。
既有的 `eq5_mutation_check.py` 兩個夾具（CODES_A／CODES_B）都含通過者，
所以這條路徑從來沒有被夾具走到過。

## 三、影響範圍（逐項界定，不含糊）

- **主估計量不受影響。** `gate_deliv = accepted ∧ truth`、`vote_deliv = vote_truth`
  （`gain_run.py` row 計分段），拒交格的 `gate_deliv` 本來就是 False。
  配對的 b/c、Δ、CI、四格判定**一個數字都不會動**。
- **受影響的只有 `same_choice_rate`**，而它是 **P-R446-5**（窗口 [40,95]%）與
  **推翻條件 §六-1**（>95% ⇒ 結論只准寫「測不出來」）的量。
- 偏差方向：**只會把 `same_choice_rate` 往上推**（假的 True，永不假 False）。

## 四、修法：加一個欄位，不改舊欄位

DECISION §六-1 的字面意思是「兩條規則幾乎總是**選到同一份** ⇒ 這個比較沒有對比」。
**拒交不是「選到同一份」**——一邊交了、一邊沒交，是這個比較最有對比的一格。
所以下面這個量才是 §六-1 那句話的忠實實作：

```
same_choice_effective := accepted ∧ (gate_code_sha256 == vote_code_sha256)
```

- `gain_run.py`：**additive**——新增 `same_choice_effective` 欄位與 summary 計數，
  **`same_choice` 原值原封不動保留**（r446 的 rows 已經帶著它，改值會製造出處漂移）。
  本輪的原始碼修改**不影響 r446**：那支行程 02:19 之前就 import 完了，
  r446 的資料是 29df6bd 版 `gain_run.py` 產的，這一點寫在這裡備查。
- `analyze_eq5.py`：`same_choice_effective` 由 rows 的
  `accepted` / `gate_code_sha256` / `vote_code_sha256` **離線重算**
  （三個欄位已確認全在 r446 的 row 裡）⇒ r446 不需要重跑，一秒都不用重花。

## 五、仲裁者換誰（這是本文件唯一動到判準的地方，直說）

| 量 | AMEND-1 之前 | AMEND-1 之後 |
|---|---|---|
| P-R446-5（窗口 [40,95]%） | `same_choice_rate` | **`same_choice_effective_rate`** |
| 推翻條件 §六-1（>95%） | `same_choice_rate` | **`same_choice_effective_rate`** |

**兩個數字都無條件印、都逐條判 HIT／MISS 進 `prereg`**（raw 那條記為
`P-R446-5-raw`，附註「AMEND-1 之後不是仲裁者」），另外印
`false_same_choice_n`＝`¬accepted ∧ same_choice` 的筆數。
任何下一輪都能拿 raw 自行改判，不需要重跑。

**要揭露的自利方向**：這個修正**只會讓 `same_choice_rate` 下降**，也就是
讓 §六-1（「測不出來」）**更不容易觸發**、讓「我們量到了東西」**更容易成立**。
這是對本輪有利的方向，所以：

1. 修正的理由是**語意**（拒交不是同選）與**合成復現**，不是任何交付率數字；
2. raw 與 effective 兩個數字**都**留在 `prereg` 與 JSON 裡，仲裁權可被後輪收回；
3. 本輪已看過的中途數字**逐條揭露**（下一節），其中沒有任何一個是交付率或 Δ。

## 六、本輪已經看過的 r446 中途數字（全部列出）

```
（一）02:24 UTC 快照，rows 40 行
     拒交筆數 = 5／40
     其中被記成 same_choice=True 的（＝本缺陷的樣態）= 2

（二）02:27 UTC 接線驗證，rows 49 行 sha256_16=85f03a085f8f54fe
     measured 49  processed 49  infra_void 0  third_category_missing_fields []
     calls_per_task 5.0  budget_all_exactly_5 true  false_same_choice_n 2
     broken_reasons ["EQ5.terminal=False ⇒ …不是收官資料"]  verdict BROKEN  rc=1
     （輸出照 DECISION §五 過濾掉 Δ 與 deliv 兩組欄位再看）
```

`same_choice_rate`、`gate_deliv`、`vote_deliv`、b/c、Δ **一個都沒算**
（DECISION §五：中途不准算 Δ）。round690 的紀錄裡有 9 題時的 `same_choice` 2/9，
round691 揭露它為了查欄位名看過 26 題時的兩個 delivery rate——兩者都遠離 95%，
本修正在任何一端都不可能是為了讓某個門檻翻面。

## 七、推翻條件（給後輪）

- 若收官時 `same_choice_effective_rate` 與 raw **相差 < 1pp**，本修正在 r446 上
  等於沒作用 ⇒ 照實寫「AMEND-1 對 r446 的結論零影響」，不要寫成它救了什麼。
- 若 raw > 95% 而 effective ≤ 95%（兩者給出相反的 §六-1 判決），
  **兩個判決都寫進結論**，並把「該信哪個」留給人類，本輪不代答。
- 若 `analyze_eq5.py` 重算的 `same_choice_effective` 與未來 run 落盤的同名欄位
  不一致 ⇒ BROKEN，不准取其一。
