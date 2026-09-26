#!/bin/bash
# run_one.sh <name> <scenario> <with_agents_md:0|1>
set -u
R=/tmp/claude-0/review_v3; NAME=$1; SCN=$2; AMD=$3; PORT=18391
OUT=$R/out/$NAME; rm -rf $OUT; mkdir -p $OUT
P=$R/proj_$NAME; rm -rf $P; mkdir -p $P; cd $P; git init -q .
for i in $(seq 1 10); do echo "r$i,v$((i%3))"; done > data.csv
if [ "$AMD" = 1 ]; then printf '# Project guidelines\n\n- Break large changes into at most 6 steps.\n- Keep commits small.\n' > AGENTS.md; fi
git add -A && git -c user.email=a@b -c user.name=a commit -qm init
rm -rf $R/home/.vacant/trace
MOCK_SCENARIO=$SCN MOCK_LOG=$OUT/mock.jsonl MOCK_BODIES=$OUT/bodies python3 /tmp/claude-0/review_v3/mock_model.py $PORT > $OUT/mock.out 2>&1 &
MOCK=$!
for i in $(seq 50); do (echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null && break; sleep 0.2; done
HOME=$R/home PYTHONPATH=$R/budget_src timeout 300 node /tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/agents/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js \
  -p --mode json --provider mock --model mock-model "Count the number of lines in data.csv and write the count to answer.txt." > $OUT/pi_stdout.jsonl 2> $OUT/pi_stderr.txt
echo "pi exit $?" > $OUT/pi_exit
kill $MOCK 2>/dev/null
cp $R/home/.vacant/trace/projects/*/delivery.* $OUT/ 2>/dev/null
cp $R/home/.vacant/trace/projects/*/chain.jsonl $OUT/ 2>/dev/null
ls $P > $OUT/proj_files.txt
