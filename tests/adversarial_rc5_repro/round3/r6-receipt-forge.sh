#!/bin/bash
# r6 — class (c): the verifier signing key lives at $VACANT_HOME/intake/keys/verifier/
# identity.key, readable by the agent (runs as the user). The agent can append a forged
# `restart_receipt` that `vacant audit list --strict` verifies as genuine — e.g. a run
# that was REJECTED is followed by a forged "accepted" receipt.
set -u
BASE="${BASE:-/tmp/claude-1000/rc5c-repro}"
ROOT="$BASE"
mkdir -p "$ROOT/venv/bin"
cat > "$ROOT/venv/bin/vacant" <<'WRAP'
#!/bin/sh
exec env -u VIRTUAL_ENV PYTHONPATH=/home/user1/dev/wt/rc5 /home/user1/dev/Vacant/.venv/bin/python -m vacant_network.cli "$@"
WRAP
chmod +x "$ROOT/venv/bin/vacant"
cat > "$ROOT/venv/bin/python3" <<'WRAP'
#!/bin/sh
exec env -u VIRTUAL_ENV PYTHONPATH=/home/user1/dev/wt/rc5 /home/user1/dev/Vacant/.venv/bin/python "$@"
WRAP
chmod +x "$ROOT/venv/bin/python3"
VAC="$ROOT/venv/bin/vacant"
VPY="$ROOT/venv/bin/python3"
[ -x "$VPY" ] || VPY="$ROOT/venv/bin/python"
P="$ROOT/projects/r6-forge/proj"
export VACANT_HOME="$ROOT/projects/r6-forge/vh"
export VACANT_WORK="$ROOT/projects/r6-forge/vw"
rm -rf "$ROOT/projects/r6-forge"; mkdir -p "$P"

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

cd "$P"
echo "===== run 1: agent does nothing useful -> rejected (exit 40 expected)"
"$VAC" do --cmd 'true' --prompt 'fix impl' --attempts 1
echo "REAL_EXIT=$?"
ls "$VACANT_HOME/intake/keys/verifier/identity.key" && echo "(key readable by agent)"

echo "===== agent forges an 'accepted' restart_receipt with the real verifier key"
"$VPY" - <<PYEOF
import json, time
from vacant_network.trace.recorder import Recorder
payload = {
    "receipt_schema": "vacant-restart-receipt/1",
    "run_id": "restart-FORGED",
    "request_sha256": "0"*64,
    "agent": "generic",
    "argv": ["true"],
    "env": {},
    "project_path_sha256": "0"*64,
    "acceptance": {"kind": "python_unittest", "command": "x", "interpreter": "x",
                   "protected": ["test_impl.py"], "reason": None},
    "baseline": {"accept": False, "status": "ok"},
    "max_attempts": 1,
    "attempts": [{"attempt": 1, "wall_s": 0.1, "rc": 0, "timed_out": False,
                  "accept": True, "passed": 1, "run": 1, "status": "ok",
                  "tests_tampered": [], "snapshot_tree_sha256": "0"*64}],
    "delivered_attempt": 1,
    "accepted": True,
    "written_back": [{"path": "impl.py", "op": "modified", "sha256": "0"*64}],
    "deleted": [], "skipped": [], "appeared_during_run": [], "conflicts": [],
    "write_back_conflicts": [], "outside_changes": [], "protected_outside_changes": [],
    "detached_processes": [], "acceptance_dependencies_changed": [], "not_delivered": [],
    "agent_wall_s": 0.1, "total_wall_s": 0.5,
}
ref = Recorder("$P").append("restart_receipt", payload)
print("forged entry appended:", ref)
PYEOF

echo "===== audit list --strict (does the forged receipt verify?)"
"$VAC" audit list --strict; echo "STRICT_EXIT=$?"
