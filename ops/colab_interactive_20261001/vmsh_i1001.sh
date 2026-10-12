#!/usr/bin/env bash
# vmsh_i1001 — 在 Colab VM 上跑一段 bash 並把輸出帶回來（本機端；走 upload＋console＋download，不走 kernel 的 `colab exec`）。
# 用法：vmsh_i1001.sh <session> [--wait 秒] [--tail N] ( -c '<指令>' | <本機腳本檔> )
#   --wait 秒   最多等這麼久（預設 120）；等不到結束標記就印目前的輸出、結束碼 124（**VM 上的指令不會被殺**）
#   --tail N    只印輸出的最後 N 行（預設全印）
# 結束碼：VM 上那段指令的結束碼；124＝等逾時；125＝上傳失敗。
# 流程：指令寫成本機暫存檔 → colab upload 到 VM 的 <目錄>/vmsh_<pid>_<時間>.sh → 在 console（同一個 tmux 殼）跑
#       `bash 那個檔 > .out 2>&1; echo "<帶本次 ID 的標記>=$?" >> .out` → 每 VMSH_POLL 秒（預設 5）colab download 那個 .out、看最後一行是不是那個標記；
#       有就印輸出（不含那一行）、以那個碼結束。
# 為什麼：2026-09-27 `colab exec`（kernel）隨機卡住好幾分鐘；console＋檔案介面是當時證明穩的路（campaign 的 vmrun.sh）。
#         vmrun.sh 只跑 python 檔、固定等一個秒數；這支跑 bash、拿得到結束碼、做完就回（不多等）。
# 長跑的程式（vLLM 安裝、driver）：在指令裡 `setsid nohup … > log 2>&1 < /dev/null &`，立刻回來，再用另一個 vmsh 看 log。
#   ⚠ console 是同一個 tmux 殼：前一段沒跑完時，新的指令會排在後面——所以長跑的一定要丟背景。
# 環境變數：COLAB（colab CLI，預設 colab）、VMSH_DIR（VM 上放暫存檔的目錄，預設 /content；測試用）、VMSH_POLL（輪詢秒數）。
# 誠實邊界：邏輯在本機用假的 colab 驗過（tests/test_colab_i1001_ops.py）；**沒有碰過真的 colab CLI**。
set -u
usage() { sed -n '2,12p' "$0" >&2; exit 2; }
[ $# -ge 2 ] || usage
S=$1; shift
WAIT=120; TAILN=0; CMD=""; FILE=""; HAVE_CMD=0
while [ $# -gt 0 ]; do
  case "$1" in
    --wait) WAIT=$2; shift 2;;
    --tail) TAILN=$2; shift 2;;
    -c) CMD=$2; HAVE_CMD=1; shift 2;;
    *) FILE=$1; shift;;
  esac
done
COLAB=${COLAB:-colab}; RD=${VMSH_DIR:-/content}; POLL=${VMSH_POLL:-5}
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
if [ "$HAVE_CMD" = 1 ]; then printf '%s\n' "$CMD" > "$T/cmd.sh"
elif [ -n "$FILE" ] && [ -f "$FILE" ]; then cp "$FILE" "$T/cmd.sh"
else usage; fi
ID="vmsh_$$_$(date +%s)"
"$COLAB" upload -s "$S" "$T/cmd.sh" "${RD}/${ID}.sh" </dev/null >/dev/null 2>&1 || { echo "VMSH_UPLOAD_FAIL" >&2; exit 125; }
MARK="__vmsh_rc_${ID}__"      # 結束標記帶這一次的 ID：指令自己印出 `__rc=…` 之類的字也不會被當成結束
( printf 'bash %s/%s.sh > %s/%s.out 2>&1; echo "%s=$?" >> %s/%s.out\nexit\n' "$RD" "$ID" "$RD" "$ID" "$MARK" "$RD" "$ID" | "$COLAB" console -s "$S" >/dev/null 2>&1 ) &
CP=$!
rc=124; waited=0
while :; do
  if "$COLAB" download -s "$S" "${RD}/${ID}.out" "$T/out" </dev/null >/dev/null 2>&1 && [ -s "$T/out" ] \
     && tail -n 1 "$T/out" | grep -Eq "^${MARK}=[0-9]+\$"; then
    rc=$(tail -n 1 "$T/out" | sed "s/^${MARK}=//"); break
  fi
  [ "$waited" -ge "$WAIT" ] && break
  sleep "$POLL"; waited=$((waited + POLL))
done
kill "$CP" 2>/dev/null; wait "$CP" 2>/dev/null
if [ -s "$T/out" ]; then
  if tail -n 1 "$T/out" | grep -Eq "^${MARK}=[0-9]+\$"; then sed '$d' "$T/out" > "$T/body"; else cp "$T/out" "$T/body"; fi
  if [ "$TAILN" -gt 0 ]; then tail -n "$TAILN" "$T/body"; else cat "$T/body"; fi
fi
[ "$rc" = 124 ] && echo "VMSH_WAIT_TIMEOUT（${WAIT}s；VM 上的指令還在跑或根本沒開始——${RD}/${ID}.out 是它的輸出）" >&2
exit "$rc"
