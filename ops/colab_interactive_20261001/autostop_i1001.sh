#!/usr/bin/env bash
# 自動關機（本機，常駐迴圈）：driver 收完（DRIVER_DONE）＋ packer 收完（PACKER_DONE）＋ **最後一個 chunk 的 sha256 已在本機驗過** ⇒
# `colab stop -s <session>`。人類的鐵則：用完資源就關掉、不要空著（2026-09-27 G4 空轉約 1 小時、浪費約 10 CU）。
# 用法：autostop_i1001.sh <colab session 名> <sync_i1001.sh 用的本機目錄> [選項]
#   --interval S        輪詢間隔秒數（預設 60）
#   --drive-grace-s S   DRIVER_DONE＋PACKER_DONE 之後，本機還沒驗完時最多再等 S 秒（預設 2700）；超過了而且 VM 上的 MIRROR_OK 在
#                       （Drive 鏡像每個 chunk 都核對過）⇒ 照樣關機並印警告（資料在 Drive＋VM 的 chunk，不是只靠一份）。0＝不啟用（一直等本機）
#   --stale-warn-s S    progress.jsonl 這麼久沒長、也沒有 DRIVER_DONE ⇒ 印警告（預設 3600；只警告、不自動關——driver 可能在等一個長 session）
#   --max-loops N       測試用：最多輪詢 N 次
#   --dry-run           只印「會關機」，不呼叫 colab stop
# 為什麼分「本機驗過」與「Drive 核對過」：關機之後 VM 上的資料就沒了。本機驗過＝兩份（本機＋Drive）以上；只有 Drive 時要明講。
# 這支從不刪任何東西、只讀旗標與 MANIFEST。`COLAB` 環境變數可指定 colab CLI（測試用假的）。
set -u
S=$1; D=$2; shift 2
INT=60; GRACE=2700; STALE=3600; MAXL=0; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --interval) INT=$2; shift 2;; --drive-grace-s) GRACE=$2; shift 2;; --stale-warn-s) STALE=$2; shift 2;;
    --max-loops) MAXL=$2; shift 2;; --dry-run) DRY=1; shift;; *) echo "unknown option $1" >&2; exit 2;;
  esac
done
COLAB=${COLAB:-colab}
W="$D/.autostop"; mkdir -p "$W"
remote_has() { rm -f "$W/probe"; "$COLAB" download -s "$S" "$1" "$W/probe" </dev/null >/dev/null 2>&1 && [ -f "$W/probe" ]; }
done_since=0; loops=0; last_size=-1; last_change=$(date +%s)
while true; do
  loops=$((loops+1)); now=$(date +%s)
  drv=0; pk=0
  remote_has /srv/eval/DRIVER_DONE && drv=1
  remote_has /srv/eval/archive/PACKER_DONE && pk=1
  if [ $drv = 0 ]; then
    if remote_has /srv/eval/progress.jsonl; then
      sz=$(wc -c < "$W/probe" | tr -d ' ')
      if [ "$sz" != "$last_size" ]; then last_size=$sz; last_change=$now; fi
      if [ $((now-last_change)) -gt "$STALE" ]; then echo "$(date -u +%FT%TZ) WARN: progress.jsonl 已 $((now-last_change)) 秒沒長、也沒有 DRIVER_DONE——driver 還活著嗎？（沒有自動關機）"; fi
    fi
  fi
  if [ $drv = 1 ] && [ $pk = 1 ]; then
    [ "$done_since" = 0 ] && done_since=$now
    # 最終的 MANIFEST（packer 收尾後的）每一個 chunk 都要在本機的 VERIFIED.tsv 裡、sha256 一致
    if "$COLAB" download -s "$S" /srv/eval/archive/MANIFEST.tsv "$W/MANIFEST.final.tsv" </dev/null >/dev/null 2>&1 && [ -s "$W/MANIFEST.final.tsv" ]; then
      missing=0
      while IFS=$'\t' read -r name digest rest; do
        [ -n "$name" ] || continue
        grep -q "^$name	$digest" "$D/VERIFIED.tsv" 2>/dev/null || { missing=$((missing+1)); }
      done < "$W/MANIFEST.final.tsv"
      last=$(tail -1 "$W/MANIFEST.final.tsv" | cut -f1)
      if [ "$missing" = 0 ]; then
        echo "$(date -u +%FT%TZ) DRIVER_DONE＋PACKER_DONE＋最後一個 chunk（${last}）本機 sha256 已驗 ⇒ 關機"
        if [ $DRY = 1 ]; then echo "DRY-RUN: colab stop -s $S"; exit 0; fi
        for k in 1 2 3; do "$COLAB" stop -s "$S" </dev/null && { echo "$(date -u +%FT%TZ) STOPPED $S"; exit 0; }; sleep 10; done
        echo "$(date -u +%FT%TZ) colab stop 連續失敗——手動關掉！" >&2; exit 5
      fi
      echo "$(date -u +%FT%TZ) 已收完，但本機還有 $missing 個 chunk 沒驗（等 sync_i1001.sh）"
      if [ "$GRACE" -gt 0 ] && [ $((now-done_since)) -ge "$GRACE" ] && remote_has /srv/eval/archive/MIRROR_OK; then
        echo "$(date -u +%FT%TZ) WARN: 本機 $missing 個 chunk 沒驗完、已超過 ${GRACE}s，但 Drive 鏡像核對過（MIRROR_OK）⇒ 照樣關機"
        if [ $DRY = 1 ]; then echo "DRY-RUN: colab stop -s $S"; exit 0; fi
        for k in 1 2 3; do "$COLAB" stop -s "$S" </dev/null && { echo "$(date -u +%FT%TZ) STOPPED $S (drive-only backup for $missing chunk(s))"; exit 0; }; sleep 10; done
        exit 5
      fi
    else
      echo "$(date -u +%FT%TZ) 拉不到最終 MANIFEST，下一輪再試"
    fi
  else
    echo "$(date -u +%FT%TZ) driver_done=$drv packer_done=${pk}（還在跑）"
  fi
  [ "$MAXL" != 0 ] && [ "$loops" -ge "$MAXL" ] && exit 0
  sleep "$INT"
done
