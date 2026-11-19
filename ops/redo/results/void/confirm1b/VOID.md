# confirm1b 作廢紀錄＋計畫偏離（2026-11-19 補記）

計畫：`ops/redo/plans/confirm1b_vacantdo_pi_gemma12b_1004.json`（sha256 開頭 `e9c1eed0d6e2`）。
發射 2026-11-18T00:09:37Z，停批約 00:23Z，完成 2 格（`pg_grep/r1/A` 通過；`pg_zebra_puzzle` 等未完成）。
本機原始資料（102 個檔，未入庫）：`~/dev/ops/redo_runs/confirm1b.void_badalloc/`；
停批後才寫出的殘留檔在其下的 `late_writes/`。

## 計畫寫的停批規則

> jobs 2：監看若在任何 10 分鐘內看到 ≥2 次 `bad allocation`／端點崩潰，停批、改 jobs 1 重新預註冊（已完成的格作廢）；這條只看基礎設施記錄，不看方向。

## 實際發生的事（時間為 1004 當地 UTC+8）

LM Studio 伺服器日誌（`lmstudio_bad_allocation_lines.txt`，原文逐行）：

| 時間 | slot / task | 打到哪一格 |
|---|---|---|
| 08:11:12 | slot 3 / task 6394 | `pg_grep/r1/P` 第 1 次內層嘗試（`agent_pg_grep__…excerpt.txt`） |
| 08:22:29 | slot 0 / task 29132 | `pg_hangman/r1/P` 第 3 次內層嘗試（`agent_pg_hangman__…excerpt.txt`） |
| 08:23:04 | slot 3 / task 30490 | 不確定：停批進行中，可能是尚未結束的孤兒 `vacant do pi`（PID 585795）或共用這台的實驗室助手 |

## 偏離

1. **停批決定不是依字面規則做出的。** 決定時（約 08:22:40）只看到前兩次，相隔 11 分 17 秒，未達「10 分鐘內 ≥2 次」。
   confirm1c 的計畫檔把理由寫成「依停批規則的精神」——這是對的描述，**不能說成完全遵守了預註冊的停止規則**。
2. 第三次（08:23:04）與第二次相隔 35 秒，字面上符合規則，但它發生在決定之後、來源不確定，**不能拿來事後補足理由**。
   confirm1c 計畫檔與 2026-11-18 的對話都只提到兩次，那是當時的掌握，這裡更正。
3. 停批依據只看基礎設施記錄：決定時兩臂各只有 1 格完成，方向資訊不存在。

## 為什麼仍然停

- 兩次都打在 P 臂的內層嘗試；P 臂的內層嘗試沒有 harness 的 infra 重試，這種錯會系統性壓低 P（對 P 不利的偏差，
  但不管方向，資料品質都會變差）。
- 同一台在 jobs 1 下（redo1）338 格約 1 次；jobs 2 下 13 分鐘 2 次，頻率高兩個數量級。

## 處置

- confirm1b 全批作廢，資料不進任何結論，也不與 confirm1／confirm1c 合併。
- 改 jobs 1 重新預註冊為 confirm1c（`87b6637c3`），同計畫、同端點。

## 勘誤：confirm1c 計畫檔的 `prereg.question`

confirm1c（以及 confirm1b）的 `prereg.question` 從 confirm1 複製過來，仍寫「gemma-4-12b-it-qat，1003」。
實際端點是 **1004**（`providers[0].provider = lms1004nothink`），`prereg.states.EFFECTIVE` 與 `known_limits` 已正確寫 1004。
計畫檔發射前已凍結（sha256 綁在報告上），不改檔；以本勘誤為準，結案報告引用時一併註明。
