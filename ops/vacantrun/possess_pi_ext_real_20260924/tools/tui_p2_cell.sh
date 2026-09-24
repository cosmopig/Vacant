#!/usr/bin/env bash
# §七 重驗 #3 #4：在 p2_new_local 那個（還裝著的）HOME 開互動 TUI。
set -u
R=/var/tmp/vacant_piext_20260924
export HOME=$R/home_p2_new_local
export PATH=$R/pi/node_modules/.bin:/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=$R/repo_new
unset OPENAI_BASE_URL OPENAI_API_BASE OPENAI_API_KEY ANTHROPIC_BASE_URL ANTHROPIC_API_KEY VACANT_AGENT_MODEL PI_CODING_AGENT_DIR
export MYLAB_KEY="$(cat $R/secret)"
PI=$R/pi/node_modules/.bin/pi
L=$R/cells/p2_new_local_tui; rm -rf $L; mkdir -p $L
ls $HOME/.vacant/possess/hooks/ | sort > $L/hooks_before.txt
mkdir -p $R/scratch_p2 && cd $R/scratch_p2
timeout 240 python3 $R/tools/tui_p2.py $L/tui.raw $L/marks.json $PI > $L/driver.out 2>&1
echo "driver rc=$? $(cat $L/driver.out)"
ls $HOME/.vacant/possess/hooks/ | sort | comm -13 $L/hooks_before.txt - > $L/hook_files_new.txt
for h in $(cat $L/hook_files_new.txt); do cp $HOME/.vacant/possess/hooks/$h $L/; done
python3 - "$L" <<'PY'
import json, sys, pathlib, hashlib
L = pathlib.Path(sys.argv[1]); marks = json.load(open(L / "marks.json"))
def h(o): return hashlib.sha256(json.dumps(o, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
for f in (L / "hook_files_new.txt").read_text().split():
    for l in open(L / f):
        d = json.loads(l); after = [m["label"] for m in marks if m["t"] <= d["ts"]]
        print(f"   hook {d['event']:<24} after mark: {after[-1] if after else '-'}")
PY
python3 $R/tools/tui_decode.py $L 5 | grep -v "^    ─" | sed -n '/===== ctrl+p #1/,$p'
