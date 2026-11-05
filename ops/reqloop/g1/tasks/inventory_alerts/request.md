# 需求：庫存補貨預警清單

請依 `inventory.csv` 產出補貨預警：

1. 排除 `supplier_status` 為 `DISCONTINUED` 的停產項目。
2. 同一 `item_id` 若出現多筆，只保留第一筆。
3. 選出庫存不足品項：`current_stock < safety_stock`（等於安全量者不需補貨）。
4. 產出 `restock_alerts.csv`，欄位：`item_id, item_name, current_stock, safety_stock, restock_needed, estimated_cost`
   - `restock_needed = safety_stock - current_stock`
   - `estimated_cost = restock_needed × unit_cost`（小數點後 2 位）
5. 產出 `summary.md`，須明確載明「需補貨品項數」與「預估補貨總金額」（精確數值，小數點後 2 位）。
