#!/bin/bash
# `r3_replay.py` 自己的負控制：把同一批改動套回 A，結果必須逐 byte 等於 B。
# （第一版就是在這裡會紅——它會安靜地少套一段。）
set -u
S=/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad
A="$1"; B="$S/mirror3/world3/index.html"
cp "$A" "$S/r3_selftest.html"
python3 "$S/r3_replay.py" "$A" "$B" "$S/r3_selftest.html"
if cmp -s "$S/r3_selftest.html" "$B"; then
  echo "✅ 自我檢驗：套回 A 之後逐 byte 等於 B"
else
  echo "🔴 自我檢驗失敗："; diff <(cat "$S/r3_selftest.html") <(cat "$B") | head -20
  exit 1
fi
