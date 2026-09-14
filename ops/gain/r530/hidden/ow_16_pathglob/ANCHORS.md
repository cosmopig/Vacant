# ow_16_pathglob — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_16_pathglob/hidden/*.py` 的
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
| `check_h01_star_does_not_cross_a_slash` | goal | A star should stay inside one directory level | a star in the middle of a pattern cannot swallow a slash, so a deeper |
| `check_h02_question_mark_is_one_character` | goal | They also need a single-character wildcard | exactly one character, no more and no fewer, and never the separator. |
| `check_h03_double_star_may_swallow_nothing` | goal | that has to work even when there is nothing underneath at all | the double star standing for zero segments is the case an |
| `check_h04_double_star_in_the_middle` | contract | A segment that is exactly `**` matches zero or more whole segments. | with a literal segment on each side the double star has to stretch to |
| `check_h05_class_and_range` | goal | a way to say "one of these characters" or "any character in this range" | a listed set and a range each match exactly one character, and a |
| `check_h06_negated_class` | goal | including the negative form | a leading exclamation mark inside the brackets flips the class, and it |
| `check_h07_whole_path_only` | goal | A pattern has to match the whole path: half a match is not a match. | a pattern that fits the start, or the end, or the middle of a path is |
| `check_h08_metacharacters_are_literal` | goal | Characters that mean something to a regular expression -- a dot, a plus, a | a dot in a pattern matches only a dot, and a plus or a parenthesis in |
| `check_h09_selection_keeps_file_order` | goal | The answer comes back in the order the files were listed, with nothing | two patterns that pick overlapping sets, written in the opposite order |
| `check_h10_exclamation_removes` | goal | a pattern beginning with an exclamation mark removes what the earlier ones | the removal applies to what has already been chosen, and leaves the |
| `check_h11_later_pattern_puts_it_back` | goal | and a later pattern can put something back | patterns are read left to right, so an add after a removal wins, and |
| `check_h12_every_pattern_is_checked` | contract | `select` checks every pattern it is given, whether or not anything matches | a malformed pattern raises even when the file list is empty, and even |
| `check_h13_nothing_selected` | contract | A plain pattern adds every path that matches it | patterns that match nothing give an empty answer, and an empty list of |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| A pattern has to match the whole path: half a match is not a match. | `check_h07_whole_path_only` |
| A star should stay inside one directory level | `check_h01_star_does_not_cross_a_slash` |
| Characters that mean something to a regular expression -- a dot, a plus, a | `check_h08_metacharacters_are_literal` |
| The answer comes back in the order the files were listed, with nothing | `check_h09_selection_keeps_file_order` |
| They also need a single-character wildcard | `check_h02_question_mark_is_one_character` |
| a pattern beginning with an exclamation mark removes what the earlier ones | `check_h10_exclamation_removes` |
| a way to say "one of these characters" or "any character in this range" | `check_h05_class_and_range` |
| and a later pattern can put something back | `check_h11_later_pattern_puts_it_back` |
| including the negative form | `check_h06_negated_class` |
| that has to work even when there is nothing underneath at all | `check_h03_double_star_may_swallow_nothing` |

`contract` 錨點 3 條、`goal` 錨點 10 條。
