#!/bin/bash
# 建一個「符號連結農場」：world3 的資產全部連過來，只有 index.html 是衍生的
# （＝現在的 index.html ＋ 兩行 <script>）。這樣在確定不會弄壞展件之前，
# 可以先把整條線跑起來。
set -eu
W3=/Users/cosmopig/Documents/GitHub/vacant_hm/world3
SC=/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad
ST="$SC/stage"
rm -rf "$ST"; mkdir -p "$ST"
for f in plates props sprites data live docs qr.png bridge.js twinseam.js scenes; do
  ln -s "$W3/$f" "$ST/$f"
done
python3 - "$W3/index.html" "$ST/index.html" <<'PY'
import sys, re
src, dst = sys.argv[1], sys.argv[2]
html = open(src, encoding="utf-8").read()
tag = ('<!-- 敘事縫線：文案層（twinseam.js，幕 5/6/8/9/16/17）＋收尾層'
       '（scenes/seam_ending.js，幕 18）。刪掉這兩行就完全還原。 -->\n'
       '<script src="twinseam.js"></script>\n'
       '<script src="scenes/seam_ending.js"></script>\n')
assert html.count("</body>") == 1, "找不到唯一的 </body>"
html = html.replace("</body>", tag + "</body>")
open(dst, "w", encoding="utf-8").write(html)
print("derived ok, bytes", len(html))
PY
ls -la "$ST"
