#!/bin/sh
# argv: ... <event>; log event and payload, reply continue for turn_check
ev="$1"
payload=$(cat)
echo "$ev $payload" >> /tmp/claude-0/review_v3/budget_first/hook.log
if [ "$ev" = "turn_check" ]; then echo '{"action":"continue","reason":"NUDGE"}'; else echo '{"action":"allow"}'; fi
