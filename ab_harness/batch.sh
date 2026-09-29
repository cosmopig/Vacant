#!/bin/bash
# batch.sh — run the paired batch.
#
#   A  plain     opencode alone. Nothing else in the path.
#   B  zero-cfg  `vacant install` (defaults: mode=evidence) has put Vacant's
#                native opencode plugin in the agent's global config. Same
#                byte-identical command as arm A.
#                ⚠ MEASURED, NOT ASSUMED: on opencode 1.18.33 this arm records
#                the accountable trace but the v3.7 Stop check never fires --
#                the opencode plugin registers only chat.message /
#                tool.execute.before / tool.execute.after / session_end, and no
#                stop-equivalent, so zerostop.stop() is unreachable. It is kept
#                in the batch anyway so the claim is evidenced, not asserted.
#   C  bridge    the 3.7 branch's own native acceptance bridge: prepare pins the
#                suite and signs the contract lock BEFORE the agent sees the
#                prompt; the agent runs natively (no wire mediation, so full
#                opencode behaviour); judge freezes the candidate, re-verifies
#                the pinned suite on the frozen copy, signs a decision; only an
#                accepted artifact_sha256 can be released.
#
# A and C run in phase 1 -- neither touches the agent's global config. B runs
# alone in phase 2, because `vacant install` writes a global plugin that would
# contaminate A and C if they were live.
#
# Same model, byte-identical prompt, byte-identical starting workspace in all
# arms. Hidden checks are never in any workspace; grade.py applies them only
# after the batch.
set -u
ROOT=/home/user1/ab-20260928
PY=$ROOT/venv/bin/python
BR=$ROOT/bridge/native_acceptance_bridge.py
MODEL=openrouter/stealth/space-bunny-alpha
JOBS=${JOBS:-3}
ARM=${1:-all}
export PATH=$HOME/.opencode/bin:$PATH
export OPENROUTER_API_KEY=$(cat $ROOT/.openrouter_key)

PROMPT='Read goal.md. Implement solution.py with the requested top-level function. You may use the visible tests and run_tests.sh. Finish with the file saved.'

arm_c () {
  t=$1
  c=$ROOT/runs/${t}__C
  rh=$ROOT/receivers/${t}
  rm -rf "$rh" "$c"; mkdir -p "$c"
  ws=$c/workspace; mkdir -p "$ws"
  cp -r $ROOT/bank_templates/$t/. "$ws/"
  if ! $PY $BR prepare --workspace "$ws" --task-id "$t" --mode repair \
        --suite "$ws/tests_visible" --receiver-home "$rh" \
        --insecure-same-account > "$c/prepare.json" 2> "$c/prepare.err"; then
    echo "C $t PREPARE_FAILED"; return 1
  fi
  ( cd "$ws" && timeout 2400 opencode run --format json -m $MODEL "$PROMPT" \
      > "$c/agent.jsonl" 2> "$c/agent.err" )
  echo $? > "$c/agent_rc.txt"
  ( cd "$ws" && $PY $BR judge --workspace "$ws" --attempt 1 --receiver-home "$rh" \
      > "$c/judge.json" 2> "$c/judge.err" ); echo $? > "$c/judge_rc.txt"
  sha=$( $PY -c "import json;print(json.load(open('$c/judge.json')).get('artifact_sha256') or '')" 2>/dev/null )
  echo "${sha:-none}" > "$c/artifact_sha256.txt"
  if [ -n "$sha" ]; then
    ( cd "$ws" && $PY $BR release --workspace "$ws" --artifact "$sha" \
        --receiver-home "$rh" > "$c/release.json" 2> "$c/release.err" )
    echo $? > "$c/release_rc.txt"
  fi
  cp -r "$rh" "$c/receiver_home" 2>/dev/null
  echo "C $t done (agent_rc=$(cat $c/agent_rc.txt) judge=$(cat $c/judge_rc.txt))"
}

arm_ab () {
  a=$1; t=$2
  $PY $ROOT/ab_harness/run_one.py --task "$t" --arm "$a" --model $MODEL
}

pool () {   # pool <arm>
  a=$1
  for d in $ROOT/bank_templates/*/; do
    t=$(basename "$d")
    while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do wait -n 2>/dev/null || sleep 5; done
    if [ "$a" = "C" ]; then arm_c "$t" & else arm_ab "$a" "$t" & fi
  done
  wait
}

case "$ARM" in
  A) echo "=== phase 1: arm A (plain) ==="; pool A ;;
  C) echo "=== phase 1: arm C (bridge gate) ==="; pool C ;;
  AC) echo "=== phase 1: arms A and C ==="; pool A; pool C ;;
  B) echo "=== phase 2: vacant install (defaults) then arm B ==="
     $ROOT/venv/bin/vacant install 2>&1 | tail -3
     pool B ;;
  *) echo "usage: batch.sh {A|C|AC|B}"; exit 2 ;;
esac
echo "=== phase $ARM complete ==="
