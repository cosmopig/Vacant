#!/bin/bash
# r3_cap.sh <outdir> <seconds> <url-query> <drive-steps...>
# 錄一段，同時讓 r3_drive.py 按時間寫快照。stderr 不吞。
set -u
S=/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad
cd "$S"
OUT="$1"; shift
SECS="$1"; shift
QUERY="$1"; shift
rm -rf "$OUT"
export PROBE_ID="p3-$(basename "$OUT")-$(date +%H%M%S)"
echo "PROBE_ID=$PROBE_ID"
python3 r3_drive.py "$@" > "${OUT}.drive.log" 2>&1 &
DRIVEPID=$!
CDP_PORT=9338 node 40_cap.mjs "http://127.0.0.1:8437/world3/index.html?${QUERY}" "$OUT" "$SECS" \
  25:r3_probe_state.js 45:r3_probe_state.js 58:r3_probe_state.js
RC=$?
wait $DRIVEPID
echo "--- drive log ---"; cat "${OUT}.drive.log"
echo "--- page console ---"; cat "$OUT/console.log"
exit $RC
