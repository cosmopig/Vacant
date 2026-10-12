#!/usr/bin/env bash
# 以某一格自己的使用者、在 bwrap 圍牆裡跑一個指令（root 呼叫）。用法：sandbox.sh <使用者> <格子目錄> [VAR=值 …] -- <指令…>
#
# 圍牆（2026-09-27 在 Colab G4 上實測可行的組合）：
# - 根目錄唯讀（--ro-bind / /）；可寫的只有這一格的 home、/tmp、/app（工作區）、/logs/agent（pi 的 session 紀錄），
#   四個都是 <格子目錄> 底下、屬於這個使用者（700）的目錄。/dev/shm 另開一塊私有 tmpfs。
# - /home、/content、/root、/srv 蓋成空的 tmpfs：看不到別格的 home、看不到 Colab 的檔案（模型、log）、看不到題庫與隱藏測試。
#   （蓋掉之後再 bind 自己的目錄：bwrap 的來源路徑在外面的檔案系統解析。）
# - 每格是**新的 Linux 使用者**：就算圍牆有漏，Unix 權限也擋住別格（home 700）與 /srv/eval（root 700）。
# - 環境變數從零開始（env -i），只給這裡列的與呼叫端傳進來的。
# ⚠ 誠實邊界：
#   1. **沒有獨立 PID 空間**：Colab 的容器不准 bwrap 掛新的 /proc（`Can't mount proc`），所以 /proc 是 bind 進來的；
#      agent 看得到別的行程（看不到別的使用者的 environ）。收尾用 `pkill -u <使用者>`，殺得乾淨。
#   2. **網路是通的**：agent 要連模型（本機代理），也可以 pip install。這是保護別格與題庫，不是資安邊界。
#   3. 沒有 cgroup：CPU／記憶體沒有硬上限（計分另外用 RLIMIT_AS）。
set -u
U=$1; C=$2; shift 2
EXTRA=()
while [ $# -gt 0 ] && [ "$1" != -- ]; do EXTRA+=("$1"); shift; done
shift  # --
H=/home/$U
exec runuser -u "$U" -- env -i \
  HOME=$H USER=$U LOGNAME=$U SHELL=/bin/bash LANG=C.UTF-8 LC_ALL=C.UTF-8 TERM=dumb TZ=UTC MPLBACKEND=Agg \
  PATH=$H/.local/bin:/opt/eval/pi/bin:/opt/eval/node/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  "${EXTRA[@]}" \
  bwrap --ro-bind / / --dev-bind /dev /dev --tmpfs /dev/shm --bind /proc /proc \
    --tmpfs /home --tmpfs /content --tmpfs /root --tmpfs /srv \
    --bind "$C/home" "$H" --bind "$C/tmp" /tmp --bind "$C/app" /app --bind "$C/agentlog" /logs/agent \
    --chdir /app --die-with-parent -- "$@"
