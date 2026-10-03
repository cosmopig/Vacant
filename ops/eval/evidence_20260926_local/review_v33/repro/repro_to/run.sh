#!/bin/bash
# usage: run.sh <version-dir> <label> <slow-seconds or empty>
V=$1; L=$2; S=$3
R=/tmp/claude-0/review_v33/repro_to
W=$R/w_$L
rm -rf $W; mkdir -p $W/home $W/vh/adapters $W/app/data
echo '{"agents": {}, "mode": "evidence"}' > $W/vh/adapters/install.json
printf 'date,amount\n2026-07-01,1200\n2026-07-02,845\n' > $W/app/data/sales.csv
cd $W
PYTHONPATH=$V /home/user/Vacant/.venv/bin/python - <<PY
import json, sys
from vacant_network.adapters import agents as AG
import vacant_network; assert vacant_network.__file__.startswith("$V"), vacant_network.__file__
argv = [sys.executable, "-m", "vacant_network", "hook", "pi"]
open("ext.mjs","w").write(AG.PI_EXTENSION % {"argv": json.dumps(argv), "timeout_ms": 600000,
      "budget_re": "/" + AG.BUDGET_RE_SRC.replace("/", r"\/") + "/i"})
PY
sed "s#__APP__#$W/app#g" $R/drive.tmpl.mjs > drive.mjs
echo "--- $L: timeout line in generated ext:"; grep -n "TIMEOUT.stop : undefined" ext.mjs
env HOME=$W/home VACANT_HOME=$W/vh PYTHONPATH=$R/site:$V SLOW_EVIDENCE=$S SLOW_LOG=$W/slow.log /opt/node22/bin/node drive.mjs
echo "node exit=$? at $(date +%s.%N)"
cat $W/slow.log 2>/dev/null || echo "(no slow log)"
cd $R && env HOME=$W/home VACANT_HOME=$W/vh PYTHONPATH=$V /home/user/Vacant/.venv/bin/python $R/peek.py $W/app
