# ow_10_dedupe — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_10_dedupe/hidden/*.py` 的
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
| `check_h01_order_is_first_appearance` | goal | in the order things first appeared | the position of a key in the result is decided by its first |
| `check_h02_first_is_the_default` | contract | The default is `"first"`. | calling without a policy behaves exactly like asking for the first |
| `check_h03_last_replaces_wholesale` | contract | `"last"` -- the latest copy's values are kept | the later copy replaces the earlier one entirely, so a field only the |
| `check_h04_merge_takes_the_last_filled` | contract | field by field, the value of the last copy that both has the field and | across three copies each field independently takes the latest real |
| `check_h05_merge_gains_new_fields` | contract | `"merge"` -- field by field | a field that only the later copy carries is added to the merged |
| `check_h06_none_never_overwrites` | goal | A field that is present but empty of meaning counts as not filled in. | a later copy carrying None for a field must leave the real value that |
| `check_h07_composite_key_order` | contract | a list of field names making a composite key whose parts are compared in | two records are the same only when every named part agrees, so |
| `check_h08_composite_parts_do_not_run_together` | goal | two records that agree on only one of them are not the same thing | two records whose key parts would glue into the same text are still |
| `check_h09_missing_key_field` | goal | A record that does not carry the field they are keying on is a data | the missing field raises, and the error names the field, for the |
| `check_h10_unknown_policy` | goal | Asking for a way of resolving disagreements that does not exist is a | anything outside the three names raises, including near misses and |
| `check_h11_inputs_are_left_alone` | goal | nothing they handed in may come back changed | after every policy the original dictionaries hold exactly what they |
| `check_h12_nothing_to_do` | contract | The result holds one record per distinct key value | an empty list gives an empty list, and a list with no repeats comes |
| `check_h13_key_values_of_other_types` | contract | `key` is a field name | the key value is whatever the field holds, so numbers and None are |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| A field that is present but empty of meaning counts as not filled in. | `check_h06_none_never_overwrites` |
| A record that does not carry the field they are keying on is a data | `check_h09_missing_key_field` |
| Asking for a way of resolving disagreements that does not exist is a | `check_h10_unknown_policy` |
| in the order things first appeared | `check_h01_order_is_first_appearance` |
| nothing they handed in may come back changed | `check_h11_inputs_are_left_alone` |
| two records that agree on only one of them are not the same thing | `check_h08_composite_parts_do_not_run_together` |

`contract` 錨點 7 條、`goal` 錨點 6 條。
