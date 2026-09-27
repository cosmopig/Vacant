#!/usr/bin/env bash
# 互動 TUI 一格（常駐 extension 那條路、真模型）。判準：掛鉤日誌 vacant_off 筆數、proxyd／relay 切片。
set -u
source /var/tmp/vacant_piext_20260924/env.sh
export MYLAB_KEY="$(cat $R/secret)"
L=$R/cells/${1:-tui_real}; mkdir -p $L
jf=$HOME/.vacant/possess/proxyd/wire/index.jsonl
rb=$(wc -l < $R/logs/relay.jsonl); jb=$(wc -l < $jf)
ls $HOME/.vacant/possess/hooks/ | sort > $L/hooks_before.txt
mkdir -p $R/scratch_tui && cd $R/scratch_tui
timeout 240 python3 $R/tools/${DRIVER:-tui_real.py} $L/tui.raw $L/marks.json $PI > $L/driver.out 2>&1
echo "driver rc=$? $(cat $L/driver.out)"
tail -n +$((rb+1)) $R/logs/relay.jsonl > $L/relay_slice.jsonl
tail -n +$((jb+1)) $jf > $L/proxyd_slice.jsonl
ls $HOME/.vacant/possess/hooks/ | sort | comm -13 $L/hooks_before.txt - > $L/hook_files_new.txt
for h in $(cat $L/hook_files_new.txt); do cp $HOME/.vacant/possess/hooks/$h $L/; done
python3 - "$L" <<'PY'
import json, sys, pathlib, collections
L = pathlib.Path(sys.argv[1])
marks = json.load(open(L / "marks.json"))
for h in (L / "hook_files_new.txt").read_text().split():
    for l in open(L / h):
        d = json.loads(l)
        after = [m["label"] for m in marks if m["t"] <= d["ts"]]
        print(f"   hook {d['event']:<24} after mark: {after[-1] if after else '-'}")
for n in ("relay_slice", "proxyd_slice"):
    rs = [json.loads(l) for l in open(L / f"{n}.jsonl") if l.strip()]
    print(" ", n, dict(collections.Counter((r["method"], r["path"].split("?")[0], r.get("auth"), r.get("status")) for r in rs)))
PY
