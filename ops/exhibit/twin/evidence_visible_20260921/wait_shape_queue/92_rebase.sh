#!/bin/bash
# 把等待態那一批（第二輪＋第三輪）rebase 到 `vacant_hm/world3/index.html` 的**當下**版本。
#
# 為什麼需要這一支：2026-09-21 同一天有十幾個代理在改同一個檔。本輪親眼看到
# `world3/index.html` 在**兩小時內被改了六次**（4262 → 4491 → 4492 → 4498 → 4526 行）。
# **硬套 `patch -p1` 會用 fuzz／offset 套到錯的位置而且退出碼還是 0**（第二輪實測）。
#
# 所以：不要硬套。這一支做的是三方合併——
#   base   ＝ 91_base_world3_index.html（這份 patch 的基底，逐 byte 釘死）
#   theirs ＝ base ＋ 90_…_r3.patch（等待態第二輪＋第三輪）
#   ours   ＝ 你現在那棵樹的 world3/index.html
# 有衝突就先交給 `92b_resolve_update_conflict.py`；那一支**只處理一種**衝突
# （兩邊都在同一個插入點各自插入、基底是空的），其餘一律停下來讓人看。
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
( cd "$WORK/t" && patch -p1 --forward -i "$HERE/90_vacant_hm_wait_shape_r3.patch" )

echo "== 2. 三方合併到你現在那一份"
cp "$HM/world3/index.html" "$WORK/merged.html"
if git merge-file -L 現行 -L 基底 -L 等待態 --diff3 \
     "$WORK/merged.html" "$HERE/91_base_world3_index.html" "$WORK/t/world3/index.html"; then
  echo "   零衝突"
else
  n=$(grep -c '^<<<<<<<' "$WORK/merged.html" || true)
  echo "   有衝突（$n 處）⇒ 交給 92b（它只吃「兩邊各自插入」那一種）"
  python3 "$HERE/92b_resolve_update_conflict.py" "$WORK/merged.html"
fi

echo "== 3. 放回去（world3/index.html ＋ tools/waitcheck.mjs）"
cp "$WORK/merged.html" "$HM/world3/index.html"
cp "$WORK/t/tools/waitcheck.mjs" "$HM/tools/waitcheck.mjs"

echo "== 4. 兩把尺"
( cd "$HM" && node tools/waitcheck.mjs | tail -2 )
( cd "$HM" && node tools/livecheck.mjs | tail -2 )
echo "完成。要還原：git -C $HM checkout -- world3/index.html && rm tools/waitcheck.mjs"
