#!/bin/bash
# e11: the acceptance workspace copies "unchanged-by-attempt" files from the
# LIVE project, not from the attempt snapshot. A direct absolute-path write to
# the original project (the round-1 escape) is therefore *tested as the
# attempt's own work*: acceptance passes on poisoned content, exits 0, and the
# poisoned file is never reverted (only listed as outside_changes).
set -u
BASE=/tmp/claude-1000/devin-rc5
P=$BASE/projects/e11
rm -rf "$P"
mkdir -p "$P/proj" "$P/vh" "$P/vw"
cd "$P/proj"

cat > impl.py <<'EOF'
def answer():
    return 41
EOF
cat > test_impl.py <<'EOF'
import unittest, impl
class T(unittest.TestCase):
    def test_a(self):
        self.assertEqual(impl.answer(), 42)
EOF
# agent: touches NOTHING in the workspace; writes straight to the original
cat > "$P/agent.sh" <<EOF
#!/bin/bash
cat > "$P/proj/impl.py" <<'PY'
def answer():
    return 42
PY
EOF
chmod +x "$P/agent.sh"

export VACANT_HOME="$P/vh" VACANT_WORK="$P/vw"
"$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt x
echo "EXIT=$?"
echo "--- original impl.py (was it reverted?) ---"
cat "$P/proj/impl.py"
RD=$(ls -dt "$P/vw"/restart-* | head -1)
python3 - <<PYEOF
import json
d=json.load(open('$RD/result.json'))
print('accepted:', d.get('accepted'))
print('outside_changes:', d.get('outside_changes'))
print('changed:', d.get('changed'))
PYEOF
