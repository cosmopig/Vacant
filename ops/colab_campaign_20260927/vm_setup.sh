#!/usr/bin/env bash
# Colab VM 一次性佈置（root）：pi 0.87.1、Vacant wheel、隔離用的 bwrap／pipx、記帳代理。可重跑（冪等）。
# 用法：vm_setup.sh <wheel 路徑> <期望的 wheel sha256>
# 目錄：
#   /opt/eval   （所有人可讀）node 22、pi、wheel、工具腳本——agent 看得到、改不了
#   /srv/eval   （root 700）題庫（含隱藏測試）、代理紀錄、歸檔——agent 看不到
#   /srv/runs   （root 711）每一格一個目錄，裡面的 home／tmp／app／agentlog 屬於那一格自己的使用者（700）
# 為什麼不是 Harbor＋docker：Colab 的 VM 本身就是容器，開不了 dockerd；改用「每格一個新的 Linux 使用者＋bwrap」
# （見 cell.sh 的隔離說明）。pi 的呼叫方式、設定檔、Vacant 的安裝指令逐字照 Harbor 6cb9ff31 的 pi agent
# 與 ops/eval/harbor_vacant.py（redesign 分支）。
set -euo pipefail
WHEEL_SRC=$1; WHEEL_SHA=$2
exec > >(tee -a /srv/setup.log) 2>&1 || true
mkdir -p /opt/eval/bin /opt/eval/wheel /srv/eval /srv/runs /app /logs/agent
chmod 755 /opt/eval /opt/eval/bin /opt/eval/wheel; chmod 700 /srv/eval; chmod 711 /srv/runs
date -u +%FT%TZ

# 1) 系統套件：bwrap（圍牆）、pipx（使用者裝 Vacant 用的就是它）、xz／zstd（歸檔）
if ! command -v bwrap >/dev/null || ! command -v pipx >/dev/null || ! command -v xz >/dev/null; then
  apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq bubblewrap pipx xz-utils zstd >/dev/null
fi
bwrap --version; pipx --version

# 2) node 22（Harbor 用 nvm 裝「22 的最新版」；這裡釘死一個版本裝到 /opt/eval/node，所有格子共用、唯讀）
NODE_V=${NODE_V:-v22.23.2}
if [ ! -x /opt/eval/node/bin/node ]; then
  curl -fsSL -o /tmp/node.tar.xz https://nodejs.org/dist/$NODE_V/node-$NODE_V-linux-x64.tar.xz
  mkdir -p /opt/eval/node && tar -xJf /tmp/node.tar.xz -C /opt/eval/node --strip-components=1 && rm /tmp/node.tar.xz
fi
/opt/eval/node/bin/node -v

# 3) pi 0.87.1（Harbor：npm install -g --ignore-scripts @earendil-works/pi-coding-agent@0.87.1）
if [ "$(PATH=/opt/eval/node/bin:$PATH /opt/eval/pi/bin/pi --version 2>/dev/null | tail -1)" != 0.87.1 ]; then
  PATH=/opt/eval/node/bin:$PATH npm install -g --ignore-scripts --prefix /opt/eval/pi @earendil-works/pi-coding-agent@0.87.1 >/dev/null
fi
PATH=/opt/eval/node/bin:$PATH /opt/eval/pi/bin/pi --version
chmod -R a+rX /opt/eval

# 4) wheel：驗 sha256 後放到 /opt/eval/wheel（所有格子讀同一個檔）
got=$(sha256sum "$WHEEL_SRC" | cut -d' ' -f1)
[ "$got" = "$WHEEL_SHA" ] || { echo "wheel sha256 不符：$got" >&2; exit 2; }
cp "$WHEEL_SRC" /opt/eval/wheel/ && chmod 644 /opt/eval/wheel/*.whl
ls -la /opt/eval/wheel

# 5) 圍牆自我檢查（負控制先跑）：一個臨時使用者讀不到 /srv/eval、讀不到別人的 home，自己的 home 可寫
id probe_a >/dev/null 2>&1 || useradd -M -d /srv/runs/_probe/home -s /bin/bash probe_a
mkdir -p /srv/runs/_probe/{home,tmp,app,agentlog}; chown -R probe_a: /srv/runs/_probe/{home,tmp,app,agentlog}
chmod 700 /srv/runs/_probe/{home,tmp,app,agentlog}
echo secret > /srv/eval/_probe_secret
runuser -u probe_a -- cat /srv/eval/_probe_secret 2>/dev/null && { echo "負控制失敗：讀得到 /srv/eval" >&2; exit 3; } || echo "負控制 OK：/srv/eval 讀不到"
rm -f /srv/eval/_probe_secret
bash /opt/eval/bin/sandbox.sh probe_a /srv/runs/_probe -- bash -c 'touch ~/ok /tmp/ok /app/ok && ls /srv/eval 2>&1 | head -1; ls /content 2>&1 | head -1; ls /home; echo UID=$(id -u) HOME=$HOME'
userdel probe_a 2>/dev/null; rm -rf /srv/runs/_probe
echo SETUP_OK
