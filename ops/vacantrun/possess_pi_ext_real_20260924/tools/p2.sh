#!/usr/bin/env bash
# §七 重驗一格：新鮮 HOME → 使用者的 pi 設定（provider 指別名中繼）→ 沒有 Vacant 先 ping（基線）
# → vacant install（不給 --upstream）→ ping → 視 KEEP 決定要不要 uninstall。
# 用法：p2.sh <label> <old|new> <provider_baseUrl> [KEEP=1]
set -u
R=/var/tmp/vacant_piext_20260924
label=$1; ver=$2; base=$3; keep=${4:-0}
REPO=$R/repo; [ "$ver" = new ] && REPO=$R/repo_new
export HOME=$R/home_p2_$label
export PATH=$R/pi/node_modules/.bin:/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=$REPO
unset OPENAI_BASE_URL OPENAI_API_BASE OPENAI_API_KEY ANTHROPIC_BASE_URL ANTHROPIC_API_KEY VACANT_AGENT_MODEL PI_CODING_AGENT_DIR
export MYLAB_KEY="$(cat $R/secret)"
PI=$R/pi/node_modules/.bin/pi; PY=/usr/bin/python3
L=$R/cells/p2_$label; rm -rf "$L" "$HOME"; mkdir -p "$L" "$HOME/.pi/agent"
$PY - "$HOME" "$base" <<'PYW'
import json, sys, pathlib
d = pathlib.Path(sys.argv[1]) / ".pi/agent"
(d / "models.json").write_text(json.dumps({"providers": {"homelab": {
    "baseUrl": sys.argv[2], "api": "openai-completions", "apiKey": "$MYLAB_KEY",
    "compat": {"supportsDeveloperRole": False, "supportsReasoningEffort": False},
    "models": [{"id": "lab-gemma", "name": "lab-gemma", "contextWindow": 131072, "maxTokens": 16384}]}}}, indent=2) + "\n")
(d / "settings.json").write_text(json.dumps({"defaultProvider": "homelab", "defaultModel": "lab-gemma"}, indent=2) + "\n")
PYW
echo "code=$ver git=$(cat $REPO/GIT_HEAD) provider_baseUrl=$base" > $L/setup.txt
sha256sum $HOME/.pi/agent/models.json $HOME/.pi/agent/settings.json > $L/pre_sha256.txt
slice() {  # $1=name  $2=relay-lines-before  $3=journal-lines-before
  tail -n +$(($2+1)) $R/logs/relay_alias.jsonl > $L/$1.relay.jsonl
  [ -f $HOME/.vacant/possess/proxyd/wire/index.jsonl ] && tail -n +$(($3+1)) $HOME/.vacant/possess/proxyd/wire/index.jsonl > $L/$1.proxyd.jsonl
  $PY - $L/$1 <<'PYS'
import json, sys, os, collections
p = sys.argv[1]
rs = [json.loads(l) for l in open(p + ".relay.jsonl") if l.strip()]
print("   relay :", [(r["method"], r.get("auth"), r.get("model_requested"), r.get("status")) for r in rs if r["method"] == "POST"])
if os.path.exists(p + ".proxyd.jsonl"):
    ps = [json.loads(l) for l in open(p + ".proxyd.jsonl") if l.strip()]
    print("   proxyd:", [(r["method"], r.get("status")) for r in ps if r["method"] == "POST"])
PYS
}
mkdir -p $R/scratch_p2 && cd $R/scratch_p2
# 1) 基線：沒有 Vacant
rb=$(wc -l < $R/logs/relay_alias.jsonl)
timeout 120 $PI -p "Reply with exactly: OK" < /dev/null > $L/bare.stdout 2> $L/bare.stderr; echo $? > $L/bare.rc
echo "== [$label] bare rc=$(cat $L/bare.rc) out=$(head -c 40 $L/bare.stdout | tr '\n' ' ')"; slice bare $rb 0
# 2) 裝（不給 --upstream）
$PY -m vacant_network.vrun.possess install --home $HOME --agent pi --service bare --port 18797 --no-shell-probe > $L/install.stdout 2> $L/install.stderr
echo "== [$label] install rc=$?"; grep -E "^上游" $L/install.stdout | sed 's/^/   /'
grep -nE "^const (UPSTREAM|KEY_FROM|BAKED_MODELS|DEFAULT_MODEL) " $HOME/.pi/agent/extensions/vacant.ts | sed 's/^/   /'
# 3) 有 Vacant
rb=$(wc -l < $R/logs/relay_alias.jsonl); jb=$(wc -l < $HOME/.vacant/possess/proxyd/wire/index.jsonl 2>/dev/null || echo 0)
timeout 120 $PI -p "Reply with exactly: OK" < /dev/null > $L/vacant.stdout 2> $L/vacant.stderr; echo $? > $L/vacant.rc
echo "== [$label] vacant rc=$(cat $L/vacant.rc) out=$(head -c 60 $L/vacant.stdout | tr '\n' ' ') err=$(head -c 160 $L/vacant.stderr | tr '\n' ' ')"; slice vacant $rb $jb
$PY -m vacant_network.vrun.possess status --home $HOME > $L/status.txt 2>&1; grep -E "^  pi  .*中介" $L/status.txt | sed 's/^/   /'
if [ "$keep" != 1 ]; then
  $PY -m vacant_network.vrun.possess uninstall --home $HOME > $L/uninstall.out 2>&1; echo "== [$label] uninstall rc=$?"
  sha256sum -c $L/pre_sha256.txt 2>&1 | sed 's/^/   /'
fi
