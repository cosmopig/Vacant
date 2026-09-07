# runs/ 索引（人讀版）

> 這一份由 `ops/gain/build_runs_index.py` 從 `runs/INDEX.json` **同一次執行**
> 產生。要改內容改產生器，不要手改本檔——手改會在下一次 `--check` 被抓到。

`runs/` 共 **322** 個項目：216 個目錄 ＋ 106 個頂層檔案，合計 115 MB。其中 **44 個目錄有 `summary.json`**。

分類統計：

| kind | 個數 | 意思 |
|---|---:|---|
| `aborted` | 9 | 發射過但沒收官（被殺、掛掉、或只有 calls/notes） |
| `analysis` | 136 | 迴圈每輪的重算工作目錄——**衍生物，不是證據** |
| `other` | 21 | B 層掃描、展件抓圖、唯讀快照等 |
| `real_run` | 37 | 真跑過模型、有 summary.json 與 rows.jsonl——這些才是證據 |
| `replay` | 1 | 離線重放產物 |
| `smoke` | 12 | 冒煙／探針／量具檢查——**不進統計** |

### `INDEX.json` 的形狀（先看這個再寫 parser）

| key | 型別 | 內容 |
|---|---|---|
| `counts` | dict | 總數與 `by_kind` |
| `runs` | **list** | 每個目錄一筆，依 `name` 排序 |
| `top_level_files` | **list** | `runs/` 頂層的散檔 |
| `banks` | **dict** | 見 §五；`banks.lcb` 是 dict（key＝`"v1"`/`"v2"`/`"v3"`），**不是 list** |
| `logs` | dict | `logs.kinds` 是 list，其餘是 dict／str |
| `caveat_record_spec`、`discipline` | str／list | 讀之前要知道的界線 |

## 一、r441b…r449c、r461 這一段的主 run

這一段是目前**唯一有獨立稽核裁決檔**的那一層。`裁決` 欄逐字抄自該檔標題，
沒有改寫、沒有摘要。

挑哪一份有兩道關卡（規則全文在 `build_runs_index.py::_refs_and_headline`）：

1. **門檻**：run 目錄名要出現在該檔的**宣告區**——標題、前言、或第一個小節
   （第二個 `##` 之前），因為裁決檔一律在那裡寫 `資料：runs/<run>`。
   **被內文順帶提到一句不算。**
2. **對象**：還要是「標題直接點名」或「宣告區只點名這一個 run」。點名了
   兩個以上的 run，那份文件的對象就是併庫後的集合體而不是這一個 run。

兩關都過不了就標 `—` 而**不拿別人的裁決來充數**，那份改列進 `INDEX.json` 的
`related_settlements`。多份都合格時依「標題點名 → 檔名輪次號相符 →
份量（收官 > 獨立稽核 > 其餘 > 期中）→ 較新」排序，全部候選記在
`headline_candidates`，選中的理由記在 `headline_source`。

`—` **不是「通過」，是「沒有專門收官它的裁決檔」**——
`g_r444_conform_mbpp` 就是這樣：唯一點名它的收官是 r444+r445 併庫 371 題那份，
它在裡面只是兩個 stratum 之一。

