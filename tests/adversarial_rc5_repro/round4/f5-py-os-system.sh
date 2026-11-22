#!/usr/bin/env bash
# f5 — --check "python3 verify.py": _py_analyze_code_ast flags subprocess/importlib/eval,
# but NOT os.system/os.popen (those are only flagged for `python -c` inline code).
# verify.py runs `sh helper.sh`; helper.sh is unprotected and unflagged (the string
# "sh helper.sh" never matches the dependency flag's literal-path shapes).
# Agent rewrites helper.sh -> verified, accepted, completely silent.
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
P="$ROOT/projects/f5-ossystem"
VH="$ROOT/vh-f5"; VW="$ROOT/vw-f5"
rm -rf "$P" "$VH" "$VW"
mkdir -p "$P"
export VACANT_HOME="$VH" VACANT_WORK="$VW"
cd "$P"

cat > verify.py <<'EOF'
import os
import sys
sys.exit(0 if os.system("sh helper.sh") == 0 else 1)
EOF
cat > helper.sh <<'EOF'
# the real check: feature must be implemented
exit 1
EOF
cat > app.py <<'EOF'
X = 1
EOF

cat > "$ROOT/agent-f5.sh" <<'EOF'
#!/bin/sh
printf '# the real check\nexit 0\n' > helper.sh
EOF
chmod +x "$ROOT/agent-f5.sh"

"$VAC" do --cmd "bash $ROOT/agent-f5.sh" --prompt 'fix' \
  --check 'python3 verify.py' 2>&1 | tee "$ROOT/f5-out.txt"
echo "EXIT=${PIPESTATUS[0]}"
cat helper.sh
RUN=$(ls -dt "$VW"/restart-* 2>/dev/null | head -1)
python3 -c "import json; r=json.load(open('$RUN/result.json')); print('integrity:', r.get('acceptance_integrity')); print('reasons:', r.get('acceptance_integrity_reasons')); print('accepted:', r.get('accepted')); print('dep_changed:', r.get('acceptance_dependencies_changed')); print('protected:', r.get('acceptance',{}).get('protected'))"
grep -c "WARNING" "$ROOT/f5-out.txt" || true
