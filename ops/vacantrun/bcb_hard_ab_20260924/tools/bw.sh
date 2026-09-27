#!/usr/bin/env bash
# 圍住 agent（預註冊補充 A1）：根目錄唯讀；只有這一格的工作區（$1）、這個後端的 HOME、私有 /tmp 可寫；
# 獨立 PID 空間（kill 碰不到外面）；網路保留（要連模型）。四組一樣。
# ⚠ 這是保護機器，不是安全邊界：網路是通的。  用法：bw.sh <工作區> <指令…>
ws=$1; shift
exec bwrap --ro-bind / / --dev /dev --proc /proc --tmpfs /tmp \
     --bind "$ws" "$ws" --bind "$HOME" "$HOME" \
     --unshare-pid --die-with-parent --chdir "$ws" "$@"
