#!/usr/bin/env bash
# 磁碟只有約 4 GB：已打包進 chunk（archive/packed_cells.txt）的格子，只留 DONE／meta／score／vacant_check（續跑與監看要用），其餘刪掉。
# 完整內容在 chunk 裡（本機同步、sha256 驗過）。每 5 分鐘一次；QUEUE_DONE 後結束。
E=/srv/eval
while true; do
  if [ -f $E/archive/packed_cells.txt ]; then
    while read -r c; do d=$E/cells/$c; [ -d "$d" ] || continue; [ -f "$d/.slim" ] && continue
      find "$d" -mindepth 1 -maxdepth 1 ! -name DONE ! -name meta.json ! -name score.json ! -name vacant_check.json -exec rm -rf {} +; touch "$d/.slim"; done < $E/archive/packed_cells.txt
  fi
  echo "$(date -u +%FT%TZ) df=$(df -h / | awk 'NR==2{print $4}')" >> $E/cleanup.log
  [ -f $E/QUEUE_DONE ] && exit 0; sleep 300
done
