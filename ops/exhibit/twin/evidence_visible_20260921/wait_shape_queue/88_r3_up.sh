#!/bin/bash
# 起自己的 server（8437）與自己的 headless Chrome（9337）。
# 🔴 不碰 8420（展場那一台）、不碰使用者的 Chrome。
set -u
S=/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad
M="$S/mirror3"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

if ! curl -s -o /dev/null -w "" --max-time 2 http://127.0.0.1:8437/world3/index.html; then
  ( cd "$M" && nohup python3 -m http.server 8437 --bind 127.0.0.1 > "$S/r3_http.log" 2>&1 & )
  sleep 1.5
fi
echo -n "server: "; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8437/world3/index.html

if ! curl -s --max-time 2 http://127.0.0.1:9337/json/version > /dev/null; then
  rm -rf "$S/r3-cdp"
  nohup "$CHROME" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
    --window-size=1920,1080 --autoplay-policy=no-user-gesture-required \
    --remote-debugging-port=9337 --user-data-dir="$S/r3-cdp" about:blank \
    > "$S/r3_chrome.log" 2>&1 &
  sleep 3
fi
echo -n "chrome: "; curl -s --max-time 3 http://127.0.0.1:9337/json/version | head -c 120; echo
