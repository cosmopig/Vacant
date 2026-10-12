#!/bin/bash
# usage: run.sh <name> <slow_seconds or 0> <FINAL 0|1>
set -u
D=/tmp/claude-0/review_v33/indep_slowend
R=$D/runs/$1; rm -rf "$R"; mkdir -p "$R"
PY=/home/user/Vacant/.venv/bin/python
export HOME=$R/home VACANT_HOME=$R/vh
unset VACANT_TRACE VACANT_MODE VACANT_HOOK_NO_STOP VACANT_FEEDBACK_MODE
PYTHONPATH=${OLDPP:-} $PY $D/build.py "$R" >/dev/null
cp $D/drive.mjs $R/
export APP=$R/app SLOW_LOG=$R/slow.log FINAL=$3 PYTHONPATH=${OLDPP:+$OLDPP:}$D/sc
if [ "$2" != "0" ]; then export SLOW_CHECK_S=$2; else unset SLOW_CHECK_S; fi
cd $R && /opt/node22/bin/node drive.mjs
echo "--- right after session_shutdown returned ($(date +%s))"
$PY $D/inspect_rec.py "$R"
