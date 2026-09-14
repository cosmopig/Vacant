# ow_02_ratelimit — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_02_ratelimit/hidden/*.py` 的
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
| `check_h01_left_open_boundary` | contract | an event counts while it falls in `(now - window_s, now]`, left open and | an event sitting exactly window_s ago is on the open side, so it no |
| `check_h02_right_closed_boundary` | contract | left open and right closed | a hair before the window expires the event is still inside, so the |
| `check_h03_zero_budget_blocks` | contract | `allow(key)` returns True when the number of counted events for that key | with a budget of zero no count is ever below it, so nothing is ever |
| `check_h04_zero_budget_wait_is_infinite` | contract | When `max_events` is 0 no wait ever helps, so `retry_after` returns | the answer to "how long until yes" has no finite value when the |
| `check_h05_keys_are_independent` | goal | counted separately per caller | one caller exhausting the budget must leave the others untouched. |
| `check_h06_wait_shrinks` | goal | that answer has to shrink as time passes rather than being a fixed guess | reading the wait at two later moments must give two smaller numbers, |
| `check_h07_wait_formula` | contract | it returns `leaving + window_s - now`, where `leaving` is the earliest | with a budget of two and events at 0 and 1, the first one leaving is |
| `check_h08_unseen_key` | contract | a key that has never been seen has no events | an unknown caller starts with a full budget and a wait of zero. |
| `check_h09_reset_one_caller` | goal | They also want to wipe the record for one caller | wiping one caller clears that caller's wait and nobody else's. |
| `check_h10_reset_everybody` | goal | or for everybody, without rebuilding the limiter | the no-argument wipe has to clear every caller at once, and the same |
| `check_h11_clock_rewound` | contract | A clock that moves backwards is not an error: events lying in the future | after the test clock is rewound past the recorded events, those |
| `check_h12_denial_does_not_extend` | contract | A denied call records nothing, so being denied ten times in a row leaves | hammering while blocked must not push the wait further out, and the |
| `check_h13_fractional_seconds` | goal | it deals in fractions of a second | a window shorter than a second has to behave exactly like a long |
| `check_h14_bad_configuration` | goal | they want a nonsensical configuration to fail at construction rather than | the error has to arrive from the constructor, before any call to |
| `check_h15_no_real_clock` | goal | the notion of now has to come from outside | if the real clock is unavailable the limiter must still work, which |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| They also want to wipe the record for one caller | `check_h09_reset_one_caller` |
| counted separately per caller | `check_h05_keys_are_independent` |
| it deals in fractions of a second | `check_h13_fractional_seconds` |
| or for everybody, without rebuilding the limiter | `check_h10_reset_everybody` |
| that answer has to shrink as time passes rather than being a fixed guess | `check_h06_wait_shrinks` |
| the notion of now has to come from outside | `check_h15_no_real_clock` |
| they want a nonsensical configuration to fail at construction rather than | `check_h14_bad_configuration` |

`contract` 錨點 8 條、`goal` 錨點 7 條。