| run | 日期 | 題庫 | 臂 | n（列／題） | 跑到底 | 零 void | void | 裁決（逐字抄自 DECISION 標題） |
|---|---|---|---|---:|---|---|---:|---|
| `g_r441_gemma_only_mbpp_b` | 2026-09-02 | MBPP+ v0.2.0 | OFF/OFF5/ON | 525／179 | — | 否 | 12 | DECISION R516（2026-09-02 21:00 UTC，Fable 5.1 稽核輪）：E1 收官——照 R483 §3d 寫死的判準裁決<br>[DECISION_20260902_R516_E1_FINAL_WRAPUP.md](../DECISION_20260902_R516_E1_FINAL_WRAPUP.md) |
| `g_r442_ononly_20260901` | 2026-09-01 | MBPP+ v0.2.0 | ON | 11／11 | — | 否 | 2 | DECISION 2026-09-01 round446: gemma-4-12b-it-qat 掛了，殺掉 g_r442_ononly_20260901<br>[DECISION_20260901_R446_GEMMA_OUTAGE_KILL_R442.md](../DECISION_20260901_R446_GEMMA_OUTAGE_KILL_R442.md) |
| `g_r443_gemma_lcb` | 2026-09-03 | lcb v1 | OFF/OFF5/ON | 269／91 | 是 | 否 | 4 | R440T：E3 收官——H-B（題目太簡單）被排除；評審在難題上翻成「幾乎一律說錯」<br>[DECISION_20260904_R440T_E3_WRAPUP.md](../DECISION_20260904_R440T_E3_WRAPUP.md) |
| `g_r444_conform_mbpp` | 2026-09-03 | MBPP+ v0.2.0 | CONFORM/OFF/OFF5 | 537／179 | 是 | 是 | 0 | —<br>（無專屬裁決；相關收官：[CONCLUSION_20260904_R445_CONFORM_SETTLEMENT.md](../.claude/worktrees/agent-ae56ce11337164082/CONCLUSION_20260904_R445_CONFORM_SETTLEMENT.md)、[CONCLUSION_20260904_R445_CONFORM_SETTLEMENT.md](../CONCLUSION_20260904_R445_CONFORM_SETTLEMENT.md)） |
| `g_r445_conform_mbpp_ext` | 2026-09-03 | MBPP+ v0.2.0 | CONFORM/OFF/OFF5 | 576／192 | 是 | 是 | 0 | R440X：r445 的獨立稽核——併庫區間排除 0 我複核成立；但真正紮實的發現是「五倍預算買不到東西」<br>[DECISION_20260904_R440X_R445_INDEPENDENT_AUDIT.md](../DECISION_20260904_R440X_R445_INDEPENDENT_AUDIT.md) |
| `g_r446_eq5_mbpp` | 2026-09-04 | MBPP+ v0.2.0 | EQ5 | 371／371 | 是 | 是 | 0 | R446 稽核：等預算臂 EQ5 的獨立重算——同意「閘門規則贏過多數決」，並把能講的話框死<br>[DECISION_20260904_R446_FABLE_AUDIT.md](../DECISION_20260904_R446_FABLE_AUDIT.md) |
| `g_r447_conform_lcb2` | 2026-09-04 | lcb v2 | CONFORM/OFF/OFF5 | 360／120 | 是 | 是 | 0 | R459：`runs/g_r447_conform_lcb2` 收官裁決（Fable 5.1 稽核輪，round726）<br>[DECISION_20260904_R459_R447_SETTLEMENT.md](../DECISION_20260904_R459_R447_SETTLEMENT.md) |
| `g_r448_eq5_mbpp_seed2` | 2026-09-06 | MBPP+ v0.2.0 | EQ5 | 371／371 | 是 | 是 | 0 | R448 稽核：EQ5 在全新 seed 上的獨立複製——判定 REPLICATED<br>[DECISION_20260906_R448_FABLE_AUDIT_REPLICATED.md](../DECISION_20260906_R448_FABLE_AUDIT_REPLICATED.md) |
| `g_r449_eq5_lcb2` | 2026-09-06 | lcb v2 | EQ5 | 120／120 | 是 | 是 | 0 | R449B 稽核：EQ5 在 LCB v2 難題上——判定 REPLICATED_ON_HARD<br>[DECISION_20260906_R449B_FABLE_AUDIT_REPLICATED_ON_HARD.md](../DECISION_20260906_R449B_FABLE_AUDIT_REPLICATED_ON_HARD.md) |
| `g_r449c_eq5_lcb3` | 2026-09-06 | lcb v3 | EQ5 | 189／189 | 是 | 是 | 0 | R449C 稽核：EQ5 在 lcb3（189 題）——判定 UNRESOLVED：同號（+4.23pp、b/c=13/5）但下界 −0.66 沒過 0<br>[DECISION_20260907_R449C_FABLE_AUDIT_UNRESOLVED.md](../DECISION_20260907_R449C_FABLE_AUDIT_UNRESOLVED.md) |
| `g_r461_lcb3_three_arm` | 2026-09-06 | lcb v3 | CONFORM/OFF/OFF5 | 567／189 | 是 | 是 | 0 | R461 稽核：CONFORM 在 LCB v3（189 題）三臂——獨立重算<br>[DECISION_20260906_R461_FABLE_AUDIT.md](../DECISION_20260906_R461_FABLE_AUDIT.md) |
| `g_r461_off_gate_lcb3` | 2026-09-04 | lcb v3 | OFF | 189／189 | 是 | 是 | 0 | —<br>— |

