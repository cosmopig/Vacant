# ow_04_layerconf — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_04_layerconf/hidden/*.py` 的
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
| `check_h01_env_beats_file` | contract | Precedence is env over file over default. | when all three name the same setting the environment value is the one |
| `check_h02_file_beats_default` | contract | Precedence is env over file over default. | with no environment variable in play the file still has to beat the |
| `check_h03_sections_make_dotted_keys` | goal | Their settings file is grouped into sections | a key under [db] is the setting db.something, and a key written |
| `check_h04_comments_and_blanks` | goal | half of it is comments | comment lines and blank lines carry no setting, and a comment sitting |
| `check_h05_boolean_spellings` | contract | A `bool` accepts `true`, `false`, `1`, `0`, `yes` and `no` without regard | all six words, in mixed case, have to land on the right boolean. |
| `check_h06_unconvertible_boolean` | goal | a value that cannot be turned into the right kind of thing must fail | a word that is not one of the accepted boolean spellings must raise |
| `check_h07_unconvertible_number` | contract | A value that cannot be converted raises `ValueError`. | a word where an integer is expected is a ValueError, from the file |
| `check_h08_env_name_shape` | contract | After the prefix, `__` stands for `.` and the rest is lowercased, so | the capitals-and-underscores spelling has to map onto the dotted key, |
| `check_h09_unrelated_env_ignored` | goal | most of which have nothing to do with this program | environment variables without the prefix must not touch the settings, |
| `check_h10_unknown_keys_ignored` | goal | A typo in a setting name should be ignored rather than quietly adding a | a misspelled key in the file or the environment changes nothing and |
| `check_h11_unknown_key_raises` | contract | `get` and `source` raise `KeyError` for a key that is not in `defaults`. | asking about a setting that does not exist is a mistake worth |
| `check_h12_no_file_at_all` | goal | Sometimes there is no settings file at all. | passing None for the file must behave exactly like passing an empty |
| `check_h13_value_with_equals_sign` | goal | Some of their values contain an equals sign. | only the first equals sign separates the key from the value, so the |
| `check_h14_whitespace_and_stray_lines` | contract | A line that is neither of those and contains no `=` is ignored. The value | padding around the key and the value disappears, and a junk line with |
| `check_h15_defaults_fix_the_key_set` | contract | `defaults` fixes both the set of keys and the type of each value. | as_dict() has exactly the default keys, no more and no fewer, and a |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| A typo in a setting name should be ignored rather than quietly adding a | `check_h10_unknown_keys_ignored` |
| Some of their values contain an equals sign. | `check_h13_value_with_equals_sign` |
| Sometimes there is no settings file at all. | `check_h12_no_file_at_all` |
| Their settings file is grouped into sections | `check_h03_sections_make_dotted_keys` |
| a value that cannot be turned into the right kind of thing must fail | `check_h06_unconvertible_boolean` |
| half of it is comments | `check_h04_comments_and_blanks` |
| most of which have nothing to do with this program | `check_h09_unrelated_env_ignored` |

`contract` 錨點 8 條、`goal` 錨點 7 條。
