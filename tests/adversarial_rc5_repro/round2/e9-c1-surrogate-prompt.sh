#!/bin/bash
# e9: C1 follow-up — filenames are sanitized now, but `request_sha256 =
# sha256(prompt.encode("utf-8"))` still crashes on a surrogate-escaped prompt,
# inside the receipt's own try. Result: run delivers + exits 0 but the signed
# receipt is silently not written.
set -u
BASE=/tmp/claude-1000/devin-rc5
P=$BASE/projects/e9
rm -rf "$P"
mkdir -p "$P/proj" "$P/vh" "$P/vw"
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
cat > calc.py <<'PY'
def add(a, b):
    return a + b
PY
EOF
chmod +x "$P/agent.sh"

export VACANT_HOME="$P/vh" VACANT_WORK="$P/vw"
"$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt $'bad\xffprompt'
echo "EXIT=$?"
RD=$(ls -dt "$P/vw"/restart-* | head -1)
python3 - <<PYEOF
import json
d=json.load(open('$RD/result.json'))
print('receipt:', d.get('receipt'))
PYEOF
echo "--- audit list --strict ---"
VACANT_HOME="$P/vh" "$BASE/venv/bin/vacant" audit list --strict 2>&1 | tail -6
