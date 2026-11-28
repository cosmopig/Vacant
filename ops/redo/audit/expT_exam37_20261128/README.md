# 實驗 T ＋ exam37 稽核包（2026-11-28）

給獨立複核用（只讀推上去的檔）。不含家目錄路徑、主機位址、帳號；私有教材（維基百科修訂頁面、答案）不公開，只給 sha256。

## expT/（實驗 T，37 組 × 2 × 7 臂＝518 格）
- `expT_cells.csv`／`.json`：逐格。欄位有 set、rep、arm、host、ts（完成時間）、rounds_run、stop_reason、c0_flagged、sent_back、sent_back_fixed、n_lines、c0_correct、c0_filled、final_correct、final_filled、harm_c2w_or_d、harm_b2w、tokens、wall、haiku_*、chain_ok、報告的 sha256。
- `expT_lines.jsonl`：逐行（9,730 行）。欄位有前後狀態、錯誤類型、位數分桶、是否被標、是否送回、傷害旗標、前後值的 sha256（不放值）。
- `expT_chains/<組>__r<次>__<臂>/feedback_chain_hashed.ndjson`＋`feedback_chain.pub.json`：回饋鏈。每筆保留 seq、prev_hash、ts_ms、type、sig、entry_hash，payload 換成 `payload_sha256`（payload 含回饋文字，可能引用頁面值）。鏈的串接（prev_hash＝上一筆 entry_hash）可以公開驗；簽章要用私有原檔驗。`expT_chain_anchors.json` 列 stream_id、鏈頭、公鑰、`verify_chain`（518 條全部 true，在私有原檔上驗）。⚠ 每格用臨時金鑰。
- `expT_haiku.jsonl`：TE／TER 每格（148 格、120 次實際呼叫）的模型、prompt／回覆 sha256、token、花費、牆鐘、停止原因、送上去的行數、讀過的頁數。
- `expT_metrics_report.txt`／`expT_metrics.json`：`python3 ops/d2/expT_metrics.py <root>`（預註冊指定）的輸出。
- `expT_te_sensitivity_nonprereg.json`：`ops/d2/expT_te_sensitivity.py`，非預註冊。
- `expT_escape_calls.jsonl`：agent 越界讀取的逐筆結果，422 次呼叫，路徑去識別（只留組、次、臂、輪、類別與教材內的相對位置）。`expT_escape_summary.json`：彙總、被排除的對、兩個版本的敏感度（`ops/d2/expT_escape.py`，非預註冊）。
- 匯出腳本：`ops/d2/export_expT_audit.py`。計畫與預註冊：`ops/d2/plans/expT_qwen9b.json`（`prereg`）；修訂依據 `decisions/notes/NOTE_20261127_EXPERIMENT_T_N_CRITIQUE.md`。

### 結論數字對照（`decisions/conclusions/CONCLUSION_20261128_EXPT.md`）
| 結論裡的數字 | 來源 | 欄位／算法 |
|---|---|---|
| 各臂 (a)／(b)／(c)、token、牆鐘 | `expT_metrics_report.txt` 的 Per-Arm 表（也在 `expT_metrics.json` 的 `by_arm`） | (a) 是組平均；也可用 `expT_cells` 的 final_correct／n_lines 依組平均重算 |
| T 對 G／TB／TO、TE 對 TER 的差與區間 | `expT_metrics_report.txt` 的 Paired Comparisons；`expT_metrics.json` 的 `comparisons` | 以組為群集的 bootstrap，2,000 次，種子 20261127 |
| 判定 | `expT_metrics.json` 的 `readout` | 照 `prereg.frozen_readout` |
| 無法區分條件 | A 的 (a)；`expT_cells` 中 arm=T 且 sent_back>0 的格數（60/74） | |
| 錯誤類型 | `expT_metrics_report.txt` 的 Error Breakdown；`expT_lines` 的 before_etype／after_etype | |
| Haiku 花費、截斷 | `expT_haiku.jsonl` 的 cost_usd、stop_reason=max_tokens | |
| 敏感度（保留原值、排除截斷） | `expT_te_sensitivity_nonprereg.json` | 全部行合計，非組平均 |
| 越界讀取、排除後的敏感度 | `expT_escape_summary.json` | `summary`、`sensitivity.{all,a_exclude_any_escape_pairs,b_exclude_flags_future_pairs}` 的 `per_set_correct_prop_diff`／`_ci95` |
| fb-s11/r1 受污染 | `expT_cells`：A 的 c0_correct≠final_correct 只有這一對 | |

## exam37/（外部考卷先導，Colab L4 E4B）
- `exam37_part1_cells.*`（A／N3／GT／XM）、`exam37_part2_cells.*`（XMV／PB／XMT）：逐格。每格附每次嘗試的驗收數、逾時、隱藏評分、token、時間。XM、PB、XMT、XMV 各少 1–2 格，是考卷沒建成的題。
- `exam37_metrics.md`／`.json`：`python3 ops/redo/analysis/exam_metrics.py <part1> <part2> --reference-ok-json ops/redo/analysis/exam37_xm_reference_ok.json` 的輸出，和 `ops/redo/results/exam37/exam37_colab_e4b_summary.json` 一致（gt_minus_n3、verdict 相同）。
- `exam37_colab_e4b_part{1,2}_*.json`：越界讀取掃描（`ops/redo/analysis/scan_redo_leak.py`），兩部分讀到隱藏測試或考卷的呼叫都是 0。
- `*_token_timeout_by_arm_host.json`：token、逾時分臂（Colab 是單一 VM）。
- 計畫：`ops/redo/plans/exam37_colab_e4b_part1.json`、`exam37_colab_e4b_part2.json`。結論：`decisions/conclusions/CONCLUSION_20261127_EXAM37_COLAB_E4B.md`。

