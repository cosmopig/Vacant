#!/usr/bin/env bash
# vacant-dev（Ubuntu 24.04，root）一鍵佈署：系統套件 → 建 wheel（與 Colab 同法）→ vm_setup → 題目就位 → 代理（g1003／g1004）。
# 用法：sudo bash setup_vd.sh /var/tmp/vd_deploy（已解開的 bundle 目錄）
set -euo pipefail
B=$1; exec > >(tee -a /var/tmp/vd_setup.log) 2>&1
date -u +%FT%TZ
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq pipx python3-pandas python3-numpy xz-utils zstd bc >/dev/null
python3 -c 'import pandas; print("pandas", pandas.__version__)'
mkdir -p /srv/eval /opt/eval/bin /opt/eval/wheel; chmod 700 /srv/eval
# wheel：uv 0.8.17＋setuptools 84.0.0＋SOURCE_DATE_EPOCH（同 Colab）
if [ ! -f $B/wheel/built.sha256 ]; then
  python3 -m venv /root/uvvenv && /root/uvvenv/bin/pip install -q uv==0.8.17
  rm -rf $B/wsrc $B/wheel && mkdir -p $B/wsrc $B/wheel && tar -xf $B/wheel_src_e4da5ebc.tar -C $B/wsrc
  echo 'setuptools==84.0.0' > $B/bc.txt
  (cd $B/wsrc && SOURCE_DATE_EPOCH=$(cat ../source_date_epoch.txt) /root/uvvenv/bin/uv build --wheel -b ../bc.txt -o ../wheel) > $B/wheel/build.log 2>&1
  sha256sum $B/wheel/*.whl | tee $B/wheel/built.sha256
fi
W=$(ls $B/wheel/*.whl); GOT=$(cut -d' ' -f1 $B/wheel/built.sha256)
python3 - "$W" $B/wheel_src_e4da5ebc.tar <<'PY'
import json, sys, tarfile, zipfile
z = zipfile.ZipFile(sys.argv[1]); t = tarfile.open(sys.argv[2])
git = {m.name: t.extractfile(m).read() for m in t.getmembers() if m.isfile() and m.name.startswith("vacant_network/")}
names = [n for n in z.namelist() if n.startswith("vacant_network/")]
bad = [n for n in names if z.read(n) != git.get(n)]
print(json.dumps({"wheel": len(names), "git": len(git), "mismatch": len(bad)}))
sys.exit(0 if not bad and len(names) == len(git) else 1)
PY
[ "$GOT" = 92ddc44d7bb545b9f3c81d923286a952d3fa23b9d2f3b81d6f530fe9aedfbc1f ] && echo "WHEEL_SHA_MATCH_COLAB" || echo "WHEEL_SHA_DIFFERENT $GOT（114 檔比對判定同一產品）"
cp -r $B/bin/. /opt/eval/bin/ && chmod -R a+rX /opt/eval && chmod 755 /opt/eval/bin/*.sh
mkdir -p /srv/eval/staged && cp -a $B/staged/. /srv/eval/staged/
# DABstep 資料：硬連結（79 題共用一份 23 MB），逐題核 sha256
(cd $B/dabdata && sha256sum *) > /srv/eval/dabdata.sha256
for t in /srv/eval/staged/dabstep/*; do mkdir -p $t/workspace/data; for f in $B/dabdata/*; do ln -f $f $t/workspace/data/; done; (cd $t/workspace/data && sha256sum -c --quiet /srv/eval/dabdata.sha256); done
chmod -R go-rwx /srv/eval/staged; cp $B/plan_*.json /srv/eval/
bash /opt/eval/bin/vm_setup.sh "$W" "$GOT"
mkdir -p /srv/eval/proxy
cat > /srv/eval/proxy.json <<'J'
{"models": {"gemma-4-12b-it-qat": {}}, "upstreams": {"g1003": "http://100.119.113.56:1234", "g1004": "http://100.86.226.21:1234"},
 "host_id": "vacant-dev", "retry_waits": [5, 15, 30, 60], "budget_usd": 1000000}
J
pkill -f "opt/eval/bin/orproxy.py" || true; sleep 1
setsid nohup python3 /opt/eval/bin/orproxy.py --config /srv/eval/proxy.json --out /srv/eval/proxy --host 127.0.0.1 --port 18900 > /srv/eval/proxy.log 2>&1 < /dev/null &
sleep 2; head -2 /srv/eval/proxy.log
echo VD_SETUP_OK
