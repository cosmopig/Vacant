#!/usr/bin/env bash
# Sanity: a legit fix -> sensible message (not part of the findings)
set -u
BASE="${BASE:-/tmp/claude-1000/rc5e-repro}"
ROOT="$BASE"
mkdir -p "$ROOT/venv/bin"
cat > "$ROOT/venv/bin/vacant" <<'WRAP'
#!/bin/sh
exec env -u VIRTUAL_ENV PYTHONPATH=/home/user1/dev/wt/rc5 /home/user1/dev/Vacant/.venv/bin/python -m vacant_network.cli "$@"
WRAP
chmod +x "$ROOT/venv/bin/vacant"
VAC="$ROOT/venv/bin/vacant"
R="$ROOT/projects/f0-legit"
rm -rf "$R"; mkdir -p "$R/proj" "$R/vhome" "$R/vwork"
cd "$R/proj"
export VACANT_HOME="$R/vhome" VACANT_WORK="$R/vwork"

printf 'def add(a, b):\n    return a - b\n' > calc.py
cat > test_calc.py <<'EOF'
import unittest
from calc import add
class T(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 2), 4)
EOF
cat > "$R/agent.sh" <<'EOF'
#!/usr/bin/env bash
printf 'def add(a, b):\n    return a + b\n' > calc.py
EOF
chmod +x "$R/agent.sh"

"$VAC" do --cmd "bash $R/agent.sh" --prompt "fix add" --attempts 1 --timeout 120 2>&1
echo "EXIT=$?"
echo "--- calc.py ---"; cat calc.py
