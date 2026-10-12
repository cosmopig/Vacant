#!/bin/sh
printf '{"event":"%s","payload":%s}\n' "$1" "$(cat)" >> /tmp/claude-0/review_v33/node/calls.jsonl
if [ "$1" = stop ]; then echo '{"action":"continue","reason":"The request asks for /app/answer.txt, but it does not exist."}'; else echo '{"action":"allow"}'; fi
