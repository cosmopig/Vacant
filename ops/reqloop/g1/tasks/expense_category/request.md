# 需求：費用報銷分類加總

請依 `expenses.csv` 產出分類加總：

1. 依 `category` 與 `subcategory` 分組；`subcategory` 空白者歸入 `unspecified`；
   `subcategory` 大小寫不分（例如 `software` 與 `Software` 為同一組），輸出用 lower。
2. 產出 `expense_summary.csv`，欄位：`category, subcategory, total_amount`
   - `total_amount` = 該組 `amount` 加總後四捨五入到小數點後 2 位（**先加總、後取整**）。
3. 產出 `summary.md`，須明確載明「報銷總金額」（全部加總、小數點後 2 位，精確數值）。
