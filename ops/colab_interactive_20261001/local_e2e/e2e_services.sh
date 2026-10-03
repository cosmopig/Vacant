#!/usr/bin/env bash
# 本機端到端的三個服務：替身模型（18000）、tag_front（18950）、orproxy（18900，本機模式；重試等待縮短）。
# 找行程用 /proc 掃描（不用 pkill -f／pgrep -f：指令列比對會殺到呼叫它的 shell——踩過兩次）。
# 用法：e2e_services.sh start <劇本.json> <日誌目錄> | stop | status
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
scan() {   # scan list|kill
  python3 - "$1" <<'PY'
import os, signal, sys
mode = sys.argv[1]
names = (b"e2e_stub.py", b"tag_front.py", b"/opt/eval/bin/orproxy.py")
for d in os.listdir("/proc"):
    if not d.isdigit() or int(d) == os.getpid():
        continue
    try:
        args = open(f"/proc/{d}/cmdline", "rb").read().split(b"\0")
    except OSError:
        continue
    if len(args) > 1 and args[0].endswith(b"python3") and args[1].endswith(names):
        if mode == "kill":
            os.kill(int(d), signal.SIGTERM)
        else:
            print(d, args[1].decode().rsplit("/", 1)[-1])
PY
}
case "${1:-}" in
start)
  SCRIPT=$2; LOGD=$3; mkdir -p "$LOGD"
  export NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
  # 代理：deploy 起的那個設定的重試等待是 [5,15,30,60]（110 秒）；本機端到端的逾時只有 60 秒，所以縮成 [1,1,1,1]（次數不變＝5 次嘗試）
  python3 - <<'PY'
import json
p = "/srv/eval/proxy.json"
d = json.load(open(p))
d["retry_waits"] = [1, 1, 1, 1]
json.dump(d, open(p, "w"))
PY
  scan kill; sleep 1      # 包含 deploy_i1001.sh 自己起的那個 orproxy（它佔著 18900、重試等待是真設定的）
  setsid nohup python3 "$HERE/e2e_stub.py" --port 18000 --script "$SCRIPT" --log "$LOGD/stub_requests.jsonl" > "$LOGD/stub.out" 2>&1 < /dev/null &
  (cd /srv/eval && setsid nohup python3 /opt/eval/bin/orproxy.py --config /srv/eval/proxy.json --out /srv/eval/proxy --host 127.0.0.1 --port 18900 > /srv/eval/proxy.log 2>&1 < /dev/null &)
  setsid nohup python3 "$HERE/tag_front.py" --listen 18950 --target-port 18900 > "$LOGD/front.out" 2>&1 < /dev/null &
  sleep 2; scan list ;;
stop)
  scan kill ;;
status)
  scan list ;;
*) echo "usage: $0 start <script.json> <logdir> | stop | status"; exit 2 ;;
esac
