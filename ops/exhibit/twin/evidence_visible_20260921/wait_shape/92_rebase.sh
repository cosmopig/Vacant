#!/bin/bash
# 把等待態那一批 rebase 到 `vacant_hm/world3/index.html` 的**當下**版本。
#
# 為什麼需要這一支：2026-09-21 同一天有十幾個代理在改同一個檔。這份 patch 錄好的
# 那一刻（基底 sha256 709d717d…）到你套用的那一刻之間，那個檔很可能又動過——
# 本輪就親眼看到它在 40 分鐘內被改了三次。**硬套會用 fuzz／offset 套到錯的位置
# 而且退出碼還是 0**（本輪實測：套完的檔跟預期的合併結果不相同，但 patch 說成功）。
#
# 所以：不要硬套。這一支做的是三方合併——
#   base   ＝ 91_base_world3_index.html（這份 patch 的基底，逐 byte 釘死）
#   theirs ＝ base ＋ 90_…patch（等待態那一批）
#   ours   ＝ 你現在那棵樹的 world3/index.html
# 有衝突就**停下來讓人看**，不會安靜地選一邊。
#
# 用法：bash 92_rebase.sh <vacant_hm 的路徑>
set -eu
HM="${1:?用法: bash 92_rebase.sh <vacant_hm 路徑>}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
# ⚠ `${WORK}` 的大括號不能省：後面緊接著全形括號，bash 會把它吃進變數名
#   （`set -u` 之下就是 `WORK?: unbound variable`）。實際踩過。
trap 'echo "工作目錄留在 ${WORK}（要自己清）"' EXIT

echo "== 1. 重建 theirs（base ＋ patch）"
mkdir -p "$WORK/t/world3" "$WORK/t/tools"
cp "$HERE/91_base_world3_index.html" "$WORK/t/world3/index.html"
( cd "$WORK/t" && patch -p1 --forward -i "$HERE/90_vacant_hm_wait_shape_rebased.patch" )

echo "== 2. 三方合併到你現在那一份"
cp "$HM/world3/index.html" "$WORK/merged.html"
if git merge-file -L 現行 -L 基底 -L 等待態 --diff3 \
     "$WORK/merged.html" "$HERE/91_base_world3_index.html" "$WORK/t/world3/index.html"; then
  echo "   零衝突"
else
  echo "🔴 有衝突（$(grep -c '^<<<<<<<' "$WORK/merged.html") 處）。"
  echo "   檔在 $WORK/merged.html，自己看過再放回去。**不要盲目接受任何一邊。**"
  exit 2
fi

echo "== 3. 放回去（world3/index.html ＋ tools/waitcheck.mjs）"
cp "$WORK/merged.html" "$HM/world3/index.html"
cp "$WORK/t/tools/waitcheck.mjs" "$HM/tools/waitcheck.mjs"

echo "== 4. 兩把尺"
( cd "$HM" && node tools/waitcheck.mjs | tail -2 )
( cd "$HM" && node tools/livecheck.mjs | tail -2 )
echo "完成。要還原：git -C $HM checkout -- world3/index.html && rm tools/waitcheck.mjs"
