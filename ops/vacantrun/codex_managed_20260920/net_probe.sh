#!/bin/bash
OUT="${1:-/var/tmp/nwkey/probe_out.txt}"
{
echo "ts=$(date -Is)"
echo "netns=$(readlink /proc/self/ns/net)"
echo "CODEX_NETWORK_PROXY_ACTIVE=[${CODEX_NETWORK_PROXY_ACTIVE:-}]"
echo "HTTP_PROXY=[${HTTP_PROXY:-}]"
echo "ALL_PROXY=[${ALL_PROXY:-}]"
for t in "http://100.119.113.56:1234/v1/models" "http://1.1.1.1/" "http://104.20.23.154/" "http://example.com/" "https://example.com/"; do
  body=$(curl -s -m 12 -w "\n__HTTP__%{http_code}" "$t" 2>&1)
  rc=$?
  code=$(printf "%s" "$body" | tail -1 | sed "s/__HTTP__//")
  snip=$(printf "%s" "$body" | head -c 160 | tr -d "\r\n" )
  echo "GET $t -> http=$code rc=$rc body[0:160]=<$snip>"
done
python3 -c "
import socket
for h,p in [(\"1.1.1.1\",443),(\"100.119.113.56\",1234)]:
    s=socket.socket(); s.settimeout(8)
    try:
        s.connect((h,p)); print(\"rawsock %s:%d CONNECT_OK\"%(h,p))
    except Exception as e:
        print(\"rawsock %s:%d %s %s\"%(h,p,type(e).__name__,e))
    s.close()
"
} > "$OUT" 2>&1
cat "$OUT"
