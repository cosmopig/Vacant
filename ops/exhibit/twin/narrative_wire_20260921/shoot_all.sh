#!/bin/bash
# 一鍵把「接上線之後，走到展場前面讀得到什麼」整批拍下來。
#
#   bash shoot_all.sh <base_url> <輸出目錄> [tag]
#   例：bash shoot_all.sh http://127.0.0.1:8477/world3/index.html shots wired
#
# 每一格：PNG ＋ 同名 .json（大標／副標是**從頁面上讀回來**的，見 shoot_wire.mjs）。
# 🔴 不吞 stderr、不用 `cmd && echo ✅`：每一格自己的退出碼記在 shoot_all_result.txt。
set -u
BASE="$1"; OUTDIR="$2"; TAG="${3:-wired}"
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$OUTDIR"
RES="$OUTDIR/shoot_all_${TAG}.txt"
: > "$RES"
PORT=9410
FAIL=0

shoot () {   # shoot <名字> <query> <期待的幕>
  local name="$1" q="$2" expect="$3"
  PORT=$((PORT + 1))
  node "$HERE/shoot_wire.mjs" "$OUTDIR/${TAG}_${name}.png" "${BASE}?${q}" 9000 "$PORT" "$expect" \
    > "$OUTDIR/${TAG}_${name}.log" 2>&1
  local rc=$?
  local head sub src
  head=$(python3 -c "
import json,sys
try:
    d=json.load(open('$OUTDIR/${TAG}_${name}.json'))
    print(d.get('head'))
except Exception as e:
    print('（讀不到）')
" 2>/dev/null)
  sub=$(python3 -c "
import json,sys
try:
    d=json.load(open('$OUTDIR/${TAG}_${name}.json'))
    print(d.get('sub'))
except Exception as e:
    print('（讀不到）')
" 2>/dev/null)
  src=$(python3 -c "
import json,sys
try:
    d=json.load(open('$OUTDIR/${TAG}_${name}.json'))
    print(d.get('title_ov_source'))
except Exception as e:
    print('（讀不到）')
" 2>/dev/null)
  printf '%s\trc=%s\t%s\t%s\t%s\n' "$name" "$rc" "$head" "$sub" "$src" >> "$RES"
  echo "[$name] rc=$rc  $head ／ $sub  ←$src"
  [ "$rc" -eq 0 ] || FAIL=$((FAIL + 1))
}

shoot b05_arrived   "seamshot=arrived"      s03
shoot b06_queued    "seamshot=queued"       s03
shoot b07w1_waiting "scene=s11&seamwait=1"  s11
shoot b07w3_waiting "scene=s11&seamwait=3"  s11
shoot b08_enter     "seamshot=enter"        s04
shoot b09_goal      "seamshot=goal"         s05
shoot b09b_nomatch  "seamshot=nomatch"      s11
shoot b16_receiptA  "seamshot=receiptA"     s13
shoot b17_receiptB  "seamshot=receiptB"     s11
shoot b18_one       "scene=s11&seamend=1"   s11
shoot b18_many      "scene=s11&seamend=3"   s11

echo "---"
echo "失敗格數=$FAIL  結果表=$RES"
exit $FAIL
