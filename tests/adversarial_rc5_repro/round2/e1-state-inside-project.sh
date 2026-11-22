#!/bin/bash
# e1: VACANT_HOME / VACANT_WORK inside the project — contract mode's _skip_dirs
# excludes them; restart mode's copytree does not.
#  a) VACANT_HOME inside project -> private signing keys copied into agent workspace.
#  b) VACANT_WORK inside project -> copytree recurses into the workspace itself -> crash.
set -u
BASE=/tmp/claude-1000/devin-rc5
P=$BASE/projects/e1
rm -rf "$P"
mkdir -p "$P/proj"

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
cat > "$P/agent.sh" <<'EOF'
#!/bin/bash
echo "agent cwd: $PWD"
echo "=== files in my workspace containing 'identity.key' ==="
find "$PWD" -name 'identity.key' 2>/dev/null
find "$PWD" -name '*.key' 2>/dev/null | head
cat > calc.py <<'PYEOF'
def add(a, b):
    return a + b
PYEOF
EOF
chmod +x "$P/agent.sh"

echo "############ (a) VACANT_HOME inside the project ############"
export VACANT_HOME="$P/proj/.vacant"      # CI-style: state dir inside the repo
export VACANT_WORK="$P/vw"                # work dir OUTSIDE project (sibling)
mkdir -p "$VACANT_WORK"
"$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt x
echo "EXIT=$?"
echo
echo "--- verifier private key inside agent's workspace? ---"
find "$VACANT_WORK" -name identity.key | head -5
find "$VACANT_WORK" -path '*/attempt_*/w/*' -name 'identity.key' | head -5 && \
  echo ">>> EVIDENCE: agent received a copy of the vacant signing keys"

echo
echo "############ (b) VACANT_WORK inside the project ############"
unset VACANT_HOME
export VACANT_HOME="$P/vh2"
export VACANT_WORK="$P/proj/vw2"          # work dir INSIDE project
mkdir -p "$VACANT_WORK"
"$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt x 2>&1 | tail -8
echo "EXIT=$?"
