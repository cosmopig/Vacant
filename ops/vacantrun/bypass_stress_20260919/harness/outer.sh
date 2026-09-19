#!/usr/bin/env bash
# launcher 以 user1（proxy 的 uid）跑這一層；它把 **agent 降到 uid 1001**。
#
# 為什麼要這一層（V3 撞出來的缺口一，本輪照樣撞）：
# `launcher.py` 的 proxy 與 agent 在**同一個行程樹、同一個 uid**，而
# `-m owner --uid-owner` 只認 uid ⇒ 不分 uid 的話，刻度／封鎖會把 proxy
# 自己的上游一起算／一起擋。**launcher 沒有 `--agent-uid`**，所以這一層是
# 手工補的，不是既有功能。補法列在
# `ops/vacantrun/bypass_stress_20260919/README.md` 的「要改 vacant_network/ 的清單」。
set -uo pipefail
R=/var/tmp/vbypass
INNER="$1"; shift
ENVF="$(mktemp "$R/work/envpass-XXXXXX")"
chmod 644 "$ENVF"
export -p > "$ENVF"                      # 鐵律 3：agent 實際拿到的 env 逐字落盤
cp "$ENVF" "$R/logs/env_${VB_CELL:-unknown}.txt"
exec sudo -n -u "#1001" "$INNER" "$ENVF" "$@"
