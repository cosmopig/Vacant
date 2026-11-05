# 需求：網站流量按當地日期統計

伺服器日誌以 UTC 記錄（`day_index`、`hour`、`tz_offset_hours` 為訪客時區偏移，單位：小時）。

1. 當地日期 `local_day = day_index + ((hour + tz_offset_hours) // 24)`（整數除、向負無窮取整；
   例如 hour 23、tz +8 → 歸入下一日）。
2. 依 `local_day` 產出 `daily_traffic.csv`，欄位：`local_day, visits, uv, avg_dwell`
   - `visits` = 該當地日期之造訪筆數
   - `uv` = 該當地日期之獨立 `user_id` 數
   - `avg_dwell` = 該當地日期 `dwell_seconds` 平均（小數點後 2 位）；`dwell_seconds` 空白＝無停留紀錄，**剔除不計入平均**
3. 產出 `summary.md`，須明確載明「全期獨立訪客數 UV」（全部資料跨日去重之 `user_id` 數）與「全期造訪總數」（精確數值）。
   注意：全期 UV **不是**每日 UV 相加。
