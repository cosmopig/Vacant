#!/usr/bin/env bash
# 執行端一次性準備。**不改機器的共用狀態**，除了：
#   · 建一個專屬 uid（1001，跑完刪掉）——一跑一 uid 才讓計數器乾淨（邊界 3）
#   · 一個 /var/tmp 下的工作目錄
# iptables 的改動**不在這裡**（那是 apply.sh，有 watchdog ＋ 快照還原）。
set -uo pipefail
R=/var/tmp/vbypass
AGENT_UID=1001
mkdir -p "$R"/{bin,logs,work,ws,rd,out}
chmod 777 "$R" "$R/work" "$R/ws" "$R/logs"
mkdir -p "$R/work/home"; chmod 777 "$R/work/home"

if ! getent passwd "$AGENT_UID" >/dev/null; then
  sudo -n useradd -u "$AGENT_UID" -M -d "$R/work/home" -s /bin/bash vbagent \
    && echo "建了 uid=$AGENT_UID (vbagent)"
else
  echo "uid=$AGENT_UID 已存在：$(getent passwd $AGENT_UID)"
fi

echo "=== 版本逐字落盤（鐵律 3）==="
export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:/home/user1/.local/bin:$PATH
{
  echo "host=$(hostname)  date=$(date -Is)"
  echo "kernel=$(uname -a)"
  echo "python3=$(python3 -V 2>&1)"
  echo "node=$(node -v 2>&1)"
  for a in pi opencode claude codex; do
    printf '%-9s path=%s version=%s\n' "$a" "$(command -v $a || echo MISSING)" \
      "$($a --version 2>&1 | head -1)"
  done
  if [ -x "$R/hv/bin/hermes" ]; then
    printf '%-9s path=%s version=%s\n' hermes "$R/hv/bin/hermes" \
      "$($R/hv/bin/hermes --version 2>&1 | head -1)"
  else
    echo "hermes    path=MISSING（跑 setup.sh --hermes 裝）"
  fi
  echo "iptables=$(sudo -n iptables --version 2>&1)"
  echo "df=$(df -h / | tail -1)"
} | tee "$R/out/env.txt"

if [ "${1:-}" = "--hermes" ]; then
  echo "=== 裝 Hermes Agent（venv，約 204 MB）==="
  python3 -m venv "$R/hv" && "$R/hv/bin/pip" -q install hermes-agent \
    && "$R/hv/bin/hermes" --version
  chmod -R a+rX "$R/hv"
fi
echo "=== df 收尾 ==="; df -h /
