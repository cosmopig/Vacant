# ow_05_router — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_05_router/hidden/*.py` 的
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
| `check_h01_literal_beats_parameter` | goal | they want the same answer every time -- the more specific one | a literal segment is more specific than a named one at the same |
| `check_h02_parameter_beats_catch_all` | contract | Rank the segments literal, then `{name}`, then `{name:*}` | a single-segment parameter outranks a rest-of-path capture at the |
| `check_h03_leftmost_difference_decides` | contract | compare the two patterns segment by segment from the left: the first | both patterns have one literal and one parameter, so a rule that |
| `check_h04_literal_prefix_beats_bare_catch_all` | contract | the first position at which they differ picks the winner | at the first segment one pattern has a literal and the other a |
| `check_h05_registration_order_irrelevant` | goal | the answer must not depend on that order | every permutation of the same three routes must answer the same way |
| `check_h06_same_pattern_twice` | contract | Two patterns that differ only in their parameter names are the same | the parameter name is not part of what makes a pattern distinct, so |
| `check_h07_several_named_pieces` | goal | pulling out the named pieces of the path along the way | every parameter in the pattern appears in the returned mapping, under |
| `check_h08_catch_all_keeps_slashes` | goal | a pattern that swallows the rest of the path for serving files | the captured remainder keeps its slashes, so a nested file path comes |
| `check_h09_parameter_rejects_empty_segment` | contract | `{name}` matches exactly one segment, never spans a `/`, and never matches | a trailing slash leaves an empty segment, which a named segment must |
| `check_h10_parameter_does_not_span_slash` | contract | never spans a `/` | a two-segment tail cannot be swallowed by one named segment, so the |
| `check_h11_nobody_owns_it` | goal | A path that belongs to nobody | with routes registered but none fitting, the answer is None rather |
| `check_h12_matched_with_no_named_pieces` | goal | has to be distinguishable from a path that matched with no named pieces | an all-literal pattern returns an empty mapping, which must not be |
| `check_h13_catch_all_must_be_last` | contract | may only appear as the last segment | a rest-of-path capture in the middle is a malformed pattern and is |
| `check_h14_malformed_patterns` | goal | they want a mistake in a pattern to be reported when the route is | every malformed shape raises from add, before any path is matched. |
| `check_h15_catch_all_needs_something` | contract | must not be empty | the rest-of-path capture needs at least one character, so the bare |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| A path that belongs to nobody | `check_h11_nobody_owns_it` |
| a pattern that swallows the rest of the path for serving files | `check_h08_catch_all_keeps_slashes` |
| has to be distinguishable from a path that matched with no named pieces | `check_h12_matched_with_no_named_pieces` |
| pulling out the named pieces of the path along the way | `check_h07_several_named_pieces` |
| the answer must not depend on that order | `check_h05_registration_order_irrelevant` |
| they want a mistake in a pattern to be reported when the route is | `check_h14_malformed_patterns` |
| they want the same answer every time -- the more specific one | `check_h01_literal_beats_parameter` |

`contract` 錨點 8 條、`goal` 錨點 7 條。
