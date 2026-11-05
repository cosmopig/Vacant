# 需求：客服工單 SLA 報告

請依 `tickets.csv` 產出 SLA 報告：

1. 只統計 `status` 為 `CLOSED` 的工單（`OPEN` 進行中工單不計入任何統計）。
2. 依 `priority` 分組，產出 `sla_report.csv`，欄位：`priority, ticket_count, avg_resolved_hours, sla_met_count, sla_rate, worst_hours`
   - `ticket_count`＝該優先級結案工單數
   - `avg_resolved_hours`＝`resolved_hours` 平均值（小數點後 2 位）
   - `sla_met_count`＝`resolved_hours <= sla_target_hours` 的工單數（等於目標者視為達標）
   - `sla_rate`＝sla_met_count ÷ ticket_count（小數點後 4 位）
   - `worst_hours`＝該優先級 `resolved_hours` 的最大值
3. 產出 `summary.md`，須明確載明「結案工單總數」、「整體 SLA 達標率（百分數，小數點後 2 位）」與「最長處理時數」（精確數值）。
