# NOW（round 1388 redo 收口）

## 狀態
- 分支 auto/qwen27b；r1388 redo（審查點名 4 檔例外工單）：4 檔全數實開、依賴重算 0 更正。
  - effects summary（60,228 B、a710f7e4…fda5）：50 cells 獨立重算全 MATCH——policy30 w2r 13（g7/l6）r2w 0 sess 35 api 915 tok 33,670,510（5 cells tokens None→UNKNOWN）；once20 w2r 11（g7/l4）r2w 0 sess 20 api 457 tok 19,503,953；totals 50/local 45/current 50；與 11-06 人工記錄一致。
  - g25 filing：3 gates 全 PASS（g1 39/39 false_acc 0／real14 9/9 false_acc 0 total_good 5／phase3 9 fixed 7 unresolved 2 r2w 0 errors 0）＋6 內嵌 sha 磁碟重算 6/6 MATCH。
  - **歷史轉抄錯誤（新發現、記錄在案）**：r1383–r1387 條目之 filing sha c9b19873…與 run_eval 92ab5a7f…經 git 全歷史核對，均不對應任何已提交版本；live 真值＝filing 6e5afb46…（＝HEAD、自 dd9788291 未變）＋run_eval 332cd324…（＝2db8afa51 態）＝筆誤、非檔案被改動。
  - extract.py 1217 行 blob e757aec5…／repair.py 2795 行 blob 5147f8c3…＝錨點 MATCH、未改。
- r1388 紅燈根因定案（上條）：50b7023c/cc5de0c1 三紅測＝pre-r1387 修 pin 族；tip 88 passed 收口。
- 凍結不變：filing 6/6 MATCH、queue 空（含隱藏）、G3 NOT_FIRED。
- vq-el4.72 本輪開→關；vq-1zf（G3）仍等人類 --fire；無其他 open 待辦。

## 下一步（loop 側）
- 下輪開頭一次讀取 CI（不 poll）：3 tips 之 per-sha json——綠＝三分支收口；紅＝查因（先核是否 pin 族同型）。
- vq-1zf 仍等人類 --fire；無其他待辦。

## 紅線（不變）
- 不 push（loop 自動推）／不動 main／不 reset-rebase／不讀 hidden+scorer／不 fire G3／不寫 queue／不 full pytest／不跑 gate_command（0 模型呼叫）／CI 只讀一次不 poll。
