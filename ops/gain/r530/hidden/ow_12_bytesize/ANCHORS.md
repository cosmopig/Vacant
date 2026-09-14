# ow_12_bytesize — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_12_bytesize/hidden/*.py` 的
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
| `check_h01_two_meanings_of_kb` | goal | the two meanings of "KB" | the i spelling steps by 1024 and the plain spelling by 1000, so the |
| `check_h02_unit_case_does_not_matter` | goal | People write the unit in whatever case they feel like | every casing of a unit reads as the same unit. |
| `check_h03_space_is_optional` | goal | sometimes leave a space before it and sometimes not | none, one or several spaces between the number and the unit all read |
| `check_h04_no_unit_is_bytes` | goal | A size with no unit at all is a count of bytes. | a bare number and the same number with the byte unit in either case |
| `check_h05_fraction_is_dropped` | goal | the fraction is dropped rather than rounded up | a value whose product has a fraction truncates downward, so 2.9 |
| `check_h06_largest_unit_below_the_step` | contract | The unit chosen is the largest one that leaves the number below the step | each size lands in the unit whose number is at least 1 and less than |
| `check_h07_trailing_zero_is_kept` | goal | keep one decimal place even when it is a round number | a size that lands on a whole number of units still shows the decimal |
| `check_h08_bytes_are_whole_things` | goal | except for plain bytes, which are whole things and should look like it | anything below one step prints as an integer with the byte unit and |
| `check_h09_decimal_family` | contract | It uses the 1024 units when `binary` is true and the 1000 units otherwise. | with the flag turned off the steps are thousands and the unit names |
| `check_h10_above_the_largest_unit` | goal | Sizes larger than the biggest unit they use should still print, rather | beyond a terabyte the unit stops changing and the number grows past |
| `check_h11_round_trip` | goal | numbers that come back out different from the way they went in | for a size the printed form represents exactly, reading it back gives |
| `check_h12_negative_is_refused` | goal | a negative size | a minus sign is refused when reading and when printing, rather than |
| `check_h13_other_refusals` | goal | an empty setting, a unit nobody has heard of, two units in one string | each named refusal is checked on its own, including a string that has |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| A size with no unit at all is a count of bytes. | `check_h04_no_unit_is_bytes` |
| People write the unit in whatever case they feel like | `check_h02_unit_case_does_not_matter` |
| Sizes larger than the biggest unit they use should still print, rather | `check_h10_above_the_largest_unit` |
| a negative size | `check_h12_negative_is_refused` |
| an empty setting, a unit nobody has heard of, two units in one string | `check_h13_other_refusals` |
| except for plain bytes, which are whole things and should look like it | `check_h08_bytes_are_whole_things` |
| keep one decimal place even when it is a round number | `check_h07_trailing_zero_is_kept` |
| numbers that come back out different from the way they went in | `check_h11_round_trip` |
| sometimes leave a space before it and sometimes not | `check_h03_space_is_optional` |
| the fraction is dropped rather than rounded up | `check_h05_fraction_is_dropped` |
| the two meanings of "KB" | `check_h01_two_meanings_of_kb` |

`contract` 錨點 2 條、`goal` 錨點 11 條。
