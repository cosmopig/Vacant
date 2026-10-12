#!/usr/bin/env bash
# VM 端一鍵佈署（root）：解開 /content/deploy.tgz → 在 Linux 上重建 v3.6.1 wheel 並驗雜湊 → 工具與題目就位 → 起記帳代理。
# 用法：deploy_vm.sh [上游名，預設 g4] [vLLM 基底網址，預設 http://127.0.0.1:18000]
# 題目（含隱藏測試）解到 /srv/eval/staged（root 700），bundle 解完就從 /content 刪掉。
set -euo pipefail
UP=${1:-g4}; UPURL=${2:-http://127.0.0.1:18000}
EXPECT=4ec156d6648d214baa9bc5be4093f8b8731112f16a6ee61b6118d70b41def0b4
mkdir -p /root/deploy /srv/eval; chmod 700 /root/deploy /srv/eval
tar -xzf /content/deploy.tgz -C /root/deploy && rm -f /content/deploy.tgz
cd /root/deploy

# 1) wheel：Linux 上、uv 0.8.17、setuptools 84.0.0、SOURCE_DATE_EPOCH＝c27641c6 的 commit 時間（交接檔 §4 的做法）
if [ ! -f wheel/built.sha256 ]; then
  # Colab 的 python3 沒有 ensurepip（venv 建不起來）⇒ uv 裝進獨立目錄
  python3 -m pip install -q --target /root/uvpkg uv==0.8.17
  rm -rf wsrc wheel && mkdir -p wsrc wheel && tar -xf wheel_src_c27641c6.tar -C wsrc
  echo 'setuptools==84.0.0' > bc.txt
  (cd wsrc && SOURCE_DATE_EPOCH=$(cat ../source_date_epoch.txt) /root/uvpkg/bin/uv build --wheel -b ../bc.txt -o ../wheel) > wheel/build.log 2>&1
  sha256sum wheel/*.whl | tee wheel/built.sha256
fi
W=$(ls wheel/*.whl); GOT=$(cut -d' ' -f1 wheel/built.sha256)
# 逐檔比對（不論雜湊對不對得上都做）：wheel 裡的 vacant_network/ 每個檔 vs git archive 的原檔
python3 - "$W" wheel_src_c27641c6.tar > wheel/filecmp.json <<'EOF'
import json, sys, tarfile, zipfile
z = zipfile.ZipFile(sys.argv[1]); t = tarfile.open(sys.argv[2])
git = {m.name: t.extractfile(m).read() for m in t.getmembers() if m.isfile() and m.name.startswith("vacant_network/")}
names = [n for n in z.namelist() if n.startswith("vacant_network/")]
bad = [n for n in names if z.read(n) != git.get(n)]
print(json.dumps({"wheel": len(names), "git": len(git), "mismatch": len(bad), "missing": sorted(set(git) - set(names))}))
EOF
cat wheel/filecmp.json
[ "$GOT" = "$EXPECT" ] && echo "WHEEL_SHA_MATCH $GOT" || echo "WHEEL_SHA_DIFFERENT $GOT (expected $EXPECT) — 用 114 檔比對判定同一產品"
python3 -c "import json,sys; d=json.load(open('wheel/filecmp.json')); sys.exit(0 if d['mismatch']==0 and not d['missing'] and d['wheel']==d['git'] else 1)"

# 2) 工具就位（/opt/eval/bin 所有人可讀；agent 看得到、改不了）
mkdir -p /opt/eval/bin && cp -r bin/. /opt/eval/bin/ && chmod -R a+rX /opt/eval && chmod 755 /opt/eval/bin/*.sh
# 3) 題目就位（root 700）
mkdir -p /srv/eval/staged && cp -a staged/. /srv/eval/staged/ && chmod -R go-rwx /srv/eval/staged
# 4) 環境佈置（pi、node、bwrap、pipx、圍牆自我檢查）
bash /opt/eval/bin/vm_setup.sh "$W" "$GOT"
# 5) 記帳代理（本機模式、只聽 127.0.0.1；上游用代號）
mkdir -p /srv/eval/proxy
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
