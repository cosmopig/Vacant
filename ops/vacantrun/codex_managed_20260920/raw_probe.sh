#!/bin/bash
OUT="${1:-/var/tmp/nwkey/raw_out.txt}"
{
echo "netns=$(readlink /proc/self/ns/net)"
echo "CODEX_NETWORK_PROXY_ACTIVE=[${CODEX_NETWORK_PROXY_ACTIVE:-}]"
python3 -c "
import socket
for h,p in [(\"1.1.1.1\",443),(\"104.20.23.154\",80),(\"100.119.113.56\",1234)]:
    s=socket.socket(); s.settimeout(6)
    try:
        s.connect((h,p)); print(\"rawsock %s:%d CONNECT_OK\"%(h,p))
    except Exception as e:
        print(\"rawsock %s:%d %s %s\"%(h,p,type(e).__name__,e))
    s.close()
"
} > "$OUT" 2>&1
cat "$OUT"
