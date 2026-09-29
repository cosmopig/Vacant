#!/bin/sh
# W2 A/B: identical stub, identical workspace, identical prompt. The ONLY
# difference between the two runs is one line in the installed plugin:
#
#   const NONINTERACTIVE = process.argv.includes("run");   (as shipped)
#   const NONINTERACTIVE = false;                          (gate removed)
#
# The question this settles: the shipped comment says "opencode run ends at the
# first idle: feedback could never be delivered there, so the stop check would
# only add latency". If that is true, removing the gate can only ADD a stop
# event and cannot change how many prompts the model sees. If it is false, the
# gate-on run and the gate-off run differ in the model's prompt count, and the
# difference is the feedback arriving.
#
# Prints one line of fact per run. No interpretation.
set -u
ROOT=/home/user1/ab-20260928
OC=~/.opencode/bin/opencode
STUB_LOG=/tmp/w2ab_stub.jsonl
PROJDIR=$HOME/.vacant/trace/projects
PROMPT='Finish the task and report.'

start_stub () {
  pkill -f stub_model 2>/dev/null; sleep 1
  rm -f "$STUB_LOG"
  STUB_SCRIPT='[{"content":"All tests passed."}]' \
  STUB_LOG="$STUB_LOG" STUB_CAP=8 \
    setsid nohup python3 "$ROOT/stub_model.py" > /tmp/stub.log 2>&1 < /dev/null &
  sleep 2
}

make_cfg () {   # make_cfg <dir> <gate: on|off>
  d=$1; gate=$2
  rm -rf "$d"; mkdir -p "$d/plugin"
  if [ "$gate" = on ]; then
    # the SHIPPED plugin, exactly as `vacant install` left it
    cp /home/user1/.config/opencode/plugin/vacant.js "$d/plugin/vacant.js"
  else
    sed 's|^const NONINTERACTIVE = process.argv.includes("run");|const NONINTERACTIVE = false;|' \
      /home/user1/.config/opencode/plugin/vacant.js > "$d/plugin/vacant.js"
  fi
  grep -c 'NONINTERACTIVE = false' "$d/plugin/vacant.js" > /dev/null
  cat > "$d/opencode.json" <<'JSON'
{ "$schema": "https://opencode.ai/config.json",
  "model": "stubproxy/sb",
  "provider": { "stubproxy": { "npm": "@ai-sdk/openai-compatible", "name": "StubProxy",
      "options": { "baseURL": "http://127.0.0.1:3939/v1", "apiKey": "stub-key" },
      "models": { "sb": { "name": "Scripted" } } } },
  "permission": { "edit": "allow", "bash": "allow", "webfetch": "deny" },
  "autoupdate": false, "share": "disabled", "telemetry": false }
JSON
}

one_run () {   # one_run <tag> <gate>
  tag=$1; gate=$2
  W=/tmp/w2ab_$tag
  rm -rf "$W"; mkdir -p "$W"; ( cd "$W" && git init -q . && printf 'x' > data.csv )
  make_cfg /tmp/w2abcfg_$tag "$gate"
  before=$(ls "$PROJDIR" 2>/dev/null | wc -l)
  ( cd "$W" && OPENCODE_CONFIG_DIR=/tmp/w2abcfg_$tag timeout 200 "$OC" run \
      --format json --dir "$W" -m stubproxy/sb "$PROMPT" \
      > "$W/out.jsonl" 2> "$W/err.log" )
  rc=$?
  echo "--- $tag (gate=$gate) opencode_rc=$rc stub_user_prompts=$(python3 - "$STUB_LOG" <<'PY'
import json,sys
n=0
for l in open(sys.argv[1], errors="replace"):
    try: o=json.loads(l)
    except Exception: continue
    if (o.get("roles") or [])[-1:] == ["user"]: n+=1
print(n)
PY
)"
  python3 - "$PROJDIR" "$before" "$W" <<'PY'
import collections, json, pathlib, sys
proj, before, ws = pathlib.Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
best = None
for d in sorted(proj.iterdir()):
    try: n = int(d.name[:8], 16)
    except Exception: continue
    st = d / "state.json"
    if not st.exists() or n < before: continue
    try: j = json.loads(st.read_text())
    except Exception: continue
    if j.get("workspace") == ws and (best is None or n > best[0]): best = (n, d)
if best is None:
    print("    (no trace project recorded for this workspace)"); raise SystemExit
d = best[1]
c = collections.Counter()
for l in (d / "perf.jsonl").read_text(errors="replace").splitlines():
    try: c[json.loads(l).get("event")] += 1
    except Exception: pass
print("    perf:", dict(c))
kinds = collections.Counter()
for l in (d / "chain.ndjson").read_text(errors="replace").splitlines():
    try: kinds[json.loads(l).get("type")] += 1
    except Exception: pass
print("    chain:", dict(kinds))
for n in ("delivery.md", "delivery.json"):
    f = d / n
    if f.exists(): print(f"    {n}: {f.read_text(errors='replace')[:220].strip()}")
PY
}

start_stub
one_run gateon on
one_run gateoff off
echo
echo "=== the prompt texts the stub served, gate-off run only ==="
python3 - "$STUB_LOG" <<'PY'
import json, sys
for l in open(sys.argv[1], errors="replace"):
    try: o = json.loads(l)
    except Exception: continue
    if (o.get("roles") or [])[-1:] == ["user"]:
        print("  n=%d %r" % (o["n"], o["last_text"][:200]))
PY
pkill -f stub_model 2>/dev/null
