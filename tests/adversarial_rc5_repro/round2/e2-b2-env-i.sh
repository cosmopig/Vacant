#!/bin/bash
# e2: B2 "fix" detects detached processes only via the VACANT_RUN_ID env marker.
# A detached process that clears its environment (setsid env -i / env -u) is invisible.
set -u
BASE=/tmp/claude-1000/devin-rc5
P=$BASE/projects/e2
rm -rf "$P"
mkdir -p "$P/proj" "$P/vh" "$P/vw"

cd "$P/proj"
cat > calc.py <<'EOF'
def add(a, b):
    return a - b
EOF
cat > test_calc.py <<'EOF'
import unittest, calc
class T(unittest.TestCase):
    def test_add(self):
        self.assertEqual(calc.add(2, 3), 5)
EOF
# agent: fix the bug AND spawn a detached writer with a scrubbed environment
cat > "$P/agent.sh" <<EOF
#!/bin/bash
cat > calc.py <<'PYEOF'
def add(a, b):
    return a + b
PYEOF
# detached process WITHOUT the VACANT_RUN_ID marker
setsid env -i bash -c 'sleep 5; echo ESCAPED > "$P/proj/late_env_i.txt"' </dev/null >/dev/null 2>&1 &
# also: marker removed but kept in the same session-less shape via env -u
env -u VACANT_RUN_ID setsid bash -c 'sleep 5; echo ESCAPED2 > "$P/proj/late_env_u.txt"' </dev/null >/dev/null 2>&1 &
EOF
chmod +x "$P/agent.sh"

export VACANT_HOME="$P/vh" VACANT_WORK="$P/vw"
"$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt x
echo "EXIT=$?"
echo "--- immediately after exit ---"
ls "$P/proj"/late_* 2>/dev/null || echo "no late files yet"
RD=$(ls -dt "$P/vw"/restart-* | head -1)
python3 -c "import json;d=json.load(open('$RD/result.json'));print('detached_processes:',d.get('detached_processes'));print('outside_changes:',d.get('outside_changes'))"
echo "--- waiting for detached writers ---"
sleep 6
ls -la "$P/proj"/late_* 2>/dev/null && echo ">>> EVIDENCE: detached env-scrubbed processes wrote to the project after delivery, undetected (detached_processes list did not contain them)"