> `n（列／題）`＝`rows.jsonl` 的列數／去重後的 `task_id` 數。多臂 run 的列數是**各臂相加**，不是樣本數；配對檢定的 n 要看 `task_id`。逐臂列數在 `INDEX.json` 的 `n_rows_by_arm`。
> `跑到底`＝`summary.json` 的 `run_terminal`（每個 task 都被處理過，**含判成 `infra_void` 的**）；`零 void`＝`run_complete`（`n_void==0` 且全部處理完）。兩欄不同義：`g_r443_gemma_lcb` 跑到底了但有 4 筆 void，所以比例類指標的分母要照鐵律 3 扣掉那幾筆。舊版 runner 沒寫 `run_terminal` 的一律標 `—`——**那是「不知道」，不是「跑完了」**。

## 二、其餘的 run：冒煙／探針／中止／未收官

**這一張表裡的東西都不能當證據。** 列出來是為了讓「為什麼 runs/ 有這麼多目錄」
有個交代，也讓人一眼看出哪些是半成品。

| run | kind | 日期 | 題庫 | n | 有 summary | 說明 |
|---|---|---|---|---:|---|---|
| `_probe_r210` | `smoke` | 2026-08-28 | — | 0 | 否 | probe_or_smoke |
| `_probe_r212` | `smoke` | 2026-08-28 | — | 0 | 否 | probe_or_smoke |
| `_smoke_het_r210` | `smoke` | 2026-08-28 | — | 0 | 否 | probe_or_smoke |
| `g_het2_r271_20260829` | `aborted` | 2026-08-29 | — | 0 | 是 | summary_without_rows |
| `g_het_off_r262_20260829` | `aborted` | 2026-08-29 | — | 0 | 否 | no_summary |
| `g_het_r210_20260828` | `aborted` | 2026-08-28 | — | 0 | 否 | no_summary |
| `g_local_smoke_20260824` | `smoke` | 2026-08-24 | MBPP+ v0.2.0 | 3 | 是 | probe_or_smoke |
| `g_off60_20260824` | `aborted` | 2026-08-24 | — | 0 | 是 | summary_without_rows |
| `g_off60_r345_20260830` | `aborted` | 2026-08-30 | — | 0 | 否 | no_summary |
| `g_off_failure_rate_20260901` | `aborted` | 2026-09-01 | — | 0 | 否 | no_summary |
| `g_off_failure_rate_20260901b` | `aborted` | 2026-09-01 | — | 0 | 否 | no_summary |
| `g_off_probe_20260902_n60` | `smoke` | 2026-09-02 | — | 0 | 否 | probe_or_smoke |
| `g_onoff5_qwenonly_20260824` | `aborted` | 2026-08-24 | — | 0 | 是 | summary_without_rows |
| `g_probe371_20260825` | `smoke` | 2026-08-25 | — | 0 | 否 | probe_or_smoke |
| `g_probe_20260825_r123` | `smoke` | 2026-08-25 | — | 0 | 否 | probe_or_smoke |
| `g_r441_gemma_only_mbpp` | `aborted` | 2026-09-02 | — | 0 | 否 | no_summary |
| `g_r461_probe_lcb3` | `smoke` | 2026-09-04 | — | 0 | 否 | probe_or_smoke |
| `g_smoke_20260820` | `smoke` | 2026-08-20 | MBPP+ v0.2.0 | 18 | 是 | probe_or_smoke |
| `off_probe_n60_20260902` | `smoke` | 2026-09-02 | — | 0 | 否 | probe_or_smoke |
| `off_probe_n60_20260902_test` | `smoke` | 2026-09-02 | — | 0 | 是 | probe_or_smoke |
| `probe_verify_20260901` | `smoke` | 2026-09-01 | — | 0 | 否 | probe_or_smoke |

