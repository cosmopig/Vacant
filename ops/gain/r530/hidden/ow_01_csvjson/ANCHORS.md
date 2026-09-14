# ow_01_csvjson — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_01_csvjson/hidden/*.py` 的
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
| `check_h01_comma_in_quotes` | goal | fields containing commas | a hand-edited field that holds commas must arrive as one value, not several. |
| `check_h02_newline_in_quotes` | goal | fields containing line breaks | a line break inside a quoted field belongs to the value, so the record |
| `check_h03_doubled_quote` | contract | inside such a field a doubled `""` stands for one literal double quote | the escape has to collapse to exactly one quote character. |
| `check_h04_blank_column` | goal | whole columns left blank | a column nobody filled in yields the empty string on every row, and a |
| `check_h05_repeated_header` | contract | When a header name repeats, the last occurrence wins. | two columns called the same thing collapse to one key holding the |
| `check_h06_crlf` | contract | `"\n"` and `"\r\n"` are both accepted as line endings and neither survives | a file last saved on Windows must not leave a stray carriage return |
| `check_h07_non_ascii` | goal | Some of the data is not ASCII and has to survive the trip unchanged. | non-ASCII values must come back out identical, whatever escaping the |
| `check_h08_line_number_of_bad_row` | contract | `N` is the 1-based line number on which the offending record starts and the | the reported number must point at the record that is actually wrong, |
| `check_h09_unclosed_quote` | contract | Invalid means: a record whose field count differs from the header, or an | a quote that is never closed is an error, not a value that runs to the |
| `check_h10_exit_code_is_the_signal` | goal | success and failure have to be distinguishable without reading the output | a shell script only sees the exit status, so it has to differ between |
| `check_h11_stdout_not_polluted` | goal | the converted data must not be polluted by chatter | stdout carries the data and nothing else, and on failure it carries |
| `check_h12_no_data_rows` | contract | When there are no data rows the result is the empty string. | an empty file and a header-only file both have zero data rows. |
| `check_h13_missing_final_newline` | contract | The input may or may not end with a final newline; that makes no | the same data with and without a trailing newline must convert |
| `check_h14_one_object_per_line` | contract | one JSON object per data row, each object on its own line | three data rows give three lines, each of which parses on its own as |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| Some of the data is not ASCII and has to survive the trip unchanged. | `check_h07_non_ascii` |
| fields containing commas | `check_h01_comma_in_quotes` |
| fields containing line breaks | `check_h02_newline_in_quotes` |
| success and failure have to be distinguishable without reading the output | `check_h10_exit_code_is_the_signal` |
| the converted data must not be polluted by chatter | `check_h11_stdout_not_polluted` |
| whole columns left blank | `check_h04_blank_column` |

`contract` 錨點 8 條、`goal` 錨點 6 條。
