#!/usr/bin/env bash
# f8 — ordinary-use sweep: which everyday check shapes now say "unverified" (noise)
# and does normal accept/reject still work.
set -u
BASE="${BASE:-/tmp/claude-1000/rc5d-repro}"
ROOT="$BASE"
mkdir -p "$ROOT/venv/bin"
cat > "$ROOT/venv/bin/vacant" <<'WRAP'
#!/bin/sh
exec env -u VIRTUAL_ENV PYTHONPATH=/home/user1/dev/wt/rc5 /home/user1/dev/Vacant/.venv/bin/python -m vacant_network.cli "$@"
WRAP
chmod +x "$ROOT/venv/bin/vacant"
VAC="$ROOT/venv/bin/vacant"
run_case() {
  name="$1"; shift
  P="$ROOT/projects/f8-$name"
  VH="$ROOT/vh-f8-$name"; VW="$ROOT/vw-f8-$name"
  rm -rf "$P" "$VH" "$VW"; mkdir -p "$P"
  ( cd "$P" && eval "$1" )
  echo "===== $name ====="
  ( cd "$P" && VACANT_HOME="$VH" VACANT_WORK="$VW" "$VAC" do --cmd "bash $ROOT/agent-f8.sh" --prompt 'fix' "$@" 2>&1 ) | tail -12
}

# agent: legit fix of app.py to X=2
cat > "$ROOT/agent-f8.sh" <<'EOF'
#!/bin/sh
[ -f app.py ] && printf 'X = 2\n' > app.py
[ -f app.js ] && printf 'module.exports = 2;\n' > app.js
exit 0
EOF
chmod +x "$ROOT/agent-f8.sh"

# A) bash verify.sh containing diff — the classic check shape
rm -rf "$ROOT/projects/f8-diffcheck" "$ROOT/vh-f8a" "$ROOT/vw-f8a"
mkdir -p "$ROOT/projects/f8-diffcheck"; cd "$ROOT/projects/f8-diffcheck"
cat > verify.sh <<'EOF'
#!/bin/sh
python3 -c "import app; print(app.X)" > got.txt
diff -q got.txt want.txt
EOF
printf 'X = 1\n' > app.py
printf '2\n' > want.txt
echo "===== bash verify.sh (diff) ====="
VACANT_HOME="$ROOT/vh-f8a" VACANT_WORK="$ROOT/vw-f8a" "$VAC" do --cmd "bash $ROOT/agent-f8.sh" \
  --prompt 'fix' --check 'bash verify.sh' 2>&1 | tail -10

# B) --check "bash -c 'make test'" — wrapping in bash -c
rm -rf "$ROOT/vh-f8b" "$ROOT/vw-f8b"
cd "$ROOT/projects/f8-diffcheck"
printf 'test:\n\t@exit 1\n' > Makefile
echo "===== bash -c 'make test' ====="
VACANT_HOME="$ROOT/vh-f8b" VACANT_WORK="$ROOT/vw-f8b" "$VAC" do --cmd "bash $ROOT/agent-f8.sh" \
  --prompt 'fix' --check "bash -c 'make test'" 2>&1 | tail -8

# C) plain unittest auto-detect, legit fix -> should accept (traced)
P="$ROOT/projects/f8-unit"; rm -rf "$P" "$ROOT/vh-f8c" "$ROOT/vw-f8c"; mkdir -p "$P"; cd "$P"
cat > test_app.py <<'EOF'
import unittest
import app
class T(unittest.TestCase):
    def test_x(self): self.assertEqual(app.X, 2)
EOF
printf 'X = 1\n' > app.py
echo "===== auto unittest legit fix ====="
VACANT_HOME="$ROOT/vh-f8c" VACANT_WORK="$ROOT/vw-f8c" "$VAC" do --cmd "bash $ROOT/agent-f8.sh" \
  --prompt 'fix' 2>&1 | tail -8

# D) --check python3 check.py where check.py imports app (normal!) -> untraced
P="$ROOT/projects/f8-pycheck"; rm -rf "$P" "$ROOT/vh-f8d" "$ROOT/vw-f8d"; mkdir -p "$P"; cd "$P"
cat > check.py <<'EOF'
import sys
import app
sys.exit(0 if app.X == 2 else 1)
EOF
printf 'X = 1\n' > app.py
echo "===== python3 check.py (imports app) ====="
VACANT_HOME="$ROOT/vh-f8d" VACANT_WORK="$ROOT/vw-f8d" "$VAC" do --cmd "bash $ROOT/agent-f8.sh" \
  --prompt 'fix' --check 'python3 check.py' 2>&1 | tail -9

# E) no tests at all -> honest "nothing checked"
P="$ROOT/projects/f8-none"; rm -rf "$P" "$ROOT/vh-f8e" "$ROOT/vw-f8e"; mkdir -p "$P"; cd "$P"
printf 'hello\n' > README.txt
echo "===== no tests ====="
VACANT_HOME="$ROOT/vh-f8e" VACANT_WORK="$ROOT/vw-f8e" "$VAC" do --cmd "bash $ROOT/agent-f8.sh" \
  --prompt 'fix' 2>&1 | tail -6
