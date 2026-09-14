# ow_11_reflow — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_11_reflow/hidden/*.py` 的
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
| `check_h01_wide_characters_count_two` | goal | Chinese takes two columns per character in their terminal | a line of Chinese is only within the width when each character is |
| `check_h02_break_between_wide_characters` | goal | it can be broken between any two characters without a space appearing at | a Chinese run with no spaces in it still wraps, and putting the lines |
| `check_h03_paragraph_indent_carried_down` | goal | Their notes have indented blocks | a paragraph that started indented keeps that indentation on every one |
| `check_h04_numbered_bullets` | contract | or digits followed by `. ` | a numbered item hangs under its text, so the continuation indent is |
| `check_h05_star_bullets_and_nesting_indent` | contract | a bullet marker -- `- `, `* `, or digits followed by `. ` | the star spelling behaves like the dash, and an indented bullet hangs |
| `check_h06_each_bullet_is_its_own` | goal | Each bullet in a list is its own thought and must not be glued onto the | three short bullets on three lines come back as three bullets, not as |
| `check_h07_blank_runs_kept` | goal | however many there were is however many they want back | a run of three blank lines stays three blank lines, and the |
| `check_h08_fence_contents_untouched` | goal | code fenced off with backticks that must not be touched | every line between the fences comes back byte for byte, including |
| `check_h09_long_piece_sticks_out` | goal | they would rather it stick out than be chopped in half | a single long run with no spaces occupies a line of its own, whole, |
| `check_h10_bad_width_refused` | goal | A width that makes no sense should be refused. | zero and negative widths raise rather than looping or returning |
| `check_h11_whitespace_collapses` | contract | runs of spaces and tabs separate words and are replaced by a single space | doubled spaces and tabs between words become one space each, and no |
| `check_h12_final_newline` | contract | The presence or absence of a final newline is unchanged. | a note without a final newline must not gain one, and one with a |
| `check_h13_mixed_scripts_in_one_word` | contract | A break may fall between any two characters when at least one of them is | a run that mixes Latin letters and Chinese may break where the two |
| `check_h14_bullet_after_paragraph` | goal | bullet lists whose continuation lines should line up under the text and | a bullet that follows a plain paragraph with no blank line between |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| A width that makes no sense should be refused. | `check_h10_bad_width_refused` |
| Chinese takes two columns per character in their terminal | `check_h01_wide_characters_count_two` |
| Each bullet in a list is its own thought and must not be glued onto the | `check_h06_each_bullet_is_its_own` |
| Their notes have indented blocks | `check_h03_paragraph_indent_carried_down` |
| bullet lists whose continuation lines should line up under the text and | `check_h14_bullet_after_paragraph` |
| code fenced off with backticks that must not be touched | `check_h08_fence_contents_untouched` |
| however many there were is however many they want back | `check_h07_blank_runs_kept` |
| it can be broken between any two characters without a space appearing at | `check_h02_break_between_wide_characters` |
| they would rather it stick out than be chopped in half | `check_h09_long_piece_sticks_out` |

`contract` 錨點 5 條、`goal` 錨點 9 條。
