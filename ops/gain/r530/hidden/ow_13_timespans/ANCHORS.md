# ow_13_timespans — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_13_timespans/hidden/*.py` 的
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
| `check_h01_touching_spans_join` | goal | two bookings where one ends exactly when the next begins are one busy | the end instant is not covered, so there is no gap between the two and |
| `check_h02_unordered_input` | goal | The periods arrive in no particular order | the same set of periods handed over in a different order gives the |
| `check_h03_zero_length_dropped` | goal | A period with no length is not a period at all. | a span whose start and end are the same covers nothing, so it neither |
| `check_h04_dates_are_midnight` | goal | Some systems send a date only and some send a time of day as well | a date on its own is the midnight that starts that day, so it joins |
| `check_h05_output_is_normalised` | contract | Every instant in a returned span is written `YYYY-MM-DDTHH:MM:SS`. | whatever form went in, what comes out is the long form, for merge and |
| `check_h06_hole_in_the_middle` | goal | a way to work out what is left once certain periods are taken out of it | a hole strictly inside a busy stretch leaves two stretches, one on |
| `check_h07_hole_swallows_everything` | contract | `subtract` returns the union of `spans` with every instant covered by | a hole that covers the whole stretch leaves nothing behind, and |
| `check_h08_holes_that_miss` | contract | `subtract` returns the union of `spans` | holes that fall entirely outside a stretch, or that only touch its |
| `check_h09_total_counts_overlap_once` | goal | counting time that two systems both reported only once | three heavily overlapping reports of the same hour total one hour, |
| `check_h10_reversed_span_is_reported` | goal | A period that ends before it starts is a bug in whoever sent it and has to | the reversed span raises from every entry point rather than being |
| `check_h11_unreadable_instant` | contract | and so does an instant that is not one of the two written forms | anything that is not one of the two shapes raises, including a shape |
| `check_h12_nothing_to_do` | contract | `merge` returns the union of the spans as the shortest list that covers it | no spans means no stretches and a total of zero, and subtracting from |
| `check_h13_seconds_resolution` | contract | `total_seconds` returns the number of whole seconds covered by the union, | a one-second stretch is one second, and a stretch across a day |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| A period that ends before it starts is a bug in whoever sent it and has to | `check_h10_reversed_span_is_reported` |
| A period with no length is not a period at all. | `check_h03_zero_length_dropped` |
| Some systems send a date only and some send a time of day as well | `check_h04_dates_are_midnight` |
| The periods arrive in no particular order | `check_h02_unordered_input` |
| a way to work out what is left once certain periods are taken out of it | `check_h06_hole_in_the_middle` |
| counting time that two systems both reported only once | `check_h09_total_counts_overlap_once` |
| two bookings where one ends exactly when the next begins are one busy | `check_h01_touching_spans_join` |

`contract` 錨點 6 條、`goal` 錨點 7 條。
