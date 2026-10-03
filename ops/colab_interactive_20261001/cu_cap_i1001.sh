#!/usr/bin/env bash
# cu_cap_i1001 — 運算單位（CU）上限（本機，常駐迴圈）：預註冊第十節的「軟上限＋硬上限」。
#   軟上限：已花 ≥ --soft ⇒ 在 VM 放 /srv/eval/STOP（driver 不再開新單位，**已開始的單位照樣跑完**）。
#   硬上限：已花 ≥ --hard ⇒ 先放 STOP、再放 /srv/eval/DRIVER_DONE（packer 立刻做最後一包＋Drive 鏡像核對）、等 ALL_DONE（最多
#           CU_CAP_GRACE_S 秒，預設 180）、（有 --sync-dir 時）本機同步一次、然後 `colab stop`。**進行中、還沒寫 DONE 的單位就此丟掉**
#           （它們不進任何分析；預註冊第十節-硬上限要求報告把它們列出來）。
# 「已花」取兩個估計的較大值：
#   餘額估計  ＝ --b0（`colab new` 之前讀到的餘額）－ 現在的 `colab usage` 餘額（讀不到就不用這一項、不當成 0）；
#   時間估計  ＝ --rate（預設 8.9 CU/小時，G4）× （現在 － --t0）/ 3600。`colab usage` 可能延遲或失敗，時間估計是不靠它的保險。
# 用法：cu_cap_i1001.sh <session> --b0 <CU> --t0 <epoch 秒> --soft <CU> --hard <CU> [--rate 8.9] [--interval 300]
#                       [--sync-dir <sync_i1001.sh 的本機目錄>] [--max-loops N] [--dry-run]
# 這支不取代 autostop_i1001.sh（批次收完自動關機）；兩支同時開，誰先到誰關（colab stop 重複呼叫無害）。
# 環境變數（測試用）：COLAB（colab CLI）、CU_CAP_NOW（假的現在 epoch 秒）、CU_CAP_GRACE_S、CU_CAP_POLL_S、SYNC_SH。
# 誠實邊界：`colab usage` 的「Current balance:」格式沿用第一批 cu_guard.sh 的剖析；這支在本機用假的 colab 驗過邏輯，**沒有碰過真的 colab CLI**。
set -u
usage() { sed -n '2,17p' "$0" >&2; exit 2; }
[ $# -ge 1 ] || usage
S=$1; shift
B0=""; T0=""; SOFT=""; HARD=""; RATE=8.9; INT=300; SYNCD=""; MAXL=0; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --b0) B0=$2; shift 2;; --t0) T0=$2; shift 2;; --soft) SOFT=$2; shift 2;; --hard) HARD=$2; shift 2;;
    --rate) RATE=$2; shift 2;; --interval) INT=$2; shift 2;; --sync-dir) SYNCD=$2; shift 2;;
    --max-loops) MAXL=$2; shift 2;; --dry-run) DRY=1; shift;; *) echo "unknown option $1" >&2; usage;;
  esac
done
[ -n "$B0" ] && [ -n "$T0" ] && [ -n "$SOFT" ] && [ -n "$HARD" ] || usage
awk -v s="$SOFT" -v h="$HARD" 'BEGIN{exit !(s+0 > 0 && h+0 > s+0)}' || { echo "需要 0 < --soft < --hard" >&2; exit 2; }
COLAB=${COLAB:-colab}
HERE=$(cd "$(dirname "$0")" && pwd)
SYNC_SH=${SYNC_SH:-$HERE/sync_i1001.sh}
GRACE=${CU_CAP_GRACE_S:-180}; GPOLL=${CU_CAP_POLL_S:-10}
TMPD=$(mktemp -d); trap 'rm -rf "$TMPD"' EXIT

