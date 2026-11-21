#!/bin/bash
# e3: B2 marker only covers the *agent*. Code that runs during ACCEPTANCE
# (project's own tests importing candidate code) can detach a process with no
# marker at all — VACANT_RUN_ID is never in the check's environment.
set -u
BASE=/tmp/claude-1000/devin-rc5
P=$BASE/projects/e3
rm -rf "$P"
mkdir -p "$P/proj" "$P/vh" "$P/vw"

cd "$P/proj"
cat > impl.py <<'EOF'
def ok():
    return False
EOF
cat > test_impl.py <<'EOF'
import unittest, impl
class T(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(impl.ok())
EOF
# agent: make impl.ok() True AND arm a delayed detached writer at import time.
# During acceptance the test runner imports impl -> the setsid child spawns.
# The acceptance subprocess env has no VACANT_RUN_ID at all.
cat > "$P/agent.sh" <<EOF
#!/bin/bash
cat > impl.py <<'PYEOF'
import subprocess
def ok():
    return True
subprocess.Popen(["setsid", "bash", "-c",
    "sleep 8; echo CHECKSIDE > $P/proj/late_check.txt"],
    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
PYEOF
EOF
chmod +x "$P/agent.sh"

export VACANT_HOME="$P/vh" VACANT_WORK="$P/vw"
"$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt x
echo "EXIT=$?"
RD=$(ls -dt "$P/vw"/restart-* | head -1)
python3 -c "import json;d=json.load(open('$RD/result.json'));print('detached_processes:',d.get('detached_processes'));print('outside_changes:',d.get('outside_changes'))"
echo "--- waiting for the acceptance-spawned writer ---"
sleep 9
ls -la "$P/proj"/late_* 2>/dev/null && echo ">>> EVIDENCE: code detached during ACCEPTANCE (not the agent) wrote post-delivery; detached_processes list cannot see it"
