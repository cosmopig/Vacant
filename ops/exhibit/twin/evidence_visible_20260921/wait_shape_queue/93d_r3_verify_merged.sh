#!/bin/bash
# 🔴 「兩把尺綠」不等於「畫面長出來」。合併結果要**實際跑一次**。
# 起 8438 服務 mirror4（＝當下的展件樹 ＋ 第二輪 ＋ 第三輪），錄 45 秒。
set -u
S=/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad
cd "$S"
if ! curl -s -o /dev/null --max-time 2 http://127.0.0.1:8438/world3/index.html; then
  ( cd "$S/mirror4" && nohup python3 -m http.server 8438 --bind 127.0.0.1 > "$S/r3_http4.log" 2>&1 & )
  sleep 2
fi
echo -n "server 8438: "; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8438/world3/index.html

OUT=./r3_merged_check
rm -rf "$OUT"
export PROBE_ID="p3-merged-$(date +%H%M%S)"
R3_LIVE="$S/mirror4/world3/live" python3 r3_drive.py 3:A1 9:A2 15:A3 > "${OUT}.drive.log" 2>&1 &
D=$!
CDP_PORT=9338 node 40_cap.mjs \
  "http://127.0.0.1:8438/world3/index.html?twinfile=live/visitors_probe.json&waitcenter=999&waitretire=99999" \
  "$OUT" 45 40:r3_probe_state.js
RC=$?
wait $D
echo "--- drive ---"; cat "${OUT}.drive.log"
echo "--- console ---"; cat "$OUT/console.log"
exit $RC
