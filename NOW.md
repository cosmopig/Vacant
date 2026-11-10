# NOW（round 1385 redo 收口）

## 狀態
- 分支 auto/qwen27b；r1385 redo：審查點名 2 檔（effects_20261105_summary.json、g25_all_gates_filing.json）本輪 json.load 實開＋依賴部分獨立重算，0 更正。
- effects（60,228B、sha a710f7e4…）：50 格 cells_detail 獨立重算——policy30 w2r 13（g7/l6）r2w 0、35 sess/915 api/33,670,510 tok（5 格 tok=None→UNKNOWN）；once20 w2r 11（g7/l4）r2w 0、20 sess/457 api/19,503,953 tok；per-arm 全項 MATCH、scope_note 在位。
- filing（4,681B、r1228）：6 sha256 對活檔獨立重算 6/6 MATCH（code 3＋argon worktree sources 3）；三門 g1_rerun/real14/phase3 全 PASS（直讀）。
- CI 承 r1385 一次讀取（不 poll）：state.json running=argon@1b5fdebb…；LATEST 三檔 5125/0；現 3 tips per-sha json 無→UNKNOWN。
- vq-1zf（G3）open 等人類 --fire；/srv/vlab/queue 空（含隱藏）；無新工單。

## 下一步（loop 側）
- 下輪開頭一次讀取 CI（不 poll）：三分支現 tip 之 per-sha json 或 LATEST——綠＝三分支收口；紅＝查因（本輪已於 tip 本地 66 passed 全綠、redo 後 freeze_check 11/11 OK）。
- vq-1zf 仍等人類 --fire；無其他待辦。

## 紅線（不變）
- 不 push（loop 自動推）／不動 main／不 reset-rebase／不讀 hidden+scorer／不 fire G3／不寫 queue／不 full pytest／CI 只讀一次不 poll／0 模型呼叫。
