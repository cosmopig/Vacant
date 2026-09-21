#!/bin/bash
# 證明「截圖跑的那一頁 ＝ 某一版 index.html ＋ wire_in.patch 的那三行，其餘一 byte 不差」。
#
# ⚠ 為什麼不直接拿「現在的 index.html」去比：`index.html` 今天**每幾分鐘就被別的
#   代理改一次**（本條進行中量到 sha256 變了四次）。拿一個會動的東西當基準，
#   比出來的 DIFFERENT 只是在說「別人剛剛存了檔」，不是在說我的改動不乾淨。
#   ⇒ 基準改成**從截圖用的那一頁自己身上剝掉那三行**，得到它的 base，
#     再證明 base + patch == 截圖用的那一頁。這條等式與外面的改動無關，**可重現**。
#   現況 sha256 另外印出來，只當「那一刻活的是哪一版」的紀錄。
set -u
HM=/Users/cosmopig/Documents/GitHub/vacant_hm
SC=/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad
STAGE="$SC/stage/index.html"
T="$SC/patchtest"
rm -rf "$T"; mkdir -p "$T/world3"

# 1) 從截圖用的那一頁剝掉本條加的三行 ⇒ 它的 base
python3 - "$STAGE" "$T/world3/index.html" <<'PY'
import sys
src, dst = sys.argv[1], sys.argv[2]
lines = open(src, encoding="utf-8").read().split("\n")
drop = [i for i, l in enumerate(lines)
        if l.startswith("<!-- 敘事縫線：")
        or l == '<script src="twinseam.js"></script>'
        or l == '<script src="scenes/seam_ending.js"></script>']
assert len(drop) == 3, f"預期剝掉 3 行，實際 {len(drop)}"
out = [l for i, l in enumerate(lines) if i not in set(drop)]
open(dst, "w", encoding="utf-8").write("\n".join(out))
print(f"剝掉 3 行（第 {[i+1 for i in drop]} 行）")
PY

echo "=== sha256 ==="
shasum -a 256 "$T/world3/index.html" | sed 's|$|   (截圖那一頁的 base ＝ 剝掉三行之後)|'
shasum -a 256 "$STAGE"               | sed 's|$|   (截圖跑的那一頁)|'
shasum -a 256 "$HM/world3/index.html" | sed 's|$|   (展件現況，只當紀錄：別的代理一直在改)|'

# 2) 對 base 套一次 patch，證明得到的就是截圖那一頁
P=/Users/cosmopig/Documents/GitHub/Vacant/.claude/worktrees/wf_32a45899-6ee-5/ops/exhibit/twin/evidence_visible_20260921/narrative_order/wire_in.patch
cd "$T" || exit 2
if patch -p1 --silent < "$P"; then
  echo "=== base + wire_in.patch vs 截圖那一頁 ==="
  if cmp -s "$T/world3/index.html" "$STAGE"; then
    echo "IDENTICAL —— 截圖跑的就是「那一版 index.html ＋ 這個 patch」，沒有別的改動"
  else
    echo "DIFFERENT —— 差異如下（不准說成一樣）："
    diff "$T/world3/index.html" "$STAGE" | head -20
  fi
else
  echo "patch 套不到 base 上（不准說成一樣）"
fi

# 3) 現況與截圖 base 的差（＝別人在這段期間改了什麼，與本條無關）
echo "=== 展件現況 vs 截圖那一頁的 base（別人的改動，本條沒有碰）==="
diff "$HM/world3/index.html" "$SC/patchtest_base_ref" > /dev/null 2>&1
diff "$HM/world3/index.html" "$STAGE" | grep -c '^[<>]' | sed 's|^|差異行數（含本條那三行）：|'
