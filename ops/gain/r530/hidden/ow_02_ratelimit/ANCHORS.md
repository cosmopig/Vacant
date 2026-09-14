# ow_02_ratelimit — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。狀態：**作者自填，未複核**（複核者不得是作者）。

| hidden_id | anchor_kind | anchor_quote（逐字） | derivation |
|---|---|---|---|
| `check_boundary_event_exactly_window_old_has_fallen_out` | contract | "`now - window_s < t <= now`" | 左開 ⇒ 剛好等於 `now - window_s` 的事件已落出 |
| `check_boundary_event_just_inside_window_still_counts` | contract | 同上 | 右閉＋左開的另一側 |
| `check_max_events_zero_blocks_everything` | contract | "`max_events == 0` is valid and means nothing is ever allowed." ＋ "When nothing can ever be allowed, this is `float(\"inf\")`." | 契約直接釘死 |
| `check_three_keys_do_not_share_a_budget` | goal | "counted separately per caller" | 客戶明說 per caller |
| `check_retry_after_decreases_as_time_passes` | goal | "the caller wants to know how long to wait before trying again" | 「還要等多久」必須隨時間變短，否則它不是「還要等多久」 |
| `check_retry_after_is_zero_for_an_unseen_key` | contract | "`0.0` when `.allow(key)` would return `True` right now" | 沒看過的 key 現在就可以放行 |
| `check_retry_after_is_zero_while_still_allowed` | contract | 同上 | 同上，非空窗版 |
| `check_reset_one_key_only` | contract | "`.reset(key=None)` … `None` means forget every key" | 給了 key 就只忘那一個 |
| `check_reset_all_keys` | contract | 同上 | `None` 的那一半 |
| `check_clock_going_backwards_does_not_count_future_events` | contract | "An event whose timestamp is later than `now` … does not count either." | 契約直接釘死 |
| `check_blocked_calls_do_not_extend_the_window` | contract | "**It records an event only when it returns `True`.**" | 契約直接釘死；goal 的 "bursts from the same callers" 說明為什麼這件事重要 |
| `check_small_float_window` | goal | "configured by \"how long a window\"" | 窗長是浮點參數，0.1 秒與 10 秒走同一條路徑 |
| `check_window_not_positive_raises` | contract | "`window_s <= 0` … raises `ValueError`" | 契約直接釘死 |
| `check_negative_max_events_raises` | contract | "`max_events < 0` raises `ValueError`" | 契約直接釘死 |
| `check_allow_returns_a_real_bool` | contract | "`.allow(key: str) -> bool`" | 簽名寫的是 bool；回 0/1 會讓呼叫端的 `is True` 壞掉 |

## 反向檢查（目標裡的每一句困擾都有對應嗎）

| goal 裡的困擾 | 對應的驗收 |
|---|---|
| bursts from the same callers | `check_blocked_calls_do_not_extend_the_window`、可見 `check_allows_then_blocks` |
| how long a window / how many are allowed | `check_small_float_window`、`check_boundary_*` |
| counted separately per caller | `check_three_keys_do_not_share_a_budget`、可見 `check_keys_are_independent` |
| how long to wait before trying again | `check_retry_after_*`、可見 `check_retry_after_then_allowed_again` |
| tests must not sleep, "now" comes from outside | 全部 15 條都用注入的 `FakeClock`；**沒有一條 `time.sleep`** |

## 可見 vs 隱藏不得逐字相同

可見三條用 `(10.0, 2)`／`(10.0, 1)` 起點 `t=100`／`(5.0, 1)`；
隱藏 15 條沒有一條用同一組參數與同一條斷言。
