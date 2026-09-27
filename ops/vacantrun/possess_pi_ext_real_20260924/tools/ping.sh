#!/usr/bin/env bash
# 一格 ping：pi -p "Reply with exactly: OK"（完整路徑、命令列零個 vacant）。
# 用法：ping.sh <label> <key_form> [export_env_key:0|1]
set -u
source /var/tmp/vacant_piext_20260924/env.sh
label=$1; form=$2; envkey=${3:-0}
L=$R/cells/$label; mkdir -p $L
$PY $R/tools/set_key_form.py $form > $L/key_form.txt
[ "$envkey" = 1 ] && export MYLAB_KEY="$(cat $R/secret)"
rb=$(wc -l < $R/logs/relay.jsonl)
jf=$HOME/.vacant/possess/proxyd/wire/index.jsonl; [ -f $jf ] || jf=
jb=$( [ -n "$jf" ] && wc -l < "$jf" || echo 0)
hb=$(ls $HOME/.vacant/possess/hooks/ 2>/dev/null | wc -l)
mkdir -p $R/scratch_cwd && cd $R/scratch_cwd
t0=$(date +%s.%N)
timeout 300 $PI -p "Reply with exactly: OK" < /dev/null > $L/stdout 2> $L/stderr
rc=$?
t1=$(date +%s.%N)
echo $rc > $L/rc; python3 -c "print(round($t1-$t0,2))" > $L/wall_s
tail -n +$((rb+1)) $R/logs/relay.jsonl > $L/relay_slice.jsonl
[ -n "$jf" ] && tail -n +$((jb+1)) "$jf" > $L/proxyd_slice.jsonl
ls -t $HOME/.vacant/possess/hooks/ 2>/dev/null | head -1 > $L/hook_file.txt
echo "== $label rc=$rc wall=$(cat $L/wall_s)s stdout=$(head -c 80 $L/stdout | tr '\n' ' ')"
python3 - "$L" <<'PY'
import json,sys,collections,pathlib
L=pathlib.Path(sys.argv[1])
rs=[json.loads(x) for x in open(L/"relay_slice.jsonl")]
c=collections.Counter((r["method"],r["path"].split("?")[0],r["auth"],r.get("status")) for r in rs)
for k,v in sorted(c.items()): print("   relay",v,"×",*k)
p=L/"proxyd_slice.jsonl"
if p.exists():
    ps=[json.loads(x) for x in open(p) if x.strip()]
    c2=collections.Counter((r.get("method"),str(r.get("path","")).split("?")[0],r.get("status")) for r in ps)
    for k,v in sorted(c2.items()): print("   proxyd",v,"×",*k)
PY