## 三、跑完但沒被獨立稽核的 run

有 `summary.json` 也有 `rows.jsonl`，但**不在上面那一段裡**——都是 2026-08 到
09 初的探索期 run：為了決定下一步怎麼跑而跑的，不是為了得到一個可以拿去講的結論。

這 25 個裡，`跑到底` 有 25 個是 `—`（那個時期的 runner 還沒寫 `run_terminal` 欄位，所以是**不知道**，不是跑完了）；`零 void` 是 `否` 的有 24 個。

**沒被稽核不等於不成立，也不等於成立——就是沒複核過。** 引用其中任何一個數字，
都要把這一句一起講出去。

| run | 日期 | 題庫 | 臂 | n（列／題） | 跑到底 | 零 void | void | 提到它的 DECISION | 其中屬裁決檔 |
|---|---|---|---|---:|---|---|---:|---:|---:|
| `g_e2q_off_lcb_qwenonly_20260902` | 2026-09-02 | lcb v1（子集，版本不可分辨） | OFF | 1／1 | — | 否 | 0 | 8 | 0 |
| `g_het2_r263_20260829` | 2026-08-29 | MBPP+ v0.2.0 | OFF | 177／177 | — | 否 | 2 | 14 | 6 |
| `g_het2_r274_20260829` | 2026-08-29 | MBPP+ v0.2.0 | ON | 8／8 | — | 否 | — | 6 | 0 |
| `g_het3_r278_20260829` | 2026-08-29 | MBPP+ v0.2.0 | OFF5/ON | 221／132 | — | 否 | 137 | 18 | 4 |
| `g_off371_20260825` | 2026-08-25 | MBPP+ v0.2.0 | OFF | 367／367 | — | 否 | 4 | 24 | 6 |
| `g_off5_qwen_only_20260901` | 2026-09-01 | MBPP+ v0.2.0 | OFF5 | 55／55 | — | 否 | 5 | 6 | 2 |
| `g_off60_local_20260824` | 2026-08-24 | MBPP+ v0.2.0 | OFF | 13／13 | — | 否 | — | 8 | 0 |
| `g_off60_qwenonly_20260824` | 2026-08-24 | MBPP+ v0.2.0 | OFF | 60／60 | — | 是 | 0 | 22 | 0 |
| `g_off60_relay2_20260824` | 2026-08-24 | MBPP+ v0.2.0 | OFF | 8／8 | — | 否 | — | 6 | 0 |
| `g_off60_relay_20260824` | 2026-08-24 | MBPP+ v0.2.0 | OFF | 42／42 | — | 否 | 18 | 8 | 2 |
| `g_off_failure_rate_20260901c` | 2026-09-01 | MBPP+ v0.2.0 | OFF | 16／16 | — | 否 | 0 | 2 | 2 |
| `g_off_qwen_only_20260901` | 2026-09-01 | MBPP+ v0.2.0 | OFF | 57／57 | — | 否 | 3 | 4 | 2 |
| `g_on371_20260825` | 2026-08-25 | MBPP+ v0.2.0 | ON | 167／167 | — | 否 | — | 10 | 0 |
| `g_on_qwen_only_20260901` | 2026-09-01 | MBPP+ v0.2.0 | ON | 39／39 | — | 否 | 21 | 4 | 0 |
| `g_on_qwen_only_scale2_20260901` | 2026-09-01 | MBPP+ v0.2.0 | ON | 12／12 | — | 否 | 48 | 16 | 2 |
| `g_onoff5_371_r123_20260825` | 2026-08-25 | MBPP+ v0.2.0 | OFF5/ON | 718／371 | — | 否 | 24 | 26 | 6 |
| `g_onoff5_qwenonly_v2_20260824` | 2026-08-24 | MBPP+ v0.2.0 | ON | 4／4 | — | 否 | — | 8 | 0 |
| `g_onoff5_qwenonly_v3_20260824` | 2026-08-24 | MBPP+ v0.2.0 | OFF5/ON | 116／60 | — | 否 | 4 | 8 | 0 |
| `g_onr_only_r237_20260828` | 2026-08-28 | MBPP+ v0.2.0 | ONR | 188／188 | — | 否 | — | 4 | 0 |
| `g_onr_r212_20260828` | 2026-08-28 | MBPP+ v0.2.0 | OFF | 179／179 | — | 否 | — | 12 | 0 |
| `g_r342_3arm_20260830` | 2026-08-30 | MBPP+ v0.2.0 | OFF/OFF5/ON | 11／8 | — | 否 | 16 | 8 | 0 |
| `g_r345_3arm_20260830` | 2026-08-30 | MBPP+ v0.2.0 | OFF/OFF5/ON | 16／6 | — | 否 | 2 | 10 | 0 |
| `g_r348_3arm_20260830` | 2026-08-30 | MBPP+ v0.2.0 | OFF/OFF5/ON | 33／20 | — | 否 | 38 | 10 | 0 |
| `g_r356_3arm_20260830` | 2026-08-30 | MBPP+ v0.2.0 | OFF/OFF5/ON | 432／178 | — | 否 | 101 | 42 | 10 |
| `g_r439_revcheck_20260901` | 2026-09-01 | MBPP+ v0.2.0 | OFF/OFF5/ON | 23／13 | — | 否 | 14 | 2 | 2 |

