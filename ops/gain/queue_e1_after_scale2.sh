#!/bin/bash
# ops/gain/queue_e1_after_scale2.sh — 已停用（2026-09-02 R440E）。
#
# 這支是 round440c 的 E1 watcher。經三個獨立審查者找碴（DECISION_20260902_R440E）
# 後由 ops/gain/launch_e1.sh 取代；它在 04:24 UTC 被迴圈第 4908 輪重跑過一次，
# 結果 gemma 載入失敗（1004 分頁檔太小／保護機制 44.87 GB），詳見 R440E。
# 留這個殼是為了讓任何照舊文件呼叫它的輪次**立刻停下並留下紀錄**，而不是靜默做事。
# E1 的發射由人類或 Mac 端 fable session 執行 launch_e1.sh，迴圈不要自己跑。
ROOT="$HOME/vacant"; mkdir -p "$ROOT/logs"
printf '%s  DEPRECATED: queue_e1_after_scale2.sh called (pid %s, args: %s) — use ops/gain/launch_e1.sh per DECISION_20260902_R440E; nothing done\n' \
  "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" "$$" "$*" | tee -a "$ROOT/logs/queue_e1.log" >&2
exit 2