vm_console() {   # vm_console '<一行 shell>'：在 VM 的 console 跑一行（背景＋最多 40 秒；同 cu_guard.sh）
  if [ "$DRY" = 1 ]; then echo "DRY-RUN: console << $1"; return 0; fi
  printf '%s\nexit\n' "$1" | "$COLAB" console -s "$S" >/dev/null 2>&1 &
  local p=$!; local i
  for i in $(seq 1 40); do kill -0 "$p" 2>/dev/null || break; sleep 1; done
  kill "$p" 2>/dev/null; wait "$p" 2>/dev/null; return 0
}
now() { if [ -n "${CU_CAP_NOW:-}" ]; then echo "$CU_CAP_NOW"; else date +%s; fi; }
soft_done=0; loops=0; unread=0
while true; do
  loops=$((loops + 1)); t=$(now)
  bal=$("$COLAB" usage 2>/dev/null | sed -n 's/.*Current balance: \([0-9.]*\).*/\1/p' | head -n 1)
  spent_t=$(awk -v r="$RATE" -v n="$t" -v t0="$T0" 'BEGIN{printf "%.2f", r*(n-t0)/3600.0}')
  if [ -n "$bal" ]; then
    unread=0
    spent_b=$(awk -v b0="$B0" -v b="$bal" 'BEGIN{printf "%.2f", b0-b}')
  else
    unread=$((unread + 1)); spent_b="?"
  fi
  spent=$(awk -v a="$spent_t" -v b="${spent_b/\?/0}" 'BEGIN{printf "%.2f", (a>b)?a:b}')
  echo "$(date -u +%FT%TZ) balance=${bal:-?} spent_by_balance=${spent_b} spent_by_time=${spent_t} spent=${spent} soft=${SOFT} hard=${HARD}"
  [ "$unread" -ge 6 ] && echo "$(date -u +%FT%TZ) WARN: colab usage 連續 ${unread} 次讀不到餘額——只剩時間估計在護欄"
  over_soft=$(awk -v s="$spent" -v x="$SOFT" 'BEGIN{print (s>=x)?1:0}')
  over_hard=$(awk -v s="$spent" -v x="$HARD" 'BEGIN{print (s>=x)?1:0}')
  if [ "$over_soft" = 1 ] && [ "$soft_done" = 0 ]; then
    vm_console "echo \"CU cap soft: spent ${spent} >= ${SOFT} at \$(date -u +%FT%TZ)\" > /srv/eval/STOP"
    soft_done=1; echo "$(date -u +%FT%TZ) SOFT_CAP: STOP 已放（已花 ${spent} ≥ ${SOFT}）；進行中的單位照樣跑完"
  fi
  if [ "$over_hard" = 1 ]; then
    echo "$(date -u +%FT%TZ) HARD_CAP: 已花 ${spent} ≥ ${HARD} ⇒ 收尾後關機"
    vm_console "touch /srv/eval/DRIVER_DONE"
    w=0; got_all=0
    while [ "$DRY" = 0 ] && [ "$w" -lt "$GRACE" ]; do
      if "$COLAB" download -s "$S" /srv/eval/ALL_DONE "$TMPD/all" </dev/null >/dev/null 2>&1 && [ -f "$TMPD/all" ]; then got_all=1; break; fi
      sleep "$GPOLL"; w=$((w + GPOLL))
    done
    echo "$(date -u +%FT%TZ) ALL_DONE=${got_all}（等了 ${w}s；0＝沒等到，照樣關機：資料以 Drive 鏡像與 VM 已打包的 chunk 為準）"
    if [ -n "$SYNCD" ] && [ "$DRY" = 0 ]; then bash "$SYNC_SH" "$S" "$SYNCD" 1 --once </dev/null || true; fi
    if [ "$DRY" = 1 ]; then echo "DRY-RUN: colab stop -s $S"; exit 0; fi
    for k in 1 2 3; do "$COLAB" stop -s "$S" </dev/null && { echo "$(date -u +%FT%TZ) STOPPED ${S}（硬上限）"; exit 6; }; sleep 10; done
    echo "$(date -u +%FT%TZ) colab stop 連續失敗——手動關掉！" >&2; exit 5
  fi
  [ "$MAXL" != 0 ] && [ "$loops" -ge "$MAXL" ] && exit 0
  sleep "$INT"
done
