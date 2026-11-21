#!/bin/bash
# FINDING d2-subdir-misleading (class D: misleading message)
# `vacant do` treats the CURRENT directory as the project. Run from a
# subdirectory of a project whose root contains failing tests, vacant reports
# "no tests or supported test runner detected" and delivers unchecked changes —
# it never looks upward, so the "no tests" claim is false for the real project.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VACANT="$HERE/venv/bin/vacant"
ROOT="$(mktemp -d "$HERE/projects/d2.XXXXXX")"
export VACANT_HOME="$ROOT/vhome" VACANT_WORK="$ROOT/vwork"
cd "$ROOT"

mkdir -p proj/pkg
cat > proj/test_root.py <<'EOF'
import unittest
class T(unittest.TestCase):
    def test_root(self):
        self.assertEqual(1, 2)   # failing test at the real project root
EOF
cat > agent.sh <<'EOF'
#!/bin/bash
echo done > output.txt
EOF
chmod +x agent.sh

cd proj/pkg
timeout 120 "$VACANT" do --cmd "$ROOT/agent.sh {prompt}" --prompt "make output" --attempts 1
echo "EXIT=$?"
echo "=== subdir now contains (delivered unchecked):"; ls
