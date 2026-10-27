# 真訊號列 vs 上限列：哪一欄能引用、哪一欄只是上界

> 對應 ASSIGNMENT「誠實現況」第 2 條與 P1 成效口徑（「任何成效數字：寫清楚用的是哪一欄、
> 有沒有用到評分器、n 是多少」）。本頁把三欄的重抽定義、逐題型數字、引用規則與禁句
> 寫在一處；每行都可以離線重播（§5），`tests/test_real_signal_columns_doc.py` 把本頁數字
> 釘死在機器輸出上。沒有本頁沒寫的保證。

## 1. 三欄各是什麼

重抽（resample）的停止條件決定那一欄是「Vacant 自己訊號能做到的」還是「上界」：

| 欄名 | 停止條件 | 用了評分器？ | 性質 |
|---|---|---|---|
| `flag_restart` | Vacant 自己的紀錄訊號：findings 為空＝放行，否則重抽（cap K） | **否**（所有題型） | **真實訊號列**——可引用 |
| `test_restart` | 檔案裡的 grader pass＝停，fail＝重抽（cap K） | **僅在可見測試＝評分器的題型上否**（`polyglot_py`）；其餘題型**是** | 題型綁定：`polyglot_py` 上是客户自己的可執行驗收＝真實訊號；其餘題型 agent 看不到那個測試＝**上界** |
| `oracle_any` | 組內任意一次 archived run 過即算過 | **是**（所有題型） | **永遠上界**（≈oracle@k） |

「用評分器的對錯決定要不要重抽」在可見測試≠評分器的題型上幾乎等於 oracle@k——
它量的是「如果我知道答案該重抽幾次」，不是「裝了 Vacant 能拿到什麼」。

## 2. 離線重播對照表（c37_final.json，cap=3，1187 格，331 單位）

單位＝(suite, batch, task) 組（≥2 次獨立 archived run）、每組等權。`pass@1`＝一次 archived
run 照記錄；數字來自 `ops/realrun/offline_real_signal_replay.json`（鏡像，與
`ref/c37_final.json` 重播逐欄位一致）。

| 題型 | n（組） | pass@1 | flag_restart（真訊號） | test_restart | oracle_any |
|---|---|---|---|---|---|
| dabench | 60 | 79.36% | **81.31%**（scorer=否） | 97.92%（**上界**，scorer=是） | 98.33%（**上界**） |
| dabstep | 144 | 65.05% | **67.74%**（scorer=否） | 75.26%（**上界**，scorer=是） | 75.69%（**上界**） |
| databench | 59 | 67.32% | **70.14%**（scorer=否） | 88.14%（**上界**，scorer=是） | 89.83%（**上界**） |
| polyglot_py | 68 | 37.28% | **46.96%**（scorer=否） | 55.88%（真訊號——該題型可見測試＝評分器，scorer=否） | 55.88%（**上界**） |
| ALL（每組等權） | 331 | 62.34% | **66.36%**（scorer=否） | 77.68%（**上界**，scorer=是——池含用評分器的題型） | 78.25%（**上界**） |

可引用的真實訊號讀法（口徑＝flag_restart 欄）：
**ALL 62.3% → 66.4%（+4.1pp）**；**polyglot_py 37.3% → 47.0%（+9.7pp）**。
polyglot_py 上 `test_restart` 的 55.9% 也是真的拿得到（可見測試＝評分器，客户自己的
可執行驗收＋重抽）——**但只在該題型**。

## 3. Live 實跑（polyglot_py 34 題，可見測試＝評分器，scorer=否）

`ops/realrun/analyze_v4.json`、`analyze_v6.json`（exact two-sided McNemar，alpha=0.05）：

| 批次 | 臂 | n（pairs） | b | c | p | 決定狀態 |
|---|---|---|---|---|---|---|
| v4（2026-10-26） | A_none vs B_resample3 | 102 | 5 | 15 | 0.0414 | EFFECTIVE |
| v6（2026-10-27） | A_none vs B_resample3 | 170 | 3 | 20 | 0.0005 | EFFECTIVE |

可引句（照 prereg 原文口徑）：B（resample）在此批次接受的比 A（none）多
（n=170 pairs，34 題 × 5 reps）——**同一列真實訊號**（可見驗收＋乾淨重抽）在 v4
（n=102，p=0.0414）量到、在 v6 以更高功率重測。不得說「證明變好」（單一批次、
單一模型，H-12）。

v5（fresh_hint vs resample，n=102）＝UNRESOLVED：空結果非負結果，方向與幅度照實記錄。
v7（gemma-4-12b-it-qat 第二模型 cross-replication）＝進行中，**INCOMPLETE**：
<5 rep 只描述性、不給決定狀態，不得引用。

## 4. 引用規則（禁句）

**可引用為「裝了 Vacant 能做到的」：**
- `flag_restart` 欄（任何題型，scorer=否）；
- `test_restart` 欄**僅在** `visible_tests_are_grader_suites`（目前只有 `polyglot_py`）；
- live v4/v6 的 B_resample3 vs A_none（必帶 n、scorer=否、單一批次口徑）。

**不得引用為成效（是上界，不是 Vacant 自己訊號）：**
- `test_restart` 在 dabench／dabstep／databench（scorer=是）；
- `oracle_any` 在任何題型（scorer=是）；
- 歷史誤引「+15.4pp（62.3%→77.7%）」——那是 `test_restart` 欄（ALL 池 77.68%），用評分器的對錯決定重抽；77.7 與 78.2（oracle）都只能當**上界**報告。

**紀律（每筆成效數字都要帶）：**
1. 欄名（flag_restart／test_restart／oracle_any）與題型；
2. scorer 真偽（是＝上界、不得當成效）；
3. n（組數或 pairs）與批次；
4. 前提一句：離線重播＝對 archived runs 的 resample 模擬（零模型調用）、cap=3、
   每組等權；live＝單一模型單一題集的實跑（H-12：不轉移到其他模型／題庫，除非重跑）。

**禁句**（AGENTS.md §9 `banned_phrasings_for_results`＋口徑規則）：
「證明變好／證明有效」、「信任層」，以及對結果的
「replication failed」「effect disappeared」「equivalent」「tied」「majority supports」
「replication stable」「the loop is useless」。口徑用「可究責／有根據」；
demo 可說「可以看到改善」，「證明改善」保留給先註冊的批次跑。

## 5. 重現（零模型調用）

```bash
# 算法自證（合成組手算期望值＋標記守衛）
python3 ops/realrun/offline_real_signal_replay.py --selftest
# 對照表（落盤輸入存在時；repo 內同 sha256 副本：runs/_replay/c37_final.json）
python3 ops/realrun/offline_real_signal_replay.py ref/c37_final.json 3
# 本頁數字 vs 鏡像逐欄位比對
pytest tests/test_real_signal_columns_doc.py tests/test_realrun_offline_real_signal_replay.py -q
```

輸入檔 sha256（`ref/c37_final.json`＝`runs/_replay/c37_final.json`）：
`9c6e2b1383e478f88805ccac0f0db219f32316fb4692107d9d4e9e76804bbf5c`（1187 格，全用）。
