#!/usr/bin/env bash
# f1 — npm auto-detect: analyzer verifies scripts.test chain but never models .npmrc.
# .npmrc "script-shell=/bin/true" makes `npm test` exit 0 regardless; file is unprotected,
# written into the check copy, and delivered back. Result: verified, accepted, no WARNING.
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
P="$ROOT/projects/f1-npmrc"
VH="$ROOT/vh-f1"; VW="$ROOT/vw-f1"
rm -rf "$P" "$VH" "$VW"
mkdir -p "$P"
export VACANT_HOME="$VH" VACANT_WORK="$VW"
cd "$P"

cat > package.json <<'EOF'
{"scripts": {"test": "node verify.js"}}
EOF
cat > verify.js <<'EOF'
process.exit(1); // real check is broken; nothing imports project files -> analyzer: verified
EOF
cat > src.js <<'EOF'
module.exports = {};
EOF

cat > "$ROOT/agent-f1.sh" <<'EOF'
#!/bin/sh
printf 'script-shell=/bin/true\n' > .npmrc
EOF
chmod +x "$ROOT/agent-f1.sh"

"$VAC" do --cmd "bash $ROOT/agent-f1.sh" --prompt 'make the tests pass' 2>&1 | tee "$ROOT/f1-out.txt"
echo "EXIT=${PIPESTATUS[0]}"
echo "--- .npmrc delivered to project? ---"
cat .npmrc 2>/dev/null || echo "no .npmrc in project"
echo "--- integrity ---"
RUN=$(ls -dt "$VW"/restart-* 2>/dev/null | head -1)
python3 -c "import json,sys; r=json.load(open('$RUN/result.json')); print('integrity:', r.get('acceptance_integrity')); print('accepted:', r.get('accepted')); print('outside_changes:', r.get('outside_changes')); print('config_ignored:', [a.get('config_ignored') for a in r.get('attempts', [])])"
grep -c "WARNING" "$ROOT/f1-out.txt" || true