## 越界名單的版本（探索批次；2026-11-28）
- `expT_escape_calls.jsonl`／`expT_agent_runs.jsonl`：第一版（只看絕對路徑），45 次執行。
- `expT_escape_v2_runs.jsonl`：第二版掃描，108 次。
- `expT_escape_v3_runs.jsonl`：B47 修正後（加「別格 live 目錄」、不判還在跑的執行、`d2_private` 不配 `d2_private_live`），152 次。v2 的 108 次裡有 4 次在 v3 改判成不越界（sc-s01/r2 G 第 2 輪、sc-s15/r1 G 第 1 輪、sc-s15/r2 G 第 1 輪、sc-s17/r1 TO 第 2 輪；各只有 1 筆「路徑樣式＋教材輸出」）。原因：v2 的材料特徵 `d2_private` 會配到回傳裡 agent 自己的 `d2_private_live/...` 路徑，v3 改成 `d2_private(?!_live)`。所以 v3 只保留 v2 的 104 次。
- `expT_escape_v4_b48literal_runs.jsonl`：B48 字面規則，**200 次**（G 69、TO 83、TB 23、T 22、c0 3），每格附自己 live 目錄名的 HMAC（`own_live_hmac`；鍵只在執行方本機）。152 是「舊規則下的下界」。
- `expT_other_live_reads_revision.jsonl`：讀別格 live 目錄頁面的每一筆，判定讀到的是哪個修訂。
  - 方法：用 agent.log 的回傳文字，取長度 25 以上的片段、過半命中，比對教材各修訂的純文字。分「revision0／later_revision／undeterminable／read_failed」，不推定。
  - 被讀的別格目錄**現在都已不在**（磁碟事件或更早的清理刪除）。所以只能靠回傳文字判斷；**越界次數可確定，讀到的內容大多無法逐一驗證**。
- sc-s09/r1 G 第 2 輪：抓的是裸網域 `d2-sources.example`，經代理到來源伺服器、回 404，伺服器有紀錄，所以不算越界。

## 讀別格 live 目錄的修訂判定，第二版（2026-11-28；只讀已存紀錄；vacant-cloud 第四版名單核對後要求的四件）
程式：`ops/redo/analysis/expT_other_live_reads_v2.py`。第一版檔案（`expT_other_live_reads_revision.jsonl`，384 筆）原樣保留。

**方法改了什麼**
- 第一版用「≥25 字片段、過半命中」比對教材各修訂。各修訂大部分文字相同，所以 164 筆「0–4 全中」分不出修訂。
- 第二版改用 8 字詞 shingle：先要過半 shingle 命中，才算同一頁；再只看**某一修訂獨有**的 shingle，命中哪個修訂就判哪個。
- 同頁名比不上的，對 d2_private 底下**所有** realrev* 教材（含 index.html）比對。
- 第二版逐一計入參數裡的每個 `.html`（含 index.html、一次呼叫讀多頁），所以是 401 筆，不是 384 筆。

**`expT_other_live_reads_revision_v2.jsonl`（401 筆）**：
- later_revision：137
- read_failed：110
- processed_output_unmatched：74
- undeterminable_no_distinct_hit：36
- no_material_match：26
- other_set_page：9
- revision0：9
- **later_revision 全部是第 4 修訂**（137 筆，分布在 39 格）。探索批次本身的凍結頁是第 0 修訂（sha 對過），所以這些是讀到**後續修訂**的頁面。
  - 來源是以前 D2′ 批次放在 live 目錄裡的頁面（B47）。分臂：G 80、TO 38、T 11、TB 8。
- **other_set_page**：9 筆都是 index.html，對上的是足球 s10／s20 的索引頁；其中 8 筆是軟體／公司組的格讀的。
- **processed_output_unmatched**：參數有 grep／awk／sed／python 等處理，回傳不是頁面原文，比不上。
- **no_material_match**：回傳是 agent 自己印的摘要句（例如「Found 21 rows…」），或片段太短。
- **read_failed**：錯誤、空回傳，或指令本身語法錯誤。
- 這些判定**都已在排除名單裡**：69 格在每一版名單都整對排除，數字不變。改的是「讀到什麼」的描述。

**`expT_b51_positive_control_marks.json`**：B51 正控制在 69 次上的逐次標記（嘗試、得逞、規則），69/69 嘗試、69/69 得逞。

**`expT_pc_runs_without_page_reads.json`**：69 次裡有 16 次在讀頁清單裡沒有紀錄（vacant-cloud 數到 21，差異來自第二版也計入 index.html 與多頁讀取）。
- 原因：這些執行讀的不是 `.html` 頁面，而是**別格的 `ws/report.md`**（27 次，也就是別格 agent 的報告）、別格 `vh` 底下的 Vacant 紀錄物件與專案檔、`site/`、`cfg/` 目錄列表。
- 只有 1 次純粹是列目錄。讀頁清單只收 `.html`，所以這些不在清單裡。
