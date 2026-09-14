# ow_20_slugify — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_20_slugify/hidden/*.py` 的
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
| `check_h01_same_order_same_length` | goal | one slug per title, in the same order as the titles they handed in | the slug for a title stays at that title's index, whatever the other |
| `check_h02_only_allowed_characters` | goal | a slug holds only lowercase letters, digits and hyphens | titles full of punctuation, capitals, accents and spaces still produce |
| `check_h03_hyphen_rules` | goal | never starts or ends with a hyphen, and never has two hyphens in a row | titles that begin, end or are riddled with punctuation still produce |
| `check_h04_no_two_the_same` | goal | no two slugs in a batch are the same | identical titles, and different titles that clean down to the same |
| `check_h05_same_batch_same_slugs` | goal | handing in the same batch twice gives the same slugs | repeated calls on the same batch return exactly the same list, which a |
| `check_h06_clean_titles_come_back_whole` | goal | a title that is already a clean slug, and that nothing else in the batch | a batch of titles that are already slugs is returned unchanged, one |
| `check_h07_non_latin_titles` | goal | a title written in a script with no Latin letters in it at all still gets | Chinese, Japanese and Greek titles each produce a non-empty slug that |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| a slug holds only lowercase letters, digits and hyphens | `check_h02_only_allowed_characters` |
| a title that is already a clean slug, and that nothing else in the batch | `check_h06_clean_titles_come_back_whole` |
| a title written in a script with no Latin letters in it at all still gets | `check_h07_non_latin_titles` |
| handing in the same batch twice gives the same slugs | `check_h05_same_batch_same_slugs` |
| never starts or ends with a hyphen, and never has two hyphens in a row | `check_h03_hyphen_rules` |
| no two slugs in a batch are the same | `check_h04_no_two_the_same` |
| one slug per title, in the same order as the titles they handed in | `check_h01_same_order_same_length` |

`contract` 錨點 0 條、`goal` 錨點 7 條。
