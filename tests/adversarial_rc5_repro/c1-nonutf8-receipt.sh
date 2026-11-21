#!/bin/bash
# FINDING c1-nonutf8-receipt (classes C + D)
# If the agent creates a file whose name is not valid UTF-8, acceptance passes,
# the file is DELIVERED into the original project, and only then does vacant
# fail with `vacant: 'utf-8' codec can't encode ... surrogates not allowed`
# (exit 2). No signed restart_receipt is ever appended to the project's trace
# chain; `vacant audit list --strict` can only show the run as "unreadable /
# unsigned" — a receipt the agent can deterministically suppress.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VACANT="$HERE/venv/bin/vacant"
ROOT="$(mktemp -d "$HERE/projects/c1.XXXXXX")"
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
python3 -c 'open(b"bad-\xff-name.txt","wb").write(b"x")'
EOF
chmod +x agent.sh

cd proj
timeout 120 "$VACANT" do --cmd "$ROOT/agent.sh {prompt}" --prompt "add a file" --attempts 1
echo "EXIT=$?"
echo "=== project after (file WAS delivered):"; ls -la | cat -v
echo "=== audit list --strict for this run:"
timeout 60 "$VACANT" audit list --strict
echo "=== receipt chain present?"; find "$VACANT_HOME" -name 'chain.ndjson' -o -name 'restart_receipt*' | head || true
