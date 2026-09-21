#!/bin/bash
# 最終一批：**碼凍結之後**把五臂全部重拍，這樣每一張截圖講的都是同一份碼。
#
# 前面幾批是邊量邊修（量到什麼就改什麼：換景排序、落地字壓在陶牌上、
# 同時多封信的字疊成一團、`lookAt` 把非事件記成事件）。那些中間產物**不當證據**，
# 因為它們各自拍的是不同版本。
#
# 順序：負控制第一（沒有負控制的視覺綠燈不算綠燈）。
set -u
cd "$(dirname "$0")"
SHA=$(shasum -a 256 ~/Documents/GitHub/vacant_hm/world3/index.html | cut -c1-16)
echo "index.html sha256[0:16] = $SHA   $(date +%H:%M:%S)"
for spec in "negctl:S03_negctl_arrive0:1" "after:S04_after_triple:3" \
            "before:S05_before_triple:3" "after:S02_after_single:1" \
            "before:S01_before_single:1"; do
  arm="${spec%%:*}"; rest="${spec#*:}"; out="${rest%%:*}"; n="${rest##*:}"
  echo "=== $arm -> $out (subs=$n) $(date +%H:%M:%S) load=$(uptime | sed 's/.*averages: //')"
  python3 strip.py --arm "$arm" --out "$out" --subs "$n" > "out/${out}.log" 2>&1
  echo "--- rc=$? $(date +%H:%M:%S)"
  tail -4 "out/${out}.log"
done
SHA2=$(shasum -a 256 ~/Documents/GitHub/vacant_hm/world3/index.html | cut -c1-16)
echo "index.html sha256[0:16] after = $SHA2"
[ "$SHA" = "$SHA2" ] && echo "碼在這一批期間沒有變" \
  || echo "⚠ 碼在這一批期間被改了（別的 agent 也在動這個檔）——五臂不是同一份碼"
echo ALLDONE_FINAL