> `其中屬裁決檔`＝檔名帶 AUDIT／WRAPUP／SETTLEMENT／VERDICT／KILL 的那些（PREREG／CRITERION 是**量測之前**寫的判準，不算裁決，已排除）。數字大於 0 只代表「有裁決檔提到它」，不代表那份裁決是在裁決它——`INDEX.json` 的 `verdict_decisions` 列出是哪幾份，自己打開看。

## 四、`_analysis_*` 那 136 個目錄是什麼

它們**不是 run，也不是證據**。監控迴圈（`ops/loop.sh` 驅動的每一輪 agent）
每跑一輪就開一個 `runs/_analysis_r<輪次>/`，把那一輪的重算結果寫進去：
`off5_vs_off.txt`／`within_run.txt`／`PRIMARY_on_vs_off.txt` 這類配對檢定輸出、
量測前先 commit 的判準檔 `CRITERION.md`、以及工具自身的 `SELFTEST.txt`。
算它們的工具在 `ops/gain/replay/`（`paired_ci.py`、`pooled_paired_ci.py`、
`void_bounds.py`、`token_budget.py` …）。

為什麼要特別講清楚：這些檔的內容**會隨分析工具改版而變**，而且它們的輸入
就是 `runs/g_*/rows.jsonl`。把 `_analysis_*` 當原始資料引用，等於把自己的
結論再餵給自己一次。要複核就重跑 `ops/gain/replay/` 的工具、對 `rows.jsonl` 算，
不要抄 `_analysis_*` 裡的數字。

（`analysis_round455_paired`／`analysis_round522_acurve`／`analysis_round523_audit`／
`analysis_round525_final_recompute` 是同一類東西，只是命名沒帶底線前綴。）

## 五、題庫

> **`INDEX.json` 的 `banks` 是 dict 不是 list。** 下表每一列對應
> `banks.lcb["v1"|"v2"|"v3"]`——`banks.lcb` 本身也是 dict，key 是版本字串，
> 用 `banks.lcb[0]` 會 `KeyError`。同層還有四個非題庫的 key：
> `banks.lcb_relations`（dict）、`banks.lcb_caveat_v3`（str）、
> `banks.mbpp_plus`（dict）、`banks.codebench_builtin_families`（dict）。
> 對照之下 `runs` 與 `top_level_files` 是 **list**，`logs.kinds` 也是 list。

