#!/bin/bash
# run_cap.sh <outdir> <seconds> <url-query> <drive-steps...>
set -u
cd /private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad
OUT="$1"; shift
SECS="$1"; shift
QUERY="$1"; shift
rm -rf "$OUT"
export PROBE_ID="probe-$(basename "$OUT")-$(date +%H%M%S)"
echo "PROBE_ID=$PROBE_ID"
python3 drive.py "$@" > "${OUT}.drive.log" 2>&1 &
DRIVEPID=$!
CDP_PORT=9337 node 40_cap.mjs "http://127.0.0.1:8437/world3/index.html?${QUERY}" "$OUT" "$SECS"
RC=$?
wait $DRIVEPID
echo "--- drive log ---"
cat "${OUT}.drive.log"
echo "--- page console ---"
cat "$OUT/console.log"
exit $RC
