#!/usr/bin/env bash
# VM 端一鍵佈署（root）。用法（bundle 已解在 /root/deploy）：
#   mkdir -p /root/deploy && tar -xzf /content/deploy_i1001.tgz -C /root/deploy && bash /root/deploy/bin/deploy_i1001.sh [上游名 g4] [vLLM 基底網址]
# 做的事：核對 SHA256SUMS → 工具就位（/opt/eval/bin）→ 題目就位（/srv/eval/staged，root 700）→ tmux →
#   vm_setup.sh（第一批的，逐字：bwrap／pipx／node／pi 0.87.1／wheel／圍牆自我檢查）→ bridge 的 venv（裝同一個 wheel）→
#   記帳代理（本機模式、只聽 127.0.0.1:18900）。**不起 vLLM**（backend/setup_vllm.sh、serve_vllm.sh 照第一批）。
# 下一步：python3 /opt/eval/bin/vm_selfcheck.py（機制替身、不花 GPU）→ launch_i1001.sh。
set -euo pipefail
UP=${1:-g4}; UPURL=${2:-http://127.0.0.1:18000}
R=$(cd "$(dirname "$0")/.." && pwd)
cd "$R"
sha256sum -c SHA256SUMS --quiet && echo "bundle sha256 ok"
mkdir -p /opt/eval/bin /srv/eval
cp -r bin/. /opt/eval/bin/
chmod -R a+rX /opt/eval; chmod 755 /opt/eval/bin/*.sh
mkdir -p /srv/eval/staged && cp -a staged/. /srv/eval/staged/
mkdir -p /srv/eval/cells /srv/eval/receivers /srv/eval/proxy /srv/eval/archive
chmod -R go-rwx /srv/eval; chmod 700 /srv/eval/receivers
# tmux（vm_setup.sh 不裝）。互動式 pi 的每一格都跑在自己的 tmux server 裡
command -v tmux >/dev/null || { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq tmux >/dev/null; }
tmux -V
W=$(ls wheel/*.whl | head -1); WSHA=$(cut -d' ' -f1 wheel/wheel.sha256)
[ "$(sha256sum "$W" | cut -d' ' -f1)" = "$WSHA" ] || { echo "wheel sha256 不符" >&2; exit 2; }
bash /opt/eval/bin/vm_setup.sh "$R/$W" "$WSHA"
# bridge（K 組的收件端，root 跑）：獨立 venv 裝同一個 wheel；bridge 檔放在 <根>/ops/eval/ ——它用 parents[2] 當 import 根，
# 所以不能放在有別的 vacant_network 的地方
python3 -m venv /opt/eval/bridgevenv
/opt/eval/bridgevenv/bin/pip install -q "$R/$W"
mkdir -p /opt/eval/bridge/ops/eval && cp bridge/ops/eval/native_acceptance_bridge.py /opt/eval/bridge/ops/eval/
chmod -R a+rX /opt/eval/bridge /opt/eval/bridgevenv
/opt/eval/bridgevenv/bin/python -c "import vacant_network, cryptography; print('bridge venv ok:', vacant_network.__file__)"
# 題庫端（任務題庫的計分器用 pandas／numpy；agent 端也要）。⚠ 要用「沒有特權、乾淨環境的使用者」檢查（計分與 agent 都是這樣跑）：
# root 的 user site（~/.local）在圍牆裡看不到，用 root 檢查會漏掉「依賴只裝在 root 的 user site」（2026-10-01 本機：dateutil 缺 ⇒ databench 全判 0）
CHK="runuser -u nobody -- env -i HOME=/nonexistent PATH=/usr/local/bin:/usr/bin:/bin"
$CHK python3 -c "import pandas, numpy; print('pandas', pandas.__version__, 'numpy', numpy.__version__, '(as nobody, clean env)')" \
  || { echo "ERROR: 圍牆裡的使用者 import 不了 pandas／numpy（常見：依賴裝在 root 的 user site）；databench 計分會全 void——pip3 install --ignore-installed pandas numpy python-dateutil（裝到系統 site）" >&2; exit 5; }
$CHK python3 -c "import scipy; print('scipy', scipy.__version__)" \
  || echo "WARN: 沒有 scipy（dabench／databench 的 agent 端可能要；計分器不需要）"
# 記帳代理（本機模式、只聽 127.0.0.1；上游用代號）——同 deploy_vm.sh
cat > /srv/eval/proxy.json <<EOF2
{"models": {"gemma-4-12b-it-qat": {}}, "upstreams": {"$UP": "$UPURL"}, "host_id": "colab-$UP",
 "retry_waits": [5, 15, 30, 60], "budget_usd": 1000000}
EOF2
if ! curl -s -o /dev/null -w '%{http_code}' -X POST localhost:18900/t/ping/up/$UP/api/v1/chat/completions 2>/dev/null | grep -q 4; then
  nohup python3 /opt/eval/bin/orproxy.py --config /srv/eval/proxy.json --out /srv/eval/proxy --host 127.0.0.1 --port 18900 > /srv/eval/proxy.log 2>&1 &
  sleep 2
fi
head -2 /srv/eval/proxy.log
echo DEPLOY_OK
