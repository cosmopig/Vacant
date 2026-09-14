# ow_14_statemachine — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_14_statemachine/hidden/*.py` 的
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
| `check_h01_history_starts_at_the_beginning` | goal | starting from where it began | before anything has happened the path already holds the starting |
| `check_h02_refusal_names_both_halves` | contract | it raises `ValueError` naming the state and the event | the message has to carry the state the order is in and the event that |
| `check_h03_refusal_leaves_no_trace` | goal | has to leave the order exactly where it was, in state and in record | after several refused events the state and the path are exactly what |
| `check_h04_can_matches_fire` | contract | `.can(event)` is True exactly when the current state's mapping has that | for every state and every event name in play, can() and whether fire() |
| `check_h05_self_transition_is_recorded` | goal | Something that puts an order back into the state it was already in still | an event whose target is the state it started from still appends to |
| `check_h06_history_is_a_copy` | contract | `.history()` hands back a copy: changing the returned list does not change | a caller who clears or appends to what they were given must not be |
| `check_h07_reset_starts_over` | goal | there has to be a way to start over | after reset the machine is in the starting state and its path is just |
| `check_h08_unknown_start_state` | goal | a starting state that is not on the whiteboard at all | the mistake is reported when the rules are handed over, so building |
| `check_h09_target_state_must_exist` | goal | Rules that point at a state nobody defined | an event leading somewhere that is not a state is caught at hand-over, |
| `check_h10_dead_end_states_are_fine` | contract | Every state the machine can be in appears as a key of `spec`, even when it | a state with an empty mapping is a legitimate end of the line: it |
| `check_h11_two_machines_do_not_share` | goal | They run the same rules for the next order | two machines built from the same rules keep their own state and their |
| `check_h12_long_path_in_order` | goal | They want the path an order took, in order | over a longer run through a cycle the path holds every state in the |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| Rules that point at a state nobody defined | `check_h09_target_state_must_exist` |
| Something that puts an order back into the state it was already in still | `check_h05_self_transition_is_recorded` |
| They run the same rules for the next order | `check_h11_two_machines_do_not_share` |
| They want the path an order took, in order | `check_h12_long_path_in_order` |
| a starting state that is not on the whiteboard at all | `check_h08_unknown_start_state` |
| has to leave the order exactly where it was, in state and in record | `check_h03_refusal_leaves_no_trace` |
| starting from where it began | `check_h01_history_starts_at_the_beginning` |
| there has to be a way to start over | `check_h07_reset_starts_over` |

`contract` 錨點 4 條、`goal` 錨點 8 條。
