# ow_15_tomlsub — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_15_tomlsub/hidden/*.py` 的
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
| `check_h01_five_kinds` | goal | The values they use are text, whole numbers, decimals, true and false, and | each kind arrives as its own Python type, and true is a boolean rather |
| `check_h02_escapes_in_text` | goal | Text sometimes has to contain quotes, tabs and line breaks, written with a | the four escapes turn into the characters they stand for, and nothing |
| `check_h03_hash_inside_text` | goal | a `#` inside a piece of text is not a comment | a hash inside quotes belongs to the value, while a hash after the |
| `check_h04_nested_headings` | goal | headings can be nested with dots | a dotted heading puts the names one level deeper, and the parent group |
| `check_h05_names_before_the_first_heading` | contract | Names before the first heading live at the top level. | a name written above every heading stays at the top, and the same name |
| `check_h06_mixed_list_is_a_mistake` | goal | A list that mixes kinds is a mistake. | a list holding two different kinds raises, and the message says which |
| `check_h07_duplicate_name` | goal | The same setting written twice in one group | the second appearance raises on its own line, while the same name in |
| `check_h08_duplicate_heading` | goal | or the same heading opened twice | reopening a group raises on the line that reopened it, even when the |
| `check_h09_line_numbers_on_every_mistake` | goal | Every mistake has to say which line it is on | several different kinds of malformed line each report the line they |
| `check_h10_round_trip_data` | goal | Writing the data out and reading it back has to give the same data | data holding every kind, including text that needs escaping and a |
| `check_h11_round_trip_text` | goal | writing out what was just read has to give the same text | written form is canonical, so a second pass through parse and dumps |
| `check_h12_written_order` | contract | `dumps` writes the top-level names first in name order, then each heading | whatever order the dictionary was built in, the written form is in |
| `check_h13_unwritable_data` | contract | `dumps` raises `ValueError` for data it cannot write | each of the four named cases raises rather than producing text that |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| A list that mixes kinds is a mistake. | `check_h06_mixed_list_is_a_mistake` |
| Every mistake has to say which line it is on | `check_h09_line_numbers_on_every_mistake` |
| Text sometimes has to contain quotes, tabs and line breaks, written with a | `check_h02_escapes_in_text` |
| The same setting written twice in one group | `check_h07_duplicate_name` |
| The values they use are text, whole numbers, decimals, true and false, and | `check_h01_five_kinds` |
| Writing the data out and reading it back has to give the same data | `check_h10_round_trip_data` |
| a `#` inside a piece of text is not a comment | `check_h03_hash_inside_text` |
| headings can be nested with dots | `check_h04_nested_headings` |
| or the same heading opened twice | `check_h08_duplicate_heading` |
| writing out what was just read has to give the same text | `check_h11_round_trip_text` |

`contract` 錨點 3 條、`goal` 錨點 10 條。
