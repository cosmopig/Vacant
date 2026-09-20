#!/usr/bin/env bash
# twinanchor 端到端：錨定＋負控制，一鍵重跑。
#
# 判準紀律：
#   * **每一個綠燈都有負控制。** 先證明「整條重算 / 截斷」之後 twinstore 自己
#     還是綠的（弱點屬實），再證明錨抓得到。沒有前者，後者的紅燈沒有對象。
#   * **不用 `cmd | tee f` 取退出碼**（那會拿到 tee 的）。一律先落盤再取 `$?`。
#   * 全部在暫存目錄裡跑，**不碰展場那個 store**。
#
# 用法：
#   bash ops/exhibit/twin/e2e_anchor.sh                       # 離線，出口①③④
#   bash ops/exhibit/twin/e2e_anchor.sh --scp w401@100.119.113.56:C:/Users/w401/anchor/
#        ⚠ scp 那一側要寫 C:/ 方言，ssh 那一側才是 /c/（MSYS 只轉換裸參數）
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
PY="${PY:-python3}"
SCP_TARGET=""
[ "${1:-}" = "--scp" ] && SCP_TARGET="${2:-}"

WORK="$(mktemp -d -t twinanchor_e2e)"
trap 'rm -rf "$WORK"' EXIT
export VACANT_TWIN_DB="$WORK/twinstore.sqlite3"
export VACANT_TWIN_ANCHORS="$WORK/anchors.jsonl"
export VACANT_TWIN_ANCHOR_KEY="$WORK/anchor_key"
cd "$REPO" || exit 9

pass=0; fail=0
chk () { # chk <名稱> <期望 rc> <實際 rc>
  if [ "$2" = "$3" ]; then printf '[PASS] %s (rc=%s)\n' "$1" "$3"; pass=$((pass+1))
  else printf '[FAIL] %s (期望 rc=%s，拿到 %s)\n' "$1" "$2" "$3"; fail=$((fail+1)); fi
}
A () { "$PY" ops/exhibit/twin/twinanchor.py "$@"; }
S () { "$PY" ops/exhibit/twin/twinstore.py "$@"; }

echo "工作目錄：$WORK"
echo
echo "===== 0. 離線自檢（含模組內建的負控制）====="
A selftest > "$WORK/00_selftest.txt" 2>&1; rc=$?
chk "twinanchor selftest" 0 $rc
tail -1 "$WORK/00_selftest.txt"

echo
echo "===== 1. 造一個 store（6 列）＋ 錨定金鑰 ====="
S init > /dev/null 2>&1
for i in 1 2 3 4 5 6; do S note "觀眾 $i 的分身卡" --sub-id "v0$i" > /dev/null 2>&1; done
S stats > "$WORK/01_stats.json" 2>&1; rc=$?
chk "twinstore stats" 0 $rc
A init > "$WORK/02_key.json" 2>&1; rc=$?
chk "twinanchor init（產專用金鑰）" 0 $rc
perm="$(stat -f '%Lp' "$WORK/anchor_key/identity.key" 2>/dev/null)"
if [ -z "$perm" ]; then perm="$(stat -c '%a' "$WORK/anchor_key/identity.key")"; fi
[ "$perm" = "600" ]; chk "私鑰權限 0600（拿到 ${perm}）" 0 $?
PUB="$(cat "$WORK/anchor_key/identity.pub")"

echo
echo "===== 2. emit 一枚錨，取紙條（出口④）====="
A emit --note "開館前" > "$WORK/03_emit.json" 2>&1; rc=$?
chk "emit" 0 $rc
SLIP="$("$PY" -c "
import sys; sys.path.insert(0, '.')
from ops.exhibit.twin import twinanchor as ta
print(ta.slip_of(ta.load_anchors(sys.argv[1])[-1]))
" "$WORK/anchors.jsonl")"
echo "紙條：$SLIP"
A slip --qr "$WORK/anchor_qr.png" > "$WORK/04_slip.json" 2>&1; rc=$?
chk "slip --qr 畫得出 PNG" 0 $rc
head -c 8 "$WORK/anchor_qr.png" | od -An -c | grep -q 'P   N   G'; chk "PNG magic" 0 $?

echo
echo "===== 3. 對照組：沒動過 ⇒ 綠 ====="
A verify --require-pin --pub "$PUB" --slip "$SLIP" > "$WORK/05_clean.json" 2>&1; rc=$?
chk "對照組 verify（釘公鑰＋紙條＋--require-pin）" 0 $rc

