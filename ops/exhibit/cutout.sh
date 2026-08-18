#!/bin/bash
# 去背——**必須用淹沒填色，不准用 -transparent white**。
#
# 為什麼（2026-08-18 實測，不是理論）：
#   `-transparent white` 是全域取代 ⇒ **主體身上任何白的東西一起被拿掉**。
#   實測那三個角色：中間那個手上的紙疊整片變透明、左邊那個奶油色的鞋子
#   被吃掉一塊、眼白也破了。
#
#   **而且遠看完全看不出來。** 如果拿去生六十張，會得到六十張有破洞的圖
#   然後回報成功——那正是這個專案一路在防的形狀。
#
# 淹沒填色只吃**從四角連通進來**的背景，主體內部的白留得住。
#
# 用法：cutout.sh <輸入.png> [輸出.png]
set -u
IN="$1"
OUT="${2:-${IN%.png}_cut.png}"
FUZZ="${FUZZ:-8%}"

magick "$IN" -alpha set -fill none -fuzz "$FUZZ" \
  -draw "alpha 0,0 floodfill" \
  -draw "alpha %[fx:w-1],0 floodfill" \
  -draw "alpha 0,%[fx:h-1] floodfill" \
  -draw "alpha %[fx:w-1],%[fx:h-1] floodfill" \
  -trim +repage "$OUT"

# 驗後果不驗前提：檢查真的有透明像素，而且主體沒被吃掉太多
python3 - "$OUT" <<'PY'
import subprocess, sys
p = sys.argv[1]
def fx(expr):
    return float(subprocess.run(["magick", p, "-format", expr, "info:"],
                                capture_output=True, text=True).stdout or 0)
op = fx("%[fx:mean.a]")          # 平均不透明度（0=全透明 1=全實心）
w, h = int(fx("%[fx:w]")), int(fx("%[fx:h]"))
print(f"  {p}  {w}x{h}  不透明比例 {op:.2f}")
if op > 0.97:
    print("  ⚠ 幾乎沒有透明像素——背景可能沒被吃掉（純白？fuzz 太小？）")
elif op < 0.25:
    print("  ⚠ 不透明比例過低——主體可能被吃掉了，去看圖不要只看數字")
PY
