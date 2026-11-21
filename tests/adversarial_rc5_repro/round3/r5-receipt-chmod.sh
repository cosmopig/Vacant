#!/bin/bash
# r5 — class (c): the agent makes $VACANT_HOME read-only during its attempt ->
# _record_receipt fails (fail-open) -> NO signed receipt for a run that modified the
# project, exit 0, and the message never mentions the receipt. `audit list --strict`
# exits 0 too (strict only fails on bad signatures; missing = unsigned, allowed).
set -u
BASE="${BASE:-/tmp/claude-1000/rc5c-repro}"
ROOT="$BASE"
mkdir -p "$ROOT/venv/bin"
cat > "$ROOT/venv/bin/vacant" <<'WRAP'
#!/bin/sh
exec env -u VIRTUAL_ENV PYTHONPATH=/home/user1/dev/wt/rc5 /home/user1/dev/Vacant/.venv/bin/python -m vacant_network.cli "$@"
WRAP
chmod +x "$ROOT/venv/bin/vacant"
VAC="$ROOT/venv/bin/vacant"
B="$ROOT/projects/r5-receipt"
P="$B/proj"
export VACANT_HOME="$B/vh"
export VACANT_WORK="$B/vw"
rm -rf "$B"; mkdir -p "$P"

cat > "$P/impl.py" <<'EOF'
def answer():
    return 41
EOF
cat > "$P/test_impl.py" <<'EOF'
import unittest, impl
class T(unittest.TestCase):
    def test_a(self):
        self.assertEqual(impl.answer(), 42)
EOF
cat > "$B/agent.py" <<'EOF'
import pathlib, os
p = pathlib.Path('impl.py')
p.write_text(p.read_text().replace('41', '42'))
# suppress the signed receipt: make the whole state dir unwritable
vh = os.environ.get('VACANT_HOME', os.path.expanduser('~/.vacant'))
os.makedirs(vh, exist_ok=True)
for dp, dns, fns in os.walk(vh):
    for n in dns + fns:
        try:
            os.chmod(os.path.join(dp, n), 0o500)
        except OSError:
            pass
    try:
        os.chmod(dp, 0o500)
    except OSError:
        pass
print('chmodded', vh)
EOF

cd "$P"
"$VAC" do --cmd "python3 $B/agent.py" --prompt 'fix impl'
echo "===== EXIT=$?"
echo "----- impl.py delivered:"
grep answer impl.py
echo "----- receipt field:"
python3 - <<'PYEOF'
import json, glob, os
rs = sorted(glob.glob(os.environ['VACANT_WORK'] + '/restart-*/result.json'))
res = json.load(open(rs[-1]))
print('receipt:', res.get('receipt'))
print('changed:', res.get('changed'))
PYEOF
chmod -R u+w "$VACANT_HOME" 2>/dev/null
echo "----- audit list --strict:"
"$VAC" audit list --strict; echo "STRICT_EXIT=$?"
