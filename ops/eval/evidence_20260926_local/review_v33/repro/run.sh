#!/bin/bash
# usage: run.sh <new|old> <scenario> <tag>
set -e
V=$1; S=$2; TAG=$3
R=/tmp/claude-0/review_v33/runs/$TAG
rm -rf $R; mkdir -p $R/home $R/vh
cp -r /tmp/claude-0/review_v33/template $R/proj
mkdir -p $R/vh/adapters && echo '{"agents": {}, "mode": "evidence"}' > $R/vh/adapters/install.json
cd /tmp/claude-0/review_v33
HOME=$R/home VACANT_HOME=$R/vh /opt/node22/bin/node ${DRIVE:-drive.mjs} /tmp/claude-0/review_v33/ext_$V.mjs $R/proj $S
