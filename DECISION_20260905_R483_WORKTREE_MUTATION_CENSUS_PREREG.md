# R483 預註冊：把那 8 支「只提及 --selftest」的突變量具接進語料增長擾動

日期 2026-09-05 UTC。輪次 round754。模型 Opus 5。
上游：`DECISION_20260905_R482_CORPUS_SENSITIVITY_PREREG.md`、GAIN_STATE round753 第 6 點。

**本檔在任何量測之前 commit。** 產物：`ops/gain/r483_worktree_census.py`、
`ops/gain/data/r483_worktree_census.json`。

---

## 一、要答的問題

R482 的 census 掃了 24 支自己提供 `--selftest` 的量具，三種語料增長擾動下一支都沒咬到
（`decay_prone=[]`）。但它**具名排除**了 8 支「只是把 `--selftest` 傳給別人」的突變量具：

```
eq5_analyze_mutation_check.py
mutation_test_r470_paired_ci.py      mutation_test_r474_stub_sweep.py
mutation_test_r472_gauge_capability.py  mutation_test_r475_oracle_sweep.py
mutation_test_r473_r466_census.py    mutation_test_r476_closing_arbiter_drift.py
r471_specificity_and_deletion.py
```

R482 的 `P_TEST` 擾動（往 `tests/` 加一個 `assert True` 的新檔）**本來就是衝著它們設計的**
（memory 前科：突變量具寫死期望收集數 ⇒ 測試檔一增減全部安靜 BROKEN），結果一支都沒跑到。
本輪把它們接進來。

## 二、先決的結構事實（讀原始碼得到，不是量測）

這 8 支**不是**同一種東西。它們「語料在哪」分三類，而這決定了擾動該加在哪：

| 類 | 工具 | 受測目標跑在哪 | ROOT 加新檔看得見嗎 |
|---|---|---|---|
| **ROOT 域** | `eq5_analyze_mutation_check.py` | `cwd=ROOT`，直接跑 `ops/gain/analyze_eq5.py` | **看得見** |
| **WT 域**（6 支） | r470 / r471 / r472 / r473 / r474 / r475 | `cwd=wt`，跑 `wt/<REL>` | **看不見** |
| **自建極小域** | `mutation_test_r476_closing_arbiter_drift.py` | 自己 `rmtree(wt)` 重建，只 `copy2` **兩個檔**（REL＋PREREG） | **看不見** |

⇒ **把擾動加在 ROOT、然後宣告這 6+1 支「INSENSITIVE」，是強制綠燈**（r718 的 `FORCED_GREEN`）。
它們的語料根本不是 ROOT。R482 排除它們是對的，但排除的理由（argparse rc=2）
掩蓋了這個更根本的理由。

**⚠ 操作上的地雷**：`mutation_test_r476` 的 `build_worktree()` 第一行是 `shutil.rmtree(wt)`。
把共用 worktree 路徑餵給它會**刪掉那個 worktree**。它必須拿到自己的專屬路徑。

## 三、設計：兩個臂

- **A_ROOT**：擾動加在真 ROOT（＝R482 原本的做法）。8 支全跑。
- **A_WT**：擾動加在**受測目標實際看得到的那個語料**——即共用 worktree `/dev/shm/r483wt`
  （`git worktree add --detach HEAD`，只含被追蹤內容）。6 支 WT 域跑。
  - `eq5_analyze_mutation_check` 不進 A_WT（它沒有 `--worktree`，A_ROOT 才是它的正確臂）。
  - `r476` 不進 A_WT（它會 rmtree 掉給它的路徑；且它的語料只有 2 個檔，兩臂都碰不到）。

擾動沿用 R482 的三種，逐字不改（`P_MD` root 散文 `.md`／`P_TEST` `assert True`／`P_TOOL` 只 print）。

判決規則沿用 R482 `classify()` 的語意，逐條複製：
`BROKEN`（rc 不在 {0,1,2,3} 或 timeout）> `NONDETERMINISTIC`（clean×2 不同）>
`INSENSITIVE`（三擾動 rc 皆等於 clean）> `DECAY_PRONE`（clean=0 而某擾動 ≠0）>
`MASKING`（clean≠0 而某擾動 =0）> `SENSITIVE_OTHER`。

## 四、雙向校準（沒有它，整輪的綠燈不算數）

在 **A_WT 的同一次跑**裡放兩個合成對照，放在 worktree 裡、跟真工具走同一條路徑：

- **正對照** `_r483_pos_control.py`：寫死 `len(glob("tests/test_*.py")) == <基線>`
  ⇒ 必須判 `DECAY_PRONE`，且 `triggered_by == ["P_TEST"]`。
  （這正是 memory 記的「突變量具寫死期望收集數」的合成複製。）
