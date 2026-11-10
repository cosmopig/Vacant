# NOW（round 1384 redo 收尾）

## 狀態
- 分支 auto/qwen27b；**r1384 redo**：審查點名 3 檔全數直接開啟＋依賴部分獨立重算，0 更正（數值全對上、補 phase 歸屬；0 產品改動、0 模型呼叫）。
- 直接開啟＋重算：① effects_20261105_summary.json（load in code）：50 cells（local 45/current 50）；policy30 30 cells 13w0r、35 sess/915 api/33,670,510 tok；once20 20 cells 11w0r、20 sess/457 api/19,503,953 tok；兩相合計 55 sess/1,372 api/53,174,463 tok——r1384 條目數字＝policy30 phase 值，重算一致。② g25_all_gates_filing.json（load in code）：三門 g1_rerun/real14/phase3 全 PASS；6 sha256 獨立重算 6/6 MATCH。③ extract.py（head＋wc＋git hash-object）：1217 行、blob e757aec50c16bc6481cd88545672d50884c83f40。
- CI（承 r1384 一次讀取、本輪不重讀）：vacant-ci.service active；上一輪次 qwen27b@862968eca86de80db89a95706e34b0875f09a8dd 2 failed（run 10:48 開始、早於 b58d9f56e 10:56 修復）→argon@1098d858e1add2db93ce1c72ab1c11fb1b8cce4d 5125/0→worker@96b4df5966be3cfecd6327e097d339d763fad4a4 5125/0（11:30 UTC）；qwen27b tip 尚未被 CI 覆蓋、per-sha json UNKNOWN。
- 跨分支：4 簿記檔 3 分支 sha256 恆等（redo commit 後復核）；vq-1zf 仍 open（等人類 `--fire`）；vq-el4 家族 71（0 open／0 in_progress）；/srv/vlab/queue/ 空。

## 下一步（loop 側）
- 下輪開頭一次讀取簿記新 commit（三分支）的 per-sha CI json：綠＝2 紅正式閉合（LATEST_qwen27b 不再指 pre-fix 862968eca86de80db89a95706e34b0875f09a8dd）；紅＝查因（r1384 已全量 CI 契約套件本地全綠於 tip）。
- vq-1zf（G3）仍等人類 `--fire`；無其他 open 工單。

## 紅線（不變）
- 不 push（loop 自動推）／不動 main／不 reset-rebase／不讀 hidden+scorer／不 fire G3／不寫 queue／不 full pytest／CI 只讀一次不 poll／0 模型呼叫。
