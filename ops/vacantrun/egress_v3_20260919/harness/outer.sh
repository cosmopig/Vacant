#!/usr/bin/env bash
# launcher 以 user1（proxy 的 uid）執行這一支；它把 agent **降到 uid 1001**。
# 為什麼要這一層：`vacant/vrun/launcher.py:303-307` 的 proxy 跟 agent 在**同一個
# 行程樹、同一個 uid**，而 `block_egress.sh` 的 `--uid-owner` 只認 uid ⇒
# 不分 uid 就會連 proxy 自己的上游一起封死。launcher 沒有 `--agent-uid`，
# 所以這一層是**手工補的**，不是既有功能。
set -uo pipefail
INNER="$1"; shift
ENVF="$(mktemp /var/tmp/v3egress/envpass-XXXXXX)"
chmod 644 "$ENVF"
export -p > "$ENVF"          # 鐵律 3：agent 實際拿到的 env 逐字落盤
cp "$ENVF" "/var/tmp/v3egress/logs/env_$(basename "$INNER" .sh).txt"
exec sudo -n -u "#1001" "$INNER" "$ENVF" "$@"
