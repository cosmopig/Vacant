#!/bin/bash
# L-fake: pi 0.87.1 + scripted mock model (no network). Reproduces every claim in the findings. Output: results.txt
D=/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/design/piexp
cd $D && source lib.sh
T='[{"tool":"bash","args":{"command":"echo t1"}},{"tool":"bash","args":{"command":"echo t2"}},{"tool":"bash","args":{"command":"echo t3"}},{"tool":"bash","args":{"command":"echo 42 > answer.txt"}},{"text":"done"}]'
F='[{"tool":"bash","args":{"command":"echo 42 > answer.txt"}},{"tool":"bash","args":{"command":"cat answer.txt"}},{"text":"The answer is 42."}]'
{
fresh exp1_abort_inject;      startmock "$T"; XENV=(INJECT_AT=2,3c);            runpi --extension $D/max-turns.ts "TASK"; python3 summ.py $R
fresh exp1b_abort_plain;      startmock "$T"; XENV=(INJECT_AT=);                runpi --extension $D/max-turns.ts "TASK"; python3 summ.py $R
fresh exp2_settled_followup;  startmock "$T"; XENV=(PROBE_MODE=follow INJECT_AT=3c); runpi --extension $D/max-turns.ts "TASK"; python3 summ.py $R
fresh exp3_final_at_cap;      startmock "$F"; XENV=();                          runpi --extension $D/max-turns.ts "TASK"; python3 summ.py $R
fresh exp3b_final_nocap;      startmock "$F"; XENV=();                          runpi "TASK"; python3 summ.py $R
fresh exp4_text_inject_continue; startmock '[{"text":"The answer is 41."},{"text":"Corrected: 42."}]'; XENV=(INJECT_AT=1c); runpi "TASK"; python3 summ.py $R
fresh exp5_slow_settle;       startmock '[{"text":"The answer is 42."}]'; XENV=(PROBE_MODE=slow SLOW_MS=75000); TMO=150 runpi "TASK"; python3 summ.py $R
fresh exp6_child_pi;          startmock '[{"text":"done"}]'; XENV=(PROBE_MODE=child); runpi --extension $D/max-turns.ts "TASK"; python3 summ.py $R; find $R/sessions $R/agent -name "*.jsonl" | sed "s|$R/|  session file: |"
fresh exp7_agentend_followup; startmock "$T"; XENV=(PROBE_MODE=endfollow);       runpi --extension $D/max-turns.ts "TASK"; python3 summ.py $R; grep -c '"followUp":\["VACANT' $R/stdout.jsonl | sed 's/^/  queue_update lines with queued followUp: /'
fresh exp7b_agentend_plain;   startmock "$T"; XENV=(PROBE_MODE=endplain);        runpi --extension $D/max-turns.ts "TASK"; python3 summ.py $R
} 2>&1 | grep -v '^\[\|Terminated' > $D/results.txt
pkill -f "$D/mock.py"
