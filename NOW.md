# NOW（round 1390 redo 收口）

## 狀態
- 分支 auto/qwen27b；r1390 redo＝審查點名 4 檔實開＋依賴值重算（vq-el4.76 開→關），0 更正期望值。
- **四檔已實開**：
  - effects_20261105_summary.json：50 格 current_code 50/50（local 舊 checker 45/50）；policy30 13w/0r（g7/l6）、once20 11w/0r（g7/l4）；成本 35/915/33,670,510 與 20/457/19,503,953；scope_note 邊界在案。
  - g25_all_gates_filing.json：三門全 PASS（39/39＋0；9/9＋0/5；fixed 7/unresolved 2/errors 0）；6 sha256 獨立重算 6/6 MATCH（extract.py 51abfec3…、run_eval.py 332cd324…）。
  - extract.py：1,217 行、blob e757aec5、fail-closed 組裝層。
  - repair.py：2,795 行、blob 5147f8c3、修復紀律（FAIL→UNKNOWN 不算修好、成本缺值 UNKNOWN 不填 0）。
- CI（r1390 一次讀、不 poll）：qwen27b LATEST 🟢 93707c2fa；argon LATEST 🟢 1b93dcd04（5125/0）；worker LATEST 紅＝b056caea7 舊 sha pin 族（r1388 定案）；worker@86bea3a77 running→per-sha UNKNOWN（H-0）。
- 守衛 88 passed＋freeze_check 11/11 OK FROZEN_STATE_OK＋ves 7/7 OK（r1390 新跑）；vq-1zf 仍等人類 --fire；queue 空。

## 下一步（loop 側）
- 下輪開頭一次讀取 CI：3 tips per-sha json——worker@86bea3a77 預期綠（in-scope 碼＝qwen27b tip diff 0、本地 88 passed 蓋三紅測）；綠＝三分支收口、紅＝查因（先核 pin 族同型）。
- vq-1zf 仍等人類 --fire；無其他待辦。

## 紅線（不變）
- 不 push（loop 自推）／不動 main／不 reset-rebase／不讀 hidden+scorer／不 fire G3／不寫 queue／不 full pytest／不跑 gate_command（0 模型呼叫）／CI 只讀一次不 poll。
