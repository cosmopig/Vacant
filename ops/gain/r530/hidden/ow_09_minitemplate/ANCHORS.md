# ow_09_minitemplate — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_09_minitemplate/hidden/*.py` 的
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
| `check_h01_values_become_text` | contract | converted with `str()` | numbers, booleans and None all arrive as their str() form rather |
| `check_h02_deep_paths` | goal | placeholders that can reach into nested data | a dotted name walks down several levels of dictionaries, and |
| `check_h03_missing_path_names_itself` | contract | raises `KeyError` whose single argument is the placeholder's name exactly | when the walk stops half way down, the error names the whole dotted |
| `check_h04_never_an_empty_string` | goal | silently producing an empty string is what bit them last time | every way of missing a value -- a top-level name, a path through a |
| `check_h05_item_itself` | goal | they need both the item itself and its fields | a list of plain values is reached through the lone dot, with the |
| `check_h06_outer_names_inside_a_block` | goal | they still need to reach the values that live outside the block | a name without a leading dot is looked up in the outer data even |
| `check_h07_empty_list_leaves_nothing` | goal | An empty list should leave nothing behind. | the block contributes no output at all, while the text around it is |
| `check_h08_comments_vanish` | goal | leave a note in the template that does not appear in the output | the comment contributes nothing, including when it sits inside a |
| `check_h09_literal_braces` | goal | their templates sometimes have to print two literal braces | the escaped form renders as the braces themselves, the backslash |
| `check_h10_unclosed_placeholder` | goal | a placeholder that is never closed | an opening brace pair with no closing one is a broken template and is |
| `check_h11_no_repeat_inside_a_repeat` | goal | a repeat inside a repeat | nesting the blocks is outside the language and is reported rather |
| `check_h12_repeat_over_a_non_list` | goal | a repeat over something that is not a list | a string or a dictionary is not a list, so repeating over one is a |
| `check_h13_stray_closing_tag` | goal | a closing repeat with nothing to close | a closing tag on its own, and an item reference outside any block, |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| An empty list should leave nothing behind. | `check_h07_empty_list_leaves_nothing` |
| a closing repeat with nothing to close | `check_h13_stray_closing_tag` |
| a placeholder that is never closed | `check_h10_unclosed_placeholder` |
| a repeat inside a repeat | `check_h11_no_repeat_inside_a_repeat` |
| a repeat over something that is not a list | `check_h12_repeat_over_a_non_list` |
| leave a note in the template that does not appear in the output | `check_h08_comments_vanish` |
| placeholders that can reach into nested data | `check_h02_deep_paths` |
| silently producing an empty string is what bit them last time | `check_h04_never_an_empty_string` |
| their templates sometimes have to print two literal braces | `check_h09_literal_braces` |
| they need both the item itself and its fields | `check_h05_item_itself` |
| they still need to reach the values that live outside the block | `check_h06_outer_names_inside_a_block` |

`contract` 錨點 2 條、`goal` 錨點 11 條。
