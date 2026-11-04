# 庫存預警任務要求

請根據提供的 `inventory.csv` 資料進行以下處理：

1. **資料清洗**：
   - 排除所有供應商狀態為 `DISCONTINUED`（停產）的項目。
   - 排除重複的 `item_id`（若有重複，以第一筆記錄為準）。

2. **補貨篩選**：
   - 從清洗後的資料中，篩選出庫存不足的品項（即 `current_stock < safety_stock`）。
   - 對於這些品項，計算需要補貨的數量 (`restock_needed = safety_stock - current_stock`)。
   - 計算預估補貨金額 (`estimated_cost = restock_needed * unit_cost`)。

3. **產出檔案**：
   - 產生 `restock_alerts.csv`，包含欄位：`item_id, item_name, current_stock, safety_stock, restock_needed, estimated_cost`。
   - 產生 `summary.md`，內容需包含：
     - 總計需要補貨的品項數量。
     - 預估補貨總金額（單位：元）。

請確保計算精確無誤。