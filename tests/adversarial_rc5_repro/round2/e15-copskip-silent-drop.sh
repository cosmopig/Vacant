#!/bin/bash
# e15: COPY_SKIP names are dropped at ANY depth. Files the agent creates under
# a dir literally named node_modules/.venv/.git/__pycache__/.pytest_cache are
# silently absent from the delivery — not in added, not in skipped, no message.
set -u
BASE=/tmp/claude-1000/devin-rc5
P=$BASE/projects/e15
rm -rf "$P"; mkdir -p "$P/proj" "$P/vh" "$P/vw"; cd "$P/proj"
cat > calc.py <<'EOF'
def add(a, b): return a - b
EOF
cat > test_calc.py <<'EOF'
import unittest, calc
class T(unittest.TestCase):
    def test_add(self): self.assertEqual(calc.add(2, 3), 5)
EOF
cat > "$P/agent.sh" <<'EOF'
#!/bin/bash
cat > calc.py <<'PY'
def add(a, b): return a + b
PY
mkdir -p vendor/node_modules sub/.venv pkg/__pycache__
echo 'module.exports=1' > vendor/node_modules/lib.js
echo 'x' > sub/.venv/f.txt
echo 'y' > pkg/__pycache__/g.txt
EOF
chmod +x "$P/agent.sh"
export VACANT_HOME="$P/vh" VACANT_WORK="$P/vw"
"$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt x
echo "EXIT=$?"
echo "--- delivered? ---"
ls "$P/proj/vendor/node_modules/" "$P/proj/sub/.venv/" "$P/proj/pkg/__pycache__/" 2>&1
RD=$(ls -dt "$P/vw"/restart-* | head -1)
python3 -c "import json;d=json.load(open('$RD/result.json'));print('changed:',d['changed'])"
