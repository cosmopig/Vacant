#!/usr/bin/env bash
# 假的 colab CLI（本機端到端用；**沒有碰任何真的 Colab**）：把「VM」當成這台機器自己——
#   colab download -s <session> <遠端路徑> <本機路徑>   ⇒ 複製（遠端沒有就回 1）
#   colab stop -s <session>                           ⇒ 只在 $FAKE_COLAB_LOG 記一行（不關任何東西）
#   colab usage                                       ⇒ 印一個固定餘額
set -u
LOG=${FAKE_COLAB_LOG:-/tmp/fake_colab.log}
cmd=${1:-}; shift || true
case "$cmd" in
  download) [ "$1" = -s ] && shift 2; src=$1; dst=$2; [ -f "$src" ] && cp "$src" "$dst" && { echo "download $src" >> "$LOG"; exit 0; }; exit 1 ;;
  stop)     echo "STOP $*" >> "$LOG"; exit 0 ;;
  usage)    echo "Current balance: 100.0" ;;
  *)        echo "fake colab: unsupported $cmd" >&2; exit 2 ;;
esac
