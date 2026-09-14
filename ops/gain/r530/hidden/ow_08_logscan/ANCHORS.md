# ow_08_logscan — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_08_logscan/hidden/*.py` 的
檔頭自動產生，不要手改**——改了下一次投影就蓋掉。要改內容請改那些檔頭。

`gauge_r530.py --check` 已經把**正向**那一半變成可執行的擋門：每一條的
`anchor_quote` 都逐字比對過，在 `goal.md` 或 `contract.md` 裡找得到才算過。

⚠ **反向那一半機器做不到**（目標敘述裡每一句「客戶困擾」至少要有一條驗收對應）。
下面第二張表只能列出「有驗收指過去的目標句子」，列不出**沒有被任何驗收指到的句子**
——那正是反向擋門要找的東西。**複核者必須自己讀一次 `goal.md`**。
複核者不得是作者；目前狀態：**作者自填，未複核**。

## 一、正向：每一條隱藏驗收指回哪一句

| hidden_id | anchor_kind | anchor_quote（逐字） | derivation |
|---|---|---|---|
| `check_h01_five_hundreds_only` | goal | Failed means the server's own fault, the five-hundreds; a client sending | a run of four-hundreds contributes nothing to the error share, while |
| `check_h02_error_rate_rounded` | contract | rounded to four decimal places | one failure in three is 0.3333 exactly, not the full repeating float. |
| `check_h03_p50_nearest_rank` | contract | the p-th percentile of n sorted values is the one at 1-based position | with four values the median rank is ceil(2.0) = 2, which is the |
| `check_h04_p95_nearest_rank` | goal | the unlucky tail | with four values the 95th percentile rank is ceil(3.8) = 4, the |
| `check_h05_single_sample` | contract | Percentiles are nearest-rank | with one value the rank is 1 for every percentile, so both numbers are |
| `check_h06_busiest_first` | goal | They want the busiest endpoints at the top | the ordering is by request count from large to small, whatever order |
| `check_h07_tie_broken_by_path` | goal | when two are equally busy they want the order to be the same every time | equal counts are separated by the path in ordinary string order, so |
| `check_h08_wrong_field_count` | contract | A line is bad when it does not have exactly five fields | too few fields and too many fields are both bad, and neither adds a |
| `check_h09_non_integer_fields` | contract | when `STATUS` or `MS` is not a run of digits with an optional leading `-` | a status or a duration that is not an integer makes the line |
| `check_h10_bad_timestamp` | contract | or when the timestamp is not ISO8601 | a timestamp that is not a real date-time makes the line unusable even |
| `check_h11_bad_lines_are_reported` | goal | They also want to know how many lines were unusable | the count of unusable lines is part of the answer and keeps rising |
| `check_h12_blank_lines_are_nothing` | goal | Blank lines are just noise from the rotation script and should not count | an empty or whitespace-only line is neither a request nor a bad line, |
| `check_h13_trailing_newlines` | contract | Any trailing newline is not part of the line. | lines read straight from a file keep their newline, which must not |
| `check_h14_result_shape` | contract | The result has exactly this shape | the three top-level keys and the five per-endpoint keys are fixed, |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| Blank lines are just noise from the rotation script and should not count | `check_h12_blank_lines_are_nothing` |
| Failed means the server's own fault, the five-hundreds; a client sending | `check_h01_five_hundreds_only` |
| They also want to know how many lines were unusable | `check_h11_bad_lines_are_reported` |
| They want the busiest endpoints at the top | `check_h06_busiest_first` |
| the unlucky tail | `check_h04_p95_nearest_rank` |
| when two are equally busy they want the order to be the same every time | `check_h07_tie_broken_by_path` |

`contract` 錨點 8 條、`goal` 錨點 6 條。
