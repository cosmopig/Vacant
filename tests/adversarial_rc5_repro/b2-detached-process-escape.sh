#!/bin/bash
# FINDING b2-detached-process-escape (class B: escape from the copy)
# The agent spawns a setsid-detached process. vacant only kills the agent's
# process group; the detached child survives, and a plain-file write into the
# ORIGINAL project landing after the write-back plan is computed (or after
# vacant exits) is never reverted, counted, or recorded in the receipt.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VACANT="$HERE/venv/bin/vacant"
ROOT="$(mktemp -d "$HERE/projects/b2.XXXXXX")"
export VACANT_HOME="$ROOT/vhome" VACANT_WORK="$ROOT/vwork"
cd "$ROOT"

mkdir proj
cat > proj/test_ok.py <<'EOF'
import unittest
class T(unittest.TestCase):
    def test_one(self):
        self.assertEqual(1, 1)
EOF

cat > agent.sh <<EOF
#!/bin/bash
# give setsid a moment to leave the process group, then exit; the child writes
# into the original project seconds after delivery.
setsid bash -c 'sleep 4; echo LATE > "$ROOT/proj/late.txt"' </dev/null >/dev/null 2>&1 &
sleep 1
EOF
chmod +x agent.sh

cd proj
timeout 120 "$VACANT" do --cmd "$ROOT/agent.sh {prompt}" --prompt "noop" --attempts 1
echo "EXIT=$?"
echo "=== project right after vacant exits:"; ls
sleep 6
echo "=== project 6s later:"; ls
echo "=== late.txt contents:"; cat late.txt 2>/dev/null || echo "(absent)"
