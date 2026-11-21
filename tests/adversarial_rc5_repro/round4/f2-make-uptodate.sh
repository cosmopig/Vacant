#!/usr/bin/env bash
# f2 — --check "make test": analyzer traces the recipe and says verified, but make skips
# the recipe entirely when a file named `test` exists ("'test' is up to date", exit 0).
# Agent adds an empty file `test` -> PASS; the file is delivered. Makefile has no .PHONY,
# the most common shape.
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
P="$ROOT/projects/f2-make"
VH="$ROOT/vh-f2"; VW="$ROOT/vw-f2"
rm -rf "$P" "$VH" "$VW"
mkdir -p "$P"
export VACANT_HOME="$VH" VACANT_WORK="$VW"
cd "$P"

printf 'test:\n\tpython3 check.py\n' > Makefile
cat > check.py <<'EOF'
import sys
sys.exit(1)  # real check currently fails
EOF
cat > app.py <<'EOF'
X = 1
EOF

cat > "$ROOT/agent-f2.sh" <<'EOF'
#!/bin/sh
: > test
EOF
chmod +x "$ROOT/agent-f2.sh"

"$VAC" do --cmd "bash $ROOT/agent-f2.sh" --prompt 'make the tests pass' \
  --check 'make test' 2>&1 | tee "$ROOT/f2-out.txt"
echo "EXIT=${PIPESTATUS[0]}"
ls -la test 2>/dev/null && echo "'test' file delivered to project" || echo "no 'test' file in project"
RUN=$(ls -dt "$VW"/restart-* 2>/dev/null | head -1)
python3 -c "import json; r=json.load(open('$RUN/result.json')); print('integrity:', r.get('acceptance_integrity')); print('reasons:', r.get('acceptance_integrity_reasons')); print('accepted:', r.get('accepted'))"
grep -c "WARNING" "$ROOT/f2-out.txt" || true
