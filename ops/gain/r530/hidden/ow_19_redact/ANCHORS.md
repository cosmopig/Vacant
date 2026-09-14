# ow_19_redact — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_19_redact/hidden/*.py` 的
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
| `check_h01_all_three_kinds_go` | goal | after the pass, none of the secret text is anywhere in the result | each of the three kinds the client showed, in a fresh instance, is |
| `check_h02_ordinary_lines_untouched` | goal | everything in the line that is not a secret comes back exactly as it was | lines with no secret in them, including ones that merely look |
| `check_h03_second_pass_changes_nothing` | goal | running the pass on a line that has already been through it changes | for each kind, redacting twice gives the same result as redacting |
| `check_h04_the_rest_of_the_line_survives` | goal | because a person is going to read the line and needs the rest of it | after a secret is taken out, every other word of the line is still |
| `check_h05_repeats_both_go` | goal | a secret that appears twice in one line is gone both times | the same secret written twice in one line leaves no trace of either |
| `check_h06_the_count_is_usable` | goal | they can ask what was found in a line so a dashboard can count it, and a | a line holding three secrets reports three, a line holding one reports |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| a secret that appears twice in one line is gone both times | `check_h05_repeats_both_go` |
| after the pass, none of the secret text is anywhere in the result | `check_h01_all_three_kinds_go` |
| because a person is going to read the line and needs the rest of it | `check_h04_the_rest_of_the_line_survives` |
| everything in the line that is not a secret comes back exactly as it was | `check_h02_ordinary_lines_untouched` |
| running the pass on a line that has already been through it changes | `check_h03_second_pass_changes_nothing` |
| they can ask what was found in a line so a dashboard can count it, and a | `check_h06_the_count_is_usable` |

`contract` 錨點 0 條、`goal` 錨點 6 條。
