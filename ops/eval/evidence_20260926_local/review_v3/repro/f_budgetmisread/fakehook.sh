#!/bin/sh
ev="$1"
payload=$(cat)
printf '%s %s\n' "$ev" "$payload" >> /tmp/claude-0/review_v3/f_budgetmisread/hooklog.txt
echo '{"action":"allow"}'
