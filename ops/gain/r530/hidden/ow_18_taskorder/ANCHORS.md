# ow_18_taskorder — 隱藏驗收 ⇄ 目標／契約 對照表

§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/ow_18_taskorder/hidden/*.py` 的
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
| `check_h01_every_job_exactly_once` | goal | every job appears in the order exactly once, and a job that is only ever | the order is a permutation of every name that appears anywhere in the |
| `check_h02_nothing_runs_too_early` | goal | nothing runs before something it waits for | for every job and every one of its prerequisites, the prerequisite |
| `check_h03_same_table_same_order` | goal | running the planner twice on the same table gives the same order | repeated calls on the same table return exactly the same list, so the |
| `check_h04_circles_are_reported` | goal | because some jobs wait on each other in a circle, directly or through | a two-job circle and a longer one both raise, including when other |
| `check_h05_a_job_waiting_on_itself` | goal | or because a job waits on itself | a job listing its own name can never start, so the table is reported |
| `check_h06_nothing_to_do` | contract | `plan` returns a list of job names. | an empty table gives an empty list, and a table where nothing waits |

## 二、反向：被指到的目標句子（**不完整，見上面的警告**）

| goal 裡的句子 | 指到它的驗收 |
|---|---|
| because some jobs wait on each other in a circle, directly or through | `check_h04_circles_are_reported` |
| every job appears in the order exactly once, and a job that is only ever | `check_h01_every_job_exactly_once` |
| nothing runs before something it waits for | `check_h02_nothing_runs_too_early` |
| or because a job waits on itself | `check_h05_a_job_waiting_on_itself` |
| running the planner twice on the same table gives the same order | `check_h03_same_table_same_order` |

`contract` 錨點 1 條、`goal` 錨點 5 條。