- **負對照** `_r483_neg_control.py`：讀同一份語料但斷言**關係式**（每個檔名都在自己產生的表裡）
  ⇒ 必須判 `INSENSITIVE`。

任一方向不對 ⇒ 輸出 `BASELINE_BROKEN`、rc=2、**本輪不准報任何工具的判決**。

## 五、預測（落筆於量測之前）

- **P-1**（`intent=guard`）：A_ROOT 裡那 6 支 WT 域工具全部 `INSENSITIVE`。
  **這是構造上的強制綠燈，基準率≈1，不得作為證據引用**；記錄它是為了讓 R482
  「排除它們」的決定留下可查的理由。
- **P-2**（`intent=evidence`，本輪的主預測）：A_WT 裡那 6 支，**至少 1 支**判決不是 `INSENSITIVE`。
  基準率：R481→0/未知、R482→0/24。連兩輪為 0 ⇒ 若本輪又是 0，只准寫
  「今天這 6 支上也沒有這個類別」，不准寫「已證明突變量具沒有這個缺陷」。
- **P-3**（`intent=evidence`）：若 A_WT 裡恰好 1 支翻掉，那支是 `mutation_test_r473_r466_census.py`
  （它的受測目標 `r466_r461_sec2_sec6_census.py` 有 5 處 glob，全 8 支裡掃語料最兇）。
  對照的 glob 數：r447_gauge_capability 2、r474_stub_sweep 2、r475_oracle_sweep 1、
  paired_ci 0、r476_closing_arbiter_drift 0。
- **P-4**（`intent=guard`）：四、的雙向對照兩邊都對。
- **P-5**（`intent=evidence`）：`eq5_analyze_mutation_check.py` 在 A_ROOT 判 `INSENSITIVE`。
  它**沒有 argparse**，`--selftest` 被整個忽略、每次都跑完整突變掃描才 rc=0
  ⇒ R482 把它記進 census 的那一次，跑的根本不是它的 selftest。
- **P-6**（`intent=guard`）：8 支的 `clean_a` 全部 rc=0。
  **⚠ 這一條對 r474 與 r470 不是盲測**（見八）。
- **P-7**（`intent=evidence`）：`mutation_test_r476` 在 A_ROOT 判 `INSENSITIVE`，
  且**這個綠燈同樣是強制的**（它只 copy2 兩個檔）⇒ 收官要把它跟 P-1 那 6 支列在同一欄，
  「本輪 8 支全 INSENSITIVE」這句話裡有 **7 支是構造強制的**。

## 六、推翻條件（觸發就照實寫，不准當場補判準去修）

1. 雙向對照任一方向不對 ⇒ `BASELINE_BROKEN`、rc=2、不報判決。
2. 任一支 `clean_a != clean_b` ⇒ 該支記 `NONDETERMINISTIC`，優先於一切；
   不准為了讓它安靜而重跑取多數。
3. 冒出判準沒預期的第四類 scoping ⇒ 照實寫、人眼確認、**不算進 P-2 的計數**、不當場補判準。
4. **時間盒 60 分鐘**（主 run 在跑，CPU 是共用的）。逾時就停，
   沒跑到的工具具名記 `UNSCANNED`——`UNSCANNED ≠ UNRESOLVED ≠ INSENSITIVE`。
5. 若 A_WT 的某支在**乾淨** worktree 上就 rc≠0（clean_red），它的擾動判決不可解讀，記 `CLEAN_RED` 並具名。

## 七、具名排除（不是安靜跳過）

- `runs/` 與題庫兩類語料：沿用 R482 §七，本輪**沒量**。
- 「同一份文件內部長大」（R481 真實案例的形狀）：本輪**沒有解析度**，三個擾動全是新檔案。
- 主 run `runs/g_r461_lcb3_three_arm`：本輪**零分析**，只讀列數。

## 八、本輪不是盲測——判準落筆前我讀過／跑過什麼

1. 讀過全 8 支的原始碼（第二節那張表就是這麼來的）。
2. **已經跑過** `mutation_test_r474_stub_sweep --worktree /dev/shm/r483wt`（52.9s，rc=0，
   RESULTS 三個 DETECTED＋N1 RED_UNNAMED）與 `mutation_test_r470_paired_ci`（54.2s，rc=0，
   總判決 PARTIAL_TEETH、MISSED=['M4','M9']）——那是為了估時間盒。
   ⇒ **P-6 對這兩支不是盲測**，而且我已經看到 r470 的 `PARTIAL_TEETH` 仍然 rc=0。
3. 讀過 R482 的 census 原始碼與 `data/r482_corpus_sensitivity_v2.json`。
4. 沒有讀主 run 的 rows/summary 內容。

## 九、下一輪能用什麼收回仲裁權

- `data/r483_worktree_census.json` 留原始 `records`（每支每臂的 5 個 rc），不只留判決字串。
- 本檔不因結果修改。要改判準只能開新 DECISION。