| 題庫 | 檔案 | 題數 | sha256 符合 codebench 釘值 | task_id 範圍 | contest_date 區間 | 難度 | 有參考解 | 已知壞題 | 用過它的 run |
|---|---|---:|---|---|---|---|---|---|---|
| **lcb v1** | `ops/gain/data/lcb_bank_v1.jsonl` | 91 | 是 | lcb_3487–lcb_3809 | 2024-10-12 → 2025-04-05 | hard 37／medium 54 | 12/91（13.2%） | lcb_3613、lcb_3763 | `g_e2q_off_lcb_qwenonly_20260902`、`g_r443_gemma_lcb` |
| **lcb v2** | `ops/gain/data/lcb_bank_v2.jsonl` | 120 | 是 | lcb_3026–lcb_3809 | 2023-08-26 → 2025-04-05 | hard 48／medium 72 | 12/120（10.0%） | lcb_3613、lcb_3763 | `g_r447_conform_lcb2`、`g_r449_eq5_lcb2` |
| **lcb v3** | `ops/gain/data/lcb_bank_v3.jsonl` | 189 | 是 | lcb_2728–lcb_3535 | 2023-05-07 → 2024-08-10 | hard 54／medium 135 | 12/189（6.3%） | 無 | `g_r449c_eq5_lcb3`、`g_r461_lcb3_three_arm`、`g_r461_off_gate_lcb3` |
| **MBPP+ v0.2.0** | `.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz`（**私有、不轉散布**） | 378 | 釘值 `af43697e8791c4c1…` | `mbppplus_*` | — | — | 官方 GT | — | 見下 |

- **版本關係**：v1 ⊂ v2（`True`）；v2 ∩ v3 = 0 題、聯集 309 題——v3 是刻意造出來的**樣本外**複製集，不是 v2 的超集。
- **v3 的警語**：v3 的 contest_date 全部不晚於 2024-08-10，**不能**宣稱晚於訓練截止；污染風險比 v1/v2 高（R460 C3 判定，vacant/codebench.py 有同一句）。
- **已知壞題**來源：`ops/gain/check_bank_precision.py::KNOWN_BAD`（白名單不是消音器：冒出新的照樣 FAIL）。
- **MBPP+ 為什麼不在版控**：官方 EvalPlus MBPP+ v0.2.0 包。索引**只記路徑與 codebench.py 裡的釘值**，不讀內容、不複製、不進版控。要驗就在本機比對 sha256（`vacant/codebench.py::EvalPlusMBPPLoader` 是 fail-closed 的）。刻意不記「這個 checkout 有沒有這個檔」——那是環境屬性不是資料屬性，寫進去會讓索引在不同 checkout 之間漂掉。（`.gitignore:18` 的 `.vacant-private/` 擋住整個目錄。釘值 2026-09-07（round457）本機實測 shasum 與釘值逐字相同。）**索引裡不含它的任何一個位元組。**
- **程序生成題族**（`vacant/codebench.py::_FAMILY_BUILDERS`）：boundary、off_by_one、empty_input、duplicate_values、negative_numbers、type_coercion。程序生成的六坑型族，題目**不落盤**——由 seed:family:idx 決定性生成，task_id = sha256('codebench:seed:family:idx')[:16]。沒有題庫檔可以 hash，重現靠 seed。

## 六、log 在哪、哪些進了版控

