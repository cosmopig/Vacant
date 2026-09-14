# ow_01_csvjson — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**每一條隱藏驗收都要有 anchor**，指不到就刪掉那一條，
或把目標／契約改到指得到為止。反向也要查：目標敘述裡的每一句「客戶困擾」
至少要有一條隱藏驗收對應，對不到就代表那句話是**沒有被量到的需求**。

⚠ 本檔由**題目作者**填第一版；正式發射前要由**不是作者的代理**複核一次
（複核者不得是作者），複核結果落盤 `_fairness_review.json`。
目前狀態：**作者自填，未複核**。

| hidden_id | anchor_kind | anchor_quote（逐字） | derivation |
|---|---|---|---|
| `check_quoted_comma` | goal | "fields containing commas" | 客戶明說欄位裡會有逗號 ⇒ 引號包起來的欄位要吃得下逗號 |
| `check_quoted_newline` | goal | "fields containing line breaks" | 同上，換行版 |
| `check_escaped_quote` | contract | "`\"\"` inside a wrapped field means one literal `\"`" | 契約直接釘死這條規則 |
| `check_crlf` | contract | "Line endings `\\n`, `\\r\\n` and `\\r` all end a record." | 契約直接釘死 |
| `check_empty_input` | contract | "Input with no records at all … return `\"\"`" | 契約直接釘死 |
| `check_header_only` | contract | "input with only a header, both return `\"\"`" | 契約直接釘死 |
| `check_duplicate_header_last_wins` | contract | "If the header repeats a name, the **last** column with that name wins." | 契約直接釘死 |
| `check_field_count_mismatch_line_number` | goal | "they want to be told which line is broken" | 客戶要的是行號 ⇒ 行號必須是對的那一行（第 3 行不是第 2 行） |
| `check_unclosed_quote_raises` | contract | "or when a quoted field is never closed" | 契約把未閉合引號列為不合法 |
| `check_cli_invalid_exit_2_one_line` | contract | "**exactly one line** `line <N>: <reason>` goes to stderr … exit code 2" | 契約直接釘死 |
| `check_cli_stdout_only_jsonl` | contract | "the JSON Lines go to stdout, nothing goes to stderr, exit code 0" | 契約直接釘死；「一行一個物件」來自 goal 的 "one JSON object per row" |
| `check_utf8_non_ascii` | contract | "The file is read as UTF-8." | 契約直接釘死 |
| `check_no_trailing_newline_input` | goal | "files … that people edit by hand" | 手編檔案常常沒有結尾換行；契約的 "one JSON object per data row" 不容許最後一列被吃掉 |
| `check_all_empty_fields_row` | goal | "whole columns left blank" | 客戶明說整欄可能是空的 ⇒ 空欄要變成 `""` 不是被丟掉 |

## 反向檢查（目標裡的每一句困擾都有對應嗎）

| goal 裡的困擾 | 對應的隱藏驗收 |
|---|---|
| fields containing commas | `check_quoted_comma` |
| fields containing line breaks | `check_quoted_newline` |
| quotes inside quoted fields | `check_escaped_quote` |
| whole columns left blank | `check_all_empty_fields_row` |
| told which line is broken, not a stack trace | `check_field_count_mismatch_line_number`、`check_cli_invalid_exit_2_one_line` |
| one JSON object per row / JSON Lines | `check_cli_stdout_only_jsonl`、可見驗收 `check_basic_rows` |

## 可見 vs 隱藏不得逐字相同（§五-2 第 3 條）

可見的三條是 `name,age` ／ `city,note` ／ `a,b` 的 CLI 成功路徑；
隱藏的 14 條沒有一條用同一組 `(args, expected)`。
**可以測同一個需求的不同輸入**——那是設計，不是重複。
