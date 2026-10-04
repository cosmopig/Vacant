# vacant-dev 不限時間的兩批（t3U 任務導向 → d37U DABstep）— RUNLOG

預註冊：`decisions/prereg/PREREG_20261004_VACANTDEV_UNLIMITED_V37.md`。時間 UTC。

| 時間 | 事件 |
|---|---|
| 13:1x | 人類：「派一樣的題目，然後不限時間」。1003／1004 gemma 都載著；vacant-dev 空閒、磁碟 3.3 GB |
| 13:2x | 計畫：`plan_t3u.json`（94 題 × A／C37 × 3）、`plan_d37u.json`（79 題 × A／C37 × 3）；`analyze_dabstep_u.py`（只 A／C37；用 d37L 試跑 p＝0.84 與原版相同）；`run_queue_u.sh`（`AGENT_TIMEOUT=14400` 安全網、不設回合上限）。預註冊凍結（本 commit） |
| 13:2x | **發射** `run_queue_u.sh`：t3U 開跑（8 位置、`AGENT_TIMEOUT=14400`、不設回合上限）；打包、瘦身常駐在；`keep_gemma.sh` 改成 U_DONE 才結束（第一次的「已在跑」判斷用 `pgrep -f "[k]eep…"` 比對到下指令的殼自己、沒啟動，分開重開）。Mac 同步重開 |
| 10-04 23:50 | t3U 第 1 次 188 格完成（第 2 次 45 格在跑）；撞 4 小時安全網 3 格（A 1、C37 2）；安裝失敗 0；模型全 200、沒有重新載入。速度：前 5 小時每小時約 25 格、第 1 次尾段每小時約 8–11 格（長格佔位，p90 牆鐘約 85 分鐘） |
| 10-05 00:0x | **期中看一眼（第 1 次，不改計畫、不是最終）**：void 0；A 63 vs C37 64／94，McNemar 7 對 6、p＝1.0；DABench 93.3／93.3、DataBench 83.3／76.7、Polyglot 29.4／38.2（4 對 1 題）。拿掉時限後失敗幾乎全是「說做完但答錯」（A 28、C37 25）；撞安全網 1／2；「說做完沒寫檔」2／3。A 67%，和有 1800 秒時限的 GGUF 那批（約 66%）差不多——撞時限的格子多給時間後大多交出錯的答案。`results/report_t3U_s1_interim.json` |
