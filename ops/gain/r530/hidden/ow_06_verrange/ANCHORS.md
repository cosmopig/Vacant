# ow_06_verrange — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_06_verrange/hidden/*.py` 的
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
| `check_h01_ten_after_nine` | goal | They have been burned by "1.10" sorting before "1.9" | the minor and patch fields are numbers, so a two-digit field is |
| `check_h02_release_beats_prerelease` | goal | pre-release builds being treated as newer than the real thing | for the same three numbers the plain release is the newer of the two, |
| `check_h03_only_three_values` | contract | It returns exactly those three values. | the result is -1, 0 or 1 and nothing else, so a caller may compare it |
| `check_h04_numeric_identifiers_by_value` | goal | rc.2 comes after rc.1 | an identifier made of digits is a number, so rc.10 is newer than |
| `check_h05_text_identifiers_by_ascii` | goal | alpha comes before beta | identifiers that are not all digits sort the way their characters |
| `check_h06_digits_below_text` | contract | an all-digit identifier is older than one that is not | at the same position a numeric identifier loses to a textual one, so |
| `check_h07_longer_prerelease_wins` | goal | a pre-release with more parts is newer than the same pre-release with | when every shared identifier matches, the one carrying an extra |
| `check_h08_every_condition_holds` | goal | every condition has to hold | a three-condition requirement is only satisfied when all three are |
| `check_h09_spaces_around_conditions` | goal | sometimes with spaces around them | padding around a condition is not part of the version, so the spaced |
| `check_h10_all_six_operators` | contract | A condition is one of `>=`, `>`, `<=`, `<`, `==`, `!=` followed by a | each operator is checked on both sides of its own boundary, which is |
| `check_h11_prerelease_in_a_spec` | contract | Every condition has to hold for `satisfies` to return True. | the comparison used inside a condition is the same one `compare` |
| `check_h12_bad_version_rejected` | goal | A version string or a requirement they cannot make sense of has to be | a version that is not three numbers with an optional pre-release |
| `check_h13_bad_spec_rejected` | contract | a spec with an empty condition, and a condition with an unrecognised | a requirement whose operator is not one of the six, or that contains |
| `check_h14_bad_target_version_rejected` | goal | because a silent guess is how a bad build shipped last time | the version written inside a condition goes through the same check as |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| A version string or a requirement they cannot make sense of has to be | `check_h12_bad_version_rejected` |
| They have been burned by "1.10" sorting before "1.9" | `check_h01_ten_after_nine` |
| a pre-release with more parts is newer than the same pre-release with | `check_h07_longer_prerelease_wins` |
| alpha comes before beta | `check_h05_text_identifiers_by_ascii` |
| because a silent guess is how a bad build shipped last time | `check_h14_bad_target_version_rejected` |
| every condition has to hold | `check_h08_every_condition_holds` |
| pre-release builds being treated as newer than the real thing | `check_h02_release_beats_prerelease` |
| rc.2 comes after rc.1 | `check_h04_numeric_identifiers_by_value` |
| sometimes with spaces around them | `check_h09_spaces_around_conditions` |

`contract` 錨點 5 條、`goal` 錨點 9 條。
