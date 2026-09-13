# R666：把 CONFORM 的收據鏈與公鑰落盤（純儀器）

（2026-09-03，Opus 5。量測與判準：`CRITERION_20260903_R666_RECEIPT_CHAIN_UNVERIFIABLE.md`。）

## 選了什麼

`ops/gain/gain_run.py` 新增模組層函式 `save_receipts(out, st)`，在既有的兩處
`write_summary` 呼叫點旁邊各叫一次（逐題的中途寫與收官寫），寫出
`receipts_<ARM>.ndjson`（`Logbook.save`）與 `receipts_<ARM>.pub.json`（vacant_id ＋ 公鑰 hex）。
空鏈的臂不寫檔。

## 放棄了什麼

- **不落盤私鑰**（沿用 RECORD_SPEC §7）。代價是身份仍為一次性匿名身份 ⇒
  鏈能證明的是**事後沒被改過**（要改就得重簽，私鑰隨行程消失），**不是「這是誰簽的」**。
  收據的究責宣稱只能講到這裡。
- **不回頭救 r444**。它的鏈只在記憶體裡，行程結束就消失；沒有任何事後手段能重建。
- **不改 `arm_conform` 的任何行為**（不多呼叫、不碰 rng、不改選擇邏輯）⇒ 不是實驗條件的改變。

## 根據什麼選

碼側事實（本輪讀碼確認）：`vacant/logbook.py` 早就有 `save()`（206）與
`verify_chain()`（168），`gain_run.py` **一處都沒呼叫**；註解只交代私鑰不落盤，
但 `verify_chain` 要的是**公鑰**，而公鑰也沒寫出去。
⇒ R440R 的 P-C4「該臂的鏈 verify_chain 為真」在 r444 上不是「為假」，是**跑不起來**。

## 對在跑的 r444 的影響：零（已驗，不是推論）

`gain_run.py` 全檔無 `importlib`／`reload`／`exec(open(...))`（grep 為空），
CPython 在 import 時就把原始碼讀完 ⇒ 改檔對 PID 2742320 無效。
實測：改檔前後該行程仍在跑，`rows.jsonl` 由 335 列續增到 340 列。
**r444 收官時仍然不會有 receipts 檔**——這是預期，不是 bug。

## 怎麼驗的

- `tests/test_gain_receipt_persistence.py` 4/4 PASS（`ops/run_tests_nopytest.py`，
  量具自檢先跑過）：存→載→`verify_chain` 為真；竄改 payload／抽掉中間一筆／換公鑰
  三種竄改一律為假。
- `ops/gain/replay/receipt_chain_audit.py` 端到端：乾淨鏈 `OK`；
  竄改 payload `BROKEN`；抽掉一筆 `BROKEN`；有鏈沒公鑰 `BROKEN`；r444（無鏈檔）`UNVERIFIABLE`。
- 沒有下游 globber 會撿到新檔（`grep ndjson | grep glob` 為空；既有工具都吃 `*.jsonl`）。

## 什麼條件下該被推翻

- 若日後要求收據**可歸屬到主體**（不只 tamper-evident），那要落盤穩定身份，
  而那會踩 RECORD_SPEC §7 ⇒ 是人類的決定，不是迴圈的。
- 若逐題寫鏈在長 run 造成可觀 I/O（鏈長 O(n)、每題全量重寫 ⇒ O(n²) bytes）：
  n=179、每題約 2 筆的量級下可忽略（實測檔案 KB 級），但 n 上千時要改成 append-only 寫法。
  **這一條是本決定已知的、尚未觸發的成本**，不是事後才想到的藉口。