| 種類 | 檔名 | Mac repo | vacant-dev | 進 git | 備註 |
|---|---|---|---|---|---|
| run 資料檔 | `rows.jsonl / calls.jsonl / notes.jsonl / receipts_*.ndjson / receipts_*.pub.json / summary.json` | runs/<run>/ | ~/vacant/Vacant/runs/<run>/ | 是 | Mac repo 的 runs/ 全部進版控（HEAD 1043 檔）。calls.jsonl 是最大宗（單檔可到 11 MB），但也已在版控內。 |
| launcher log | `*.launch.log / *.log / *.backend.json / *.verdict.json` | runs/ 頂層（部分） | ~/vacant/Vacant/runs/ 頂層（全部） | 是 | **同步不完整**：最新幾個 run 的 launcher log 只在 vacant-dev，Mac repo 沒有——見 not_mirrored_to_mac。 |
| 迴圈 iteration log | `iter-NNNN.log（每輪一支）` | （不存在） | ~/vacant/logs/iter-*.log | 否 | 6352 支，佔 ~/vacant/logs/ 364 MB 的絕大部分。只在 vacant-dev，沒有備份，沒有保留政策。 |
| localagent 呼叫側錄 | `localagent-N.jsonl` | （不存在） | ~/vacant/logs/localagent-*.jsonl | 否 | 104 支。同上：只在 vacant-dev。 |
| 發射前探針 | `*_probe_N.json（conform / eq5_lcb2 / eq5_lcb3 / eq5_seed2 …）` | （不存在） | ~/vacant/logs/*_probe_*.json | 否 | 每次發射前對後端打的三通探針。是「這個 run 發射時後端活著」的唯一證據，但沒進版控。 |
| 分析工作目錄 | `_analysis_r*/（CRITERION.md、重算 json/txt、SELFTEST）` | runs/_analysis_r*/ | ~/vacant/Vacant/runs/_analysis_r*/ | 是 | 衍生物。不是原始資料，不可當證據引用。 |

- **vacant-dev**（`user1@100.124.254.83（vacant-dev）`）：`~/vacant/Vacant/runs/` 329 個項目／1.7G；`~/vacant/logs/` 6514 個檔／364M，時間跨度 2026-08-15 → 2026-09-06。（ssh 唯讀 `ls`（2026-09-07 本輪實測））
- **沒有同步回 Mac 的 14 個項目**：`_analysis_r503/`、`_preliminary/`、`off_probe_n60_20260902b/`、`s1_smoke/`、`g_r448_eq5_mbpp_seed2.launch.log`、`g_r448_eq5_mbpp_seed2.backend.json`、`g_r449_eq5_lcb2.launch.log`、`g_r449_eq5_lcb2.backend.json`、`g_r449c_eq5_lcb3.launch.log`、`g_r449c_eq5_lcb3.backend.json`、`g_r461_lcb3_three_arm.launch.log`、`s13_main.log`、`s13_reload.log`、`s13_selftest.log`
- vacant-dev 有 329 個項目、Mac repo 有 315 個，差的 14 個列在上面。**最近四個被稽核過的 run（r448／r449／r449c／r461）的 launcher log 與 backend.json 只存在於 vacant-dev**——那是「發射時用的是哪個後端」的唯一紀錄，掉了就補不回來。
- **保留政策**：沒有任何自動保留／輪替政策。Mac repo 這一側靠 git 保存（runs/ 全數進版控，113 MB）；vacant-dev 那一側（~/vacant/logs/ 364 MB、runs/ 1.7 G）**沒有備份**，機器沒了就沒了。要保留 iteration log 與發射探針，得另外做一次搬運——本輪只做編目，不動任何檔案。

## 七、與 RECORD_SPEC 的落差（不要跳過這一節）

G 系列 run 目錄（`g_*`）**不是** RECORD_SPEC §1 的證據包——它們沒有 manifest.json / ledger_events.jsonl / chain_verify.txt / anomalies.md / SHA256SUMS，用的是 gain_run.py 自己的 summary.json + rows/calls/notes 版面。符合 RECORD_SPEC 的只有 `blayer_*` 那幾個 B 層掃描。每個目錄的 `record_spec` 欄位逐項列出缺哪些。

目前符合 RECORD_SPEC §1 全部必要項的目錄：`blayer_1000_v2`、`blayer_1000_v3`。

