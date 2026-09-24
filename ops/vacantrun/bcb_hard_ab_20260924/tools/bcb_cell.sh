#!/usr/bin/env bash
# 一格 ＝ 一題 × 一組 × 第幾次（GATE 的重抽是 a2、a3）。用法：bcb_cell.sh <OFF|CH|GATE> <task_id> <attempt>
set -u
source /var/tmp/vacant_piext_20260924/bcb_tools/bcb_common.sh
arm=$1; tid=$2; att=${3:-1}; safe=$(echo "$tid" | tr '/' '_'); name=${arm}_${safe}_a${att}
L=$OUT/cells/$name; ws=$OUT/ws/$name
rm -rf "$L" "$ws"; mkdir -p "$L" "$ws"
cp "$TPL/$safe/goal.md" "$TPL/$safe/contract.md" "$TPL/$safe/run_tests.sh" "$ws/"; cp -r "$TPL/$safe/tests_visible" "$ws/"
want="$(cd "$TPL/$safe" && find . -type f | sort | tr '\n' ' ')"; got="$(cd "$ws" && find . -type f | sort | tr '\n' ' ')"
[ "$want" = "$got" ] || { echo "工作區與樣板不一致：$got" >&2; echo 3 > $L/rc; exit 3; }
if [ $arm = OFF ]; then base_env $P/home_off; else base_env $P/home_on; fi
jf=$P/home_on/.vacant/possess/proxyd/wire/index.jsonl; jb=$(wc -l < $jf 2>/dev/null || echo 0)
{ echo "arm=$arm task=$tid attempt=$att backend=$BACKEND model=$MODEL"; echo "prompt=$PROMPT"; echo "containment=bwrap(ro /, rw ws+HOME, tmpfs /tmp, unshare-pid, net shared)"; date -u +%FT%TZ; } > $L/argv.txt
t0=$(date +%s.%N)
case $arm in
  OFF|CH) ( cd "$ws" && timeout 1500 bw "$ws" $PI -p "$PROMPT" < /dev/null > $L/stdout 2> $L/stderr ); rc=$? ;;
  GATE)   ( cd "$ws" && export VACANT_SUITE="$TPL/$safe/tests_visible" VACANT_TEST_TIMEOUT=${BCB_TEST_TIMEOUT:-120} \
              VACANT_ACCEPT_PATH_PREPEND="$VENV/bin" VACANT_ACCEPT_MEMORY_MB=2048 \
              VACANT_AGENT_MODEL="$MODEL" OPENAI_API_KEY="${PILOT_KEY:-lm-studio}" && \
            timeout 1500 bw "$ws" $HOME/.vacant/possess/bin/pi -p "$PROMPT" < /dev/null > $L/stdout 2> $L/stderr ); rc=$? ;;
esac
t1=$(date +%s.%N)
echo $rc > $L/rc; python3 -c "print(round($t1-$t0,1))" > $L/wall_s
[ $arm = CH ] && [ -f $jf ] && tail -n +$((jb+1)) $jf > $L/proxyd_slice.jsonl
if [ $arm = GATE ]; then
  rd=$(grep -ho "收據 [^ ]*" $L/stderr | tail -1 | cut -d" " -f2)
  [ -n "$rd" ] && [ -d "$rd" ] && { echo "$rd" > $L/run_dir.txt; cp "$rd"/wire_*/index.jsonl $L/gate_wire_index.jsonl 2>/dev/null; cp "$rd"/run_*.json $L/ 2>/dev/null; }
fi
[ -f "$ws/solution.py" ] && cp "$ws/solution.py" $L/delivered_solution.py
# 計分（run 結束之後；隱藏測試永遠不進工作區）：可見與隱藏都只拿 solution.py 去量
sc=$(mktemp -d); cp -r "$TPL/$safe/tests_visible" "$TPL/$safe/run_tests.sh" $sc/; [ -f "$ws/solution.py" ] && cp "$ws/solution.py" $sc/
( cd $sc && ulimit -v 2097152 && timeout 300 sh run_tests.sh > $L/visible.out 2>&1; echo $? > $L/visible.rc ); rm -rf $sc
$VENV/bin/python $T/bcb_score.py "$HIDDEN/$safe/test_hidden.py" "$ws/solution.py" > $L/hidden.json 2> $L/hidden.stderr
echo "=== $BACKEND $name rc=$rc wall=$(cat $L/wall_s)s visible_rc=$(cat $L/visible.rc) hidden=$(tr -d '\n ' < $L/hidden.json | head -c 50)"
