#!/bin/bash
# e16: D3 conflict — user edits a file mid-run that the delivered attempt also
# modified. Expected: user's version kept, conflict reported.
set -u
BASE=/tmp/claude-1000/devin-rc5
P=$BASE/projects/e16
rm -rf "$P"; mkdir -p "$P/proj" "$P/vh" "$P/vw"; cd "$P/proj"
cat > calc.py <<'EOF'
def add(a, b): return a - b
EOF
cat > test_calc.py <<'EOF'
import unittest, calc
class T(unittest.TestCase):
    def test_add(self): self.assertEqual(calc.add(2, 3), 5)
EOF
cat > shared.py <<'EOF'
X = 1
EOF
cat > "$P/agent.sh" <<'EOF'
#!/bin/bash
cat > calc.py <<'PY'
def add(a, b): return a + b
PY
cat > shared.py <<'PY'
X = 2
PY
sleep 3
EOF
chmod +x "$P/agent.sh"
# concurrent user edit landing while the agent sleeps
( sleep 1.5; printf 'X = 99\n' > "$P/proj/shared.py" ) &
export VACANT_HOME="$P/vh" VACANT_WORK="$P/vw"
"$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt x
echo "EXIT=$?"
echo "--- shared.py after run (should still be the user's X=99) ---"
cat "$P/proj/shared.py"
RD=$(ls -dt "$P/vw"/restart-* | head -1)
python3 -c "import json;d=json.load(open('$RD/result.json'));print('conflicts:',d.get('conflicts'));print('changed:',d.get('changed'))"
