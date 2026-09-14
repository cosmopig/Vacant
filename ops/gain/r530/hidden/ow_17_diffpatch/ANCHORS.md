# ow_17_diffpatch — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_17_diffpatch/hidden/*.py` 的
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
| `check_h01_one_piece_per_place` | goal | one per place that changed, so that a reviewer sees the two lines that | two edits far apart give two pieces, each holding only its own changed |
| `check_h02_no_unchanged_lines_at_the_edges` | goal | A piece must not carry lines that did not change: not at its start, not at | across several shapes of edit, no piece with lines on both sides ever |
| `check_h03_pieces_are_ordered_and_apart` | contract | ordered by `start`, with at least one unchanged line between the end of | over a version with several scattered edits the pieces come back in |
| `check_h04_insertions` | contract | Either side may be empty, but not both. | a pure insertion has an empty old side, and it works at the front, in |
| `check_h05_deletions` | contract | `apply(old, diff(old, new))` equals `new`, for any two lists. | a pure deletion has an empty new side, and removing a run of lines |
| `check_h06_nothing_changed` | goal | A file that did not change at all produces no pieces. | two equal versions give an empty list, and applying an empty list |
| `check_h07_piece_that_does_not_fit` | goal | Applying a list of pieces to a version they do not fit is the dangerous | a piece whose old side is not what the text holds at that index is |
| `check_h08_out_of_order_or_overlapping` | goal | a list of pieces that is out of order, that overlaps itself | pieces given back to front, and pieces whose ranges run into each |
| `check_h09_malformed_piece` | goal | or that is simply malformed | a missing key, an extra key, a piece empty on both sides, and a piece |
| `check_h10_inputs_are_untouched` | goal | Applying must not touch what it was given, because they keep the old | after a successful apply the old list and the pieces hold exactly what |
| `check_h11_empty_versions` | contract | for any two lists | an empty old version and an empty new version are both ordinary |
| `check_h12_repeated_lines` | goal | Files with many identical lines are common in their data, and going out | versions made almost entirely of one repeated line still go out and |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| A file that did not change at all produces no pieces. | `check_h06_nothing_changed` |
| A piece must not carry lines that did not change: not at its start, not at | `check_h02_no_unchanged_lines_at_the_edges` |
| Applying a list of pieces to a version they do not fit is the dangerous | `check_h07_piece_that_does_not_fit` |
| Applying must not touch what it was given, because they keep the old | `check_h10_inputs_are_untouched` |
| Files with many identical lines are common in their data, and going out | `check_h12_repeated_lines` |
| a list of pieces that is out of order, that overlaps itself | `check_h08_out_of_order_or_overlapping` |
| one per place that changed, so that a reviewer sees the two lines that | `check_h01_one_piece_per_place` |
| or that is simply malformed | `check_h09_malformed_piece` |

`contract` 錨點 4 條、`goal` 錨點 8 條。
