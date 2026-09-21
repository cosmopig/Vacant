#!/bin/bash
# 第三輪：重建一棵「現行展件樹 ＋ 等待態 patch」的鏡像。
# 不碰 8420（那是展場那一台）、不碰使用者的 Chrome。
set -eu
S=/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad
M="$S/mirror3"
HM="$HOME/Documents/GitHub/vacant_hm"

rm -rf "$M"; mkdir -p "$M"
for p in "$HM"/*; do ln -s "$p" "$M/$(basename "$p")"; done

# world3 與 tools 要是實體目錄（要換掉 index.html / waitcheck.mjs / live）
rm "$M/world3"; mkdir "$M/world3"
for p in "$HM"/world3/*; do ln -s "$p" "$M/world3/$(basename "$p")"; done
rm "$M/world3/index.html"; cp "$HM/world3/index.html" "$M/world3/index.html"
rm "$M/world3/live";       cp -R "$HM/world3/live" "$M/world3/live"

rm "$M/tools"; mkdir "$M/tools"
for p in "$HM"/tools/*; do ln -s "$p" "$M/tools/$(basename "$p")"; done

echo "== 鏡像建好 =="
echo -n "ours sha256: "; shasum -a 256 "$M/world3/index.html" | cut -d' ' -f1
wc -l < "$M/world3/index.html"
