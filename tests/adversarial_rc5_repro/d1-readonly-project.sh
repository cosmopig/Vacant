#!/bin/bash
# FINDING d1-readonly-project (class D: misleading success)
# On a read-only project directory, shutil.copytree propagates the 0555 mode to
# the agent's workspace copy, so the agent cannot write ANYTHING there
# (Permission denied, rc=1). vacant still runs acceptance on the unchanged copy,
# reports "acceptance passed ... delivered that attempt", and never tells the
# user the agent failed to do any work. The agent's error is only surfaced when
# acceptance does NOT pass, so a green result silently hides a dead agent.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VACANT="$HERE/venv/bin/vacant"
ROOT="$(mktemp -d "$HERE/projects/d1.XXXXXX")"
export VACANT_HOME="$ROOT/vhome" VACANT_WORK="$ROOT/vwork"
cd "$ROOT"

mkdir proj
cat > proj/test_ok.py <<'EOF'
import unittest
class T(unittest.TestCase):
    def test_one(self):
        self.assertEqual(1, 1)
EOF
cat > agent.sh <<'EOF'
#!/bin/bash
echo done > output.txt   # fails: workspace dir is read-only (inherited 0555)
EOF
chmod +x agent.sh
chmod 0555 proj

cd proj
timeout 120 "$VACANT" do --cmd "$ROOT/agent.sh {prompt}" --prompt "make output" --attempts 1
echo "EXIT=$?"
chmod 0755 .
echo "=== agent stderr in the run logs:"
find "$VACANT_WORK" -name agent_stderr.log -exec cat {} \;
echo "=== project:"; ls