echo
echo "===== 4. 三態：沒給 pin ⇒ null，不是 false ====="
A verify > "$WORK/06_nopin.json" 2>&1; rc=$?
chk "沒 pin 的 verify（預設不 require）" 0 $rc
A verify --require-pin > "$WORK/07_requirepin.json" 2>&1; rc=$?
chk "同一個 store 加 --require-pin ⇒ 紅" 1 $rc
"$PY" -c "
import json,sys
d=json.load(open(sys.argv[1]))
assert d['pubkey_pinned'] is None, d['pubkey_pinned']
print('pubkey_pinned =', repr(d['pubkey_pinned']), '（null 不是 false）')
" "$WORK/06_nopin.json"; chk "pubkey_pinned 是 null" 0 $?

echo
echo "===== 5. 出口③：可攜媒體副本 ====="
A mirror --dest "$WORK/usb" > "$WORK/08_mirror.json" 2>&1; rc=$?
chk "mirror --dest" 0 $rc
n="$(find "$WORK/usb" -name identity.key | wc -l | tr -d ' ')"
[ "$n" = "0" ]; chk "副本裡沒有私鑰（找到 $n 個）" 0 $?
[ -s "$WORK/usb/anchor_pub.txt" ]; chk "副本裡有公鑰" 0 $?

if [ -n "$SCP_TARGET" ]; then
  echo
  echo "===== 5b. 出口②：另一台機器（真的 scp）====="
  A mirror --scp "$SCP_TARGET" > "$WORK/09_scp.json" 2>&1; rc=$?
  chk "mirror --scp $SCP_TARGET" 0 $rc
  cat "$WORK/09_scp.json"
else
  echo
  echo "（跳過出口②：沒給 --scp。**這不代表它壞了，也不代表它好** ⇒ 沒量到）"
fi

echo
echo "===== 6. 🔴 負控制 A：整條重算 ====="
"$PY" -c "
import sys; sys.path.insert(0,'.')
from ops.exhibit.twin import twinanchor as ta
print(ta.simulate_full_rewrite(sys.argv[1], drop_seqs=[3]))
" "$WORK/twinstore.sqlite3"
S verify > "$WORK/10_store_after_rewrite.json" 2>&1; rc=$?
chk "前提：重算之後 twinstore 自己還是綠的（弱點屬實）" 0 $rc
A verify --pub "$PUB" --slip "$SLIP" > "$WORK/11_rewrite.json" 2>&1; rc=$?
chk "負控制 A：錨抓到整條重算 ⇒ 紅" 1 $rc
"$PY" -c "
import json,sys
d=json.load(open(sys.argv[1]))
assert d['store_verify']['ok'] is True, 'store 自己應該還是綠的'
for f in d['failures']: print('   紅：', f)
" "$WORK/11_rewrite.json"

echo
echo "===== 7. 🔴 負控制 B：截掉鏈尾 ====="
export VACANT_TWIN_DB="$WORK/t2.sqlite3"
export VACANT_TWIN_ANCHORS="$WORK/t2.anchors.jsonl"
for i in 1 2 3 4 5 6; do S note "觀眾 $i" --sub-id "v0$i" > /dev/null 2>&1; done
A emit > /dev/null 2>&1
"$PY" -c "
import sys; sys.path.insert(0,'.')
from ops.exhibit.twin import twinanchor as ta
print(ta.simulate_truncate(sys.argv[1], 2))
" "$WORK/t2.sqlite3"
S verify > "$WORK/12_store_after_trunc.json" 2>&1; rc=$?
chk "前提：截斷之後 twinstore 自己還是綠的（合法前綴）" 0 $rc
A verify --pub "$PUB" > "$WORK/13_trunc.json" 2>&1; rc=$?
chk "負控制 B：錨抓到截斷 ⇒ 紅" 1 $rc

echo
echo "===== 8. 🔴 負控制 C：fail-closed，鏈紅了就拒簽 ====="
A emit > "$WORK/14_refuse.txt" 2>&1; rc=$?
chk "store 已經被截斷 ⇒ emit 拒簽" 1 $rc
grep -q "拒簽" "$WORK/14_refuse.txt"; chk "拒簽理由有講出來（不是安靜失敗）" 0 $?

echo
echo "============================================"
echo "PASS=$pass  FAIL=$fail"
[ "$fail" = "0" ] && exit 0 || exit 1
