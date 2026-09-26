D=/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/design/piexp
PIBIN=/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/agents/node_modules/.bin/pi
MOCK_PORT=18941; SINK_PORT=18942
fresh() { R=$D/runs/$1; rm -rf "$R"; mkdir -p "$R/agent/extensions" "$R/proj" "$R/sessions"; cp $D/probe.ts "$R/agent/extensions/probe.ts"
  cat > "$R/agent/models.json" <<J
{"providers":{"harbor-endpoint":{"baseUrl":"http://127.0.0.1:$MOCK_PORT/v1","api":"openai-completions","apiKey":"\$OPENROUTER_API_KEY",
 "compat":{"supportsDeveloperRole":false,"supportsReasoningEffort":false},
 "models":[{"id":"mock-model","name":"mock-model","contextWindow":131072,"maxTokens":8192}]}}}
J
}
startmock() { pkill -f "$D/mock.py" 2>/dev/null; sleep 0.3
  MOCK_LOG="$R/mock.jsonl" MOCK_SCRIPT="$1" MOCK_PORT=$MOCK_PORT SINK_PORT=$SINK_PORT nohup python3 "$D/mock.py" > "$R/mock.stdout" 2>&1 &
  for i in $(seq 1 30); do curl -s -o /dev/null "http://127.0.0.1:$MOCK_PORT/v1/models" && break; sleep 0.1; done; : > "$R/mock.jsonl"; }
# Mirrors Harbor's command shape: PI_CODING_AGENT_DIR=... pi --print --mode json --session-dir ... --provider harbor-endpoint --model ... --extension max-turns.ts <instr>
runpi() { (cd "$R/proj" && timeout ${TMO:-90} env -i PATH=/opt/node22/bin:/usr/bin:/bin HOME="$R" OPENROUTER_API_KEY=sk-dummy \
   PI_CODING_AGENT_DIR="$R/agent" NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
   HTTP_PROXY=http://127.0.0.1:$SINK_PORT HTTPS_PROXY=http://127.0.0.1:$SINK_PORT \
   PROBE_LOG="$R/probe.jsonl" PI_SKIP_VERSION_CHECK=1 "${XENV[@]}" \
   "$PIBIN" --print --mode json --session-dir "$R/sessions" --provider harbor-endpoint --model mock-model "$@" < /dev/null > "$R/stdout.jsonl" 2> "$R/stderr.txt"; echo "exit=$?" > "$R/exit.txt") }
