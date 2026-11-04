# 需求：巢狀事件日誌統計

`events.json` 是 JSON 陣列，每個事件含 `event_id`、`event_type`、`ts`，
以及巢狀 `payload`（可能整個缺失；`payload.duration_ms` 也可能缺失）。

1. `event_type` 不分大小寫（`CLICK`、`click`、`Click` 為同一類），輸出用 lower。
2. `payload.duration_ms` 缺失以 0 計（該事件**仍計入** event_count）；無 payload 的事件也仍計數。
3. 產出 `event_stats.csv`，欄位：`event_type, event_count, total_duration_ms`
   - `total_duration_ms` = 該類型 `duration_ms` 加總（缺失以 0 計）。
4. 產出 `summary.md`，須明確載明「事件總數」（全部事件筆數，精確數值）與「總時長」（ms）。
