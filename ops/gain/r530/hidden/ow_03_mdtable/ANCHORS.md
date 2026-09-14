# ow_03_mdtable — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_03_mdtable/hidden/*.py` 的
檔頭自動產生，不要手改**——改了下一次投影就蓋掉。要改內容請改那些檔頭。

`gauge_r530.py --check` 已經把**正向**那一半變成可執行的擋門：每一條的
`anchor_quote` 都逐字比對過，在 `goal.md` 或 `contract.md` 裡找得到才算過。

⚠ **反向那一半機器做不到**（目標敘述裡每一句「客戶困擾」至少要有一條驗收對應）。
下面第二張表只能列出「有驗收指過去的目標句子」，列不出**沒有被任何驗收指到的句子**
——那正是反向擋門要找的東西。**複核者必須自己讀一次 `goal.md`**。
複核者不得是作者；目前狀態：**已複核**（2026-09-14，獨立代理，報告在
`ops/gain/r530/review/review_r530.md`；修正逐條在預註冊的附錄 AMEND1）。
⚠ **一檔一錨**：下面每一條只列它檔頭宣告的那一句。一條驗收實際上可能同時
量到目標的另一句（例如 AMEND1 補進 `ow_19`／`ow_20` 目標的那幾句），
這張表**描述不足**，不要當成覆蓋的完整清單。

## 一、正向：每一條隱藏驗收指回哪一句

| hidden_id | anchor_kind | anchor_quote（逐字） | derivation |
|---|---|---|---|
| `check_h01_cjk_display_width` | goal | some of the cells contain Chinese and Japanese text | when a column holds wide characters the rows only line up if width is |
| `check_h02_four_markers` | contract | A separator cell keeps the alignment markers it had | all four markers appear in one table and all four have to survive, |
| `check_h03_escaped_pipe` | goal | some are escaped | a backslash-escaped pipe is content, so the row still has two cells |
| `check_h04_pipe_in_inline_code` | goal | some sit inside inline code | a pipe between backticks belongs to the code span, so the row keeps |
| `check_h05_backtick_fence_untouched` | goal | some are inside fenced code blocks that happen to show a table | a table drawn inside a backtick fence is sample text, not structure, |
| `check_h06_tilde_fence_untouched` | contract | every line inside a fenced code block opened by three backticks or three | the tilde fence is the other spelling of the same thing and must be |
| `check_h07_missing_edge_pipes` | goal | some rows are missing the pipes at the start and end | a table written without edge pipes is still a table, and the output |
| `check_h08_ragged_rows` | goal | some rows have more cells than the header | the table grows to the widest row and the short rows are filled with |
| `check_h09_empty_cells` | goal | some cells are empty | an empty cell is still a column, padded to the column width and never |
| `check_h10_idempotent` | goal | running it twice must produce the same file as running it once | the pre-commit hook would loop forever otherwise, so the second pass |
| `check_h11_crlf_preserved` | goal | files saved on Windows must come back with the line endings they arrived | a CRLF document must still be CRLF afterwards, and must not have |
| `check_h12_no_table_at_all` | goal | A document with no table in it at all must come back byte for byte. | prose that happens to contain a pipe is not a table, because no |
| `check_h13_table_touching_prose` | goal | leaves everything that is not a table exactly as it was | with no blank line above or below, the neighbouring prose lines must |
| `check_h14_final_newline` | contract | the presence or absence of a final newline is unchanged | a document whose last line has no newline must not gain one, and one |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| A document with no table in it at all must come back byte for byte. | `check_h12_no_table_at_all` |
| files saved on Windows must come back with the line endings they arrived | `check_h11_crlf_preserved` |
| leaves everything that is not a table exactly as it was | `check_h13_table_touching_prose` |
| running it twice must produce the same file as running it once | `check_h10_idempotent` |
| some are escaped | `check_h03_escaped_pipe` |
| some are inside fenced code blocks that happen to show a table | `check_h05_backtick_fence_untouched` |
| some cells are empty | `check_h09_empty_cells` |
| some of the cells contain Chinese and Japanese text | `check_h01_cjk_display_width` |
| some rows are missing the pipes at the start and end | `check_h07_missing_edge_pipes` |
| some rows have more cells than the header | `check_h08_ragged_rows` |
| some sit inside inline code | `check_h04_pipe_in_inline_code` |

`contract` 錨點 3 條、`goal` 錨點 11 條。
