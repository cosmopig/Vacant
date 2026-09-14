# ow_07_retrypolicy — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_07_retrypolicy/hidden/*.py` 的
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
| `check_h01_first_call_wins` | contract | `retry` returns the value of the first call that returns. | when nothing fails the helper calls once, returns that value and |
| `check_h02_exact_backoff_sequence` | contract | the helper waits `min(backoff_s * 2 ** (k - 1), max_backoff_s)` seconds | the first wait is the base delay itself, not the doubled one, so the |
| `check_h03_ceiling_applies` | goal | The delay must stop growing once it reaches a ceiling they set | once the doubling passes the ceiling every later wait is the ceiling |
| `check_h04_no_trailing_wait` | goal | they do not want to sit through a pause that leads nowhere | the number of waits is one fewer than the number of attempts, because |
| `check_h05_original_error_object` | goal | they want the original error, not something the helper wrapped around it | the object that comes out is the very object the last call raised, so |
| `check_h06_subclass_counts` | goal | A subclass of a listed error counts as that error. | listing the base class is enough, so a derived failure is retried |
| `check_h07_unrelated_error_escapes_at_once` | goal | A failure that is not worth retrying has to come straight back out, | an error outside the listed kinds ends the run after one call, with |
| `check_h08_empty_retry_on` | contract | An empty `retry_on` therefore retries nothing. | with no retryable kinds at all the first failure is the last one. |
| `check_h09_attempts_must_be_at_least_one` | goal | Asking for fewer than one attempt is a programming mistake and should be | the ValueError arrives without fn having run, for zero and for |
| `check_h10_single_attempt` | contract | `fn` is called at most `attempts` times. | one attempt means one call, no wait, and the failure straight out, |
| `check_h11_succeeds_on_the_last_attempt` | contract | `retry` returns the value of the first call that returns. | a call that only works on the final allowed attempt still returns its |
| `check_h12_sleep_is_the_only_waiting` | goal | Their tests must run instantly, so waiting has to be something they can | with the real clock made unavailable the helper still has to work, |
| `check_h13_several_listed_kinds` | contract | An exception that is not an instance of any type in `retry_on` is raised | with two kinds listed, both are retried and a third one still escapes |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| A failure that is not worth retrying has to come straight back out, | `check_h07_unrelated_error_escapes_at_once` |
| A subclass of a listed error counts as that error. | `check_h06_subclass_counts` |
| Asking for fewer than one attempt is a programming mistake and should be | `check_h09_attempts_must_be_at_least_one` |
| The delay must stop growing once it reaches a ceiling they set | `check_h03_ceiling_applies` |
| Their tests must run instantly, so waiting has to be something they can | `check_h12_sleep_is_the_only_waiting` |
| they do not want to sit through a pause that leads nowhere | `check_h04_no_trailing_wait` |
| they want the original error, not something the helper wrapped around it | `check_h05_original_error_object` |

`contract` 錨點 6 條、`goal` 錨點 7 條。
