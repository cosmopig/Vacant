#!/bin/bash
# 負控制：**把它關掉，截圖看得出差別**。
#
#   bash shoot_neg.sh <base_url> <輸出目錄>
#
# 三條開關各拍一張，接線後的同一頁、同一台瀏覽器，只差網址參數：
#   ?seam=0     文案層不掛 ⇒ s04 回到烤死的「世界多了一個人／那是你託付的需求」
#   ?seamend=0  收尾層不掛 ⇒ s11 回到「這 371 格會一直重播」
#   ?arrive=0   抵達層關掉 ⇒ waiting 恆空 ⇒ 幕 7′ 連觸發條件都沒有
#
# 🔴 這三張的價值在於**跟接線後那一批擺在一起看**：字不一樣，就證明那兩層
#    真的在承重，而不是剛好烤死字串長得一樣。
set -u
BASE="$1"; OUTDIR="$2"
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$OUTDIR"
RES="$OUTDIR/shoot_all_neg.txt"
: > "$RES"
PORT=9450
FAIL=0

shoot () {
  local name="$1" q="$2" expect="$3"
  PORT=$((PORT + 1))
  node "$HERE/shoot_wire.mjs" "$OUTDIR/NEG_${name}.png" "${BASE}?${q}" 9000 "$PORT" "$expect" \
    > "$OUTDIR/NEG_${name}.log" 2>&1
  local rc=$?
  local line
  line=$(python3 -c "
import json
try:
    d=json.load(open('$OUTDIR/NEG_${name}.json'))
    print('\t'.join([str(d.get('head')), str(d.get('sub')), str(d.get('title_ov_source')),
                     'twinseam=%s' % d.get('layer_twinseam_loaded'),
                     'seamend=%s' % d.get('layer_seamending_loaded')]))
except Exception as e:
    print('（讀不到）\t\t\t\t')
" 2>/dev/null)
  printf '%s\trc=%s\t%s\n' "$name" "$rc" "$line" >> "$RES"
  echo "[$name] rc=$rc  $line"
  [ "$rc" -eq 0 ] || FAIL=$((FAIL + 1))
}

shoot seam0_s04    "scene=s04&seam=0&seamshot=enter"  s04
shoot seamend0_s11 "scene=s11&seamend=0"              s11
shoot arrive0_wait "scene=s11&arrive=0&seamwait=2"    s11

echo "---"
echo "失敗格數=$FAIL  結果表=$RES"
exit $FAIL
