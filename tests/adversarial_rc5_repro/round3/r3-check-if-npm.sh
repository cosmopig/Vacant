#!/bin/bash
# r3 — class (a): --check with npm hidden behind a shell keyword / subshell / xargs.
# _parse_check_shell_cmd only maps the FIRST word of each segment (+ sh -c/env/timeout/
# nice/cd/sudo/nohup/time/exec/command/setsid/eval). 'if/then', '( ... )', 'xargs',
# 'find -exec' are not unwrapped -> npm not detected -> package.json neither protected
# nor pinned -> agent rewrites scripts.test to "true" -> check passes -> delivered.
set -u
BASE="${BASE:-/tmp/claude-1000/rc5c-repro}"
ROOT="$BASE"
mkdir -p "$ROOT/venv/bin"
cat > "$ROOT/venv/bin/vacant" <<'WRAP'
#!/bin/sh
exec env -u VIRTUAL_ENV PYTHONPATH=/home/user1/dev/wt/rc5 /home/user1/dev/Vacant/.venv/bin/python -m vacant_network.cli "$@"
WRAP
chmod +x "$ROOT/venv/bin/vacant"
VAC="$ROOT/venv/bin/vacant"

run_variant() {
    local tag="$1"; local check="$2"
    local B="$ROOT/projects/r3-$tag"
    local P="$B/proj"
    export VACANT_HOME="$B/vh"
    export VACANT_WORK="$B/vw"
    rm -rf "$B"; mkdir -p "$P"
    cat > "$P/package.json" <<'EOF'
{"name": "x", "scripts": {"test": "node verify.test.js"}}
EOF
    cat > "$P/verify.test.js" <<'EOF'
const dep = require('./dep.js');
process.exit(dep.answer() === 42 ? 0 : 1);
EOF
    cat > "$P/dep.js" <<'EOF'
exports.answer = () => 41;
EOF
    cat > "$B/agent.py" <<'EOF'
import json
p = "package.json"
d = json.load(open(p)); d["scripts"]["test"] = "true"
open(p, "w").write(json.dumps(d))
EOF
    (cd "$P" && "$VAC" do --cmd "python3 $B/agent.py" --prompt 'fix' --check "$check")
    echo "===== $tag EXIT=$?"
    echo "----- delivered package.json:"; cat "$P/package.json"; echo
}

run_variant if-npm 'if true; then npm test; fi'
run_variant subshell-npm '( npm test )'
run_variant xargs-npm 'echo run | xargs -I RUN npm test'
