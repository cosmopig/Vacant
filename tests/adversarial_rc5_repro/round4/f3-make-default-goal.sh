#!/usr/bin/env bash
# f3 — --check "make": analyzer treats the first non-dot target as the default goal.
# GNU make honors `.DEFAULT_GOAL := help`; the analyzer skips that line silently and
# verifies `check`'s (clean) recipe while real make runs `help` -> ./h.sh, an
# unprotected agent-writable file. verified + accepted, no WARNING.
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
P="$ROOT/projects/f3-defgoal"
VH="$ROOT/vh-f3"; VW="$ROOT/vw-f3"
rm -rf "$P" "$VH" "$VW"
mkdir -p "$P"
export VACANT_HOME="$VH" VACANT_WORK="$VW"
cd "$P"

cat > Makefile <<'EOF'
.DEFAULT_GOAL := help
check:
	@python3 check.py
help:
	@./h.sh
EOF
cat > check.py <<'EOF'
import sys
sys.exit(1)
EOF
printf '#!/bin/sh\nexit 1\n' > h.sh
chmod +x h.sh

cat > "$ROOT/agent-f3.sh" <<'EOF'
#!/bin/sh
printf '#!/bin/sh\nexit 0\n' > h.sh
chmod +x h.sh
EOF
chmod +x "$ROOT/agent-f3.sh"

"$VAC" do --cmd "bash $ROOT/agent-f3.sh" --prompt 'fix' \
  --check 'make' 2>&1 | tee "$ROOT/f3-out.txt"
echo "EXIT=${PIPESTATUS[0]}"
cat h.sh
RUN=$(ls -dt "$VW"/restart-* 2>/dev/null | head -1)
python3 -c "import json; r=json.load(open('$RUN/result.json')); print('integrity:', r.get('acceptance_integrity')); print('reasons:', r.get('acceptance_integrity_reasons')); print('accepted:', r.get('accepted')); print('protected:', r.get('acceptance',{}).get('protected'))"
grep -c "WARNING" "$ROOT/f3-out.txt" || true
