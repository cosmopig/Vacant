#!/bin/bash
# FINDING d3-concurrent-delete (classes B + D: data loss)
# The delivery write-back diffs the live project against the delivered
# workspace snapshot: any regular file in the project that is not in the
# snapshot is DELETED. A file the USER creates in the project while an attempt
# is running (or that an agent writes directly, bypassing the workspace) is
# silently removed at delivery — vacant deletes files it did not create.
# The count is disclosed ("2 deleted") but the paths only appear in result.json.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VACANT="$HERE/venv/bin/vacant"
ROOT="$(mktemp -d "$HERE/projects/d3.XXXXXX")"
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
sleep 5   # window for a concurrent write into the project
EOF
chmod +x agent.sh

( sleep 2; echo USER_EDIT > "$ROOT/proj/userfile.txt" ) &

cd proj
timeout 120 "$VACANT" do --cmd "$ROOT/agent.sh {prompt}" --prompt "noop" --attempts 1
echo "EXIT=$?"
wait
echo "=== project after delivery (userfile.txt was DELETED):"; ls
echo "=== deleted paths in result.json:"
python3 -c "import json,glob;print(json.load(open(glob.glob('$VACANT_WORK'+'/*/result.json')[0]))['changed'])" 2>/dev/null || true
