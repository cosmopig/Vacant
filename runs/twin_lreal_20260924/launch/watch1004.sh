#!/usr/bin/env bash
# 每 60 秒記一次 1004 的模型狀態（JIT 卸載會變成一串逾時＝假拒交，要看得到）。跑到 BATCH2 done 為止。
while ! grep -q "BATCH2 done" /var/tmp/vacant_lreal_20260924/batch.log; do
  s=$(curl -s -m 10 http://100.86.226.21:1234/api/v0/models | python3 -c "import json,sys; print(\" \".join(m[\"id\"]+\"=\"+m[\"state\"] for m in json.load(sys.stdin)[\"data\"] if m[\"state\"]!=\"not-loaded\"))" 2>&1)
  echo "$(date -u +%FT%TZ) $s"
  sleep 60
done
echo "$(date -u +%FT%TZ) watcher end"
