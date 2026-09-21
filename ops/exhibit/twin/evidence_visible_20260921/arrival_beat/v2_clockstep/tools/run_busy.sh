#!/bin/bash
# 第六、七臂：**導演正在演別人的故事時投卡。**
#
# 為什麼補這兩臂：S03（負控制、導演閒著）拍出來，投卡 620 ms 後畫面已經硬切
# 到「世界多了一個人」。⇒「改動前投卡完全沒反應」**是錯的**。真正有落差的是
# 導演忙著的時候——那正是展場有人排隊時的常態。
#
# 順序：改動前先跑（先量基準線，免得只剩時間跑好看的那一臂）。
set -u
cd "$(dirname "$0")"
SHA=$(shasum -a 256 ~/Documents/GitHub/vacant_hm/world3/index.html | cut -c1-16)
echo "index.html sha256[0:16] = $SHA   $(date +%H:%M:%S)"
for spec in "before:S06_before_busy" "after:S07_after_busy"; do
  arm="${spec%%:*}"; out="${spec##*:}"
  echo "=== $arm -> $out $(date +%H:%M:%S) load=$(uptime | sed 's/.*averages: //')"
  python3 strip_busy.py --arm "$arm" --out "$out" --subs 1 > "out/${out}.log" 2>&1
  echo "--- rc=$? $(date +%H:%M:%S)"
  tail -4 "out/${out}.log"
done
SHA2=$(shasum -a 256 ~/Documents/GitHub/vacant_hm/world3/index.html | cut -c1-16)
[ "$SHA" = "$SHA2" ] && echo "碼在這一批期間沒有變" \
  || echo "⚠ 碼在這一批期間被改了（$SHA -> $SHA2）——兩臂不是同一份碼"
echo ALLDONE_BUSY
