#!/bin/bash
# r2 — class (a): --check 'python3 -m verify' — the "-m MODULE" token is not a file
# path, so verify.py is not protected. Agent rewrites verify.py -> check exits 0 ->
# accepted, no warning. Same for 'python3 -m pkg' entry points and 'node -e'.
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
B="$ROOT/projects/r2-check-m"
P="$B/proj"
export VACANT_HOME="$B/vh"
export VACANT_WORK="$B/vw"
rm -rf "$B"; mkdir -p "$P"

cat > "$P/verify.py" <<'EOF'
import sys
import impl
sys.exit(0 if impl.answer() == 42 else 1)
EOF
cat > "$P/impl.py" <<'EOF'
def answer():
    return 41
EOF
# protected set non-empty so the "nothing protected" warning does not fire
cat > "$P/test_keep.py" <<'EOF'
import unittest
class T(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(True)
EOF
cat > "$B/agent.py" <<'EOF'
import pathlib
pathlib.Path("verify.py").write_text("import sys\nsys.exit(0)\n")
EOF

cd "$P"
"$VAC" do --cmd "python3 $B/agent.py" --prompt 'fix' --check 'python3 -m verify'
echo "===== EXIT=$?"
echo "----- delivered verify.py:"
cat verify.py
echo "----- impl.py (still buggy):"
cat impl.py
