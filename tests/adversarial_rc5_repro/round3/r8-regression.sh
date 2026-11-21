#!/bin/bash
# r8 — regression sanity: ordinary use still works.
#  A: unittest fix -> accepted.  B: --check './verify.sh' (exec bit, round-2 R7).
#  C: no-tests project -> honest "nothing checked".  D: agent edits test -> rejected.
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

mk() { local B="$ROOT/projects/r8-$1"; local P="$B/proj"; rm -rf "$B"; mkdir -p "$P"; echo "$B|$P"; }

# A: legit fix
B=$(mk a); IFS='|' read -r BD PD <<< "$B"
export VACANT_HOME="$BD/vh"; export VACANT_WORK="$BD/vw"
printf 'def add(a,b):\n    return a-b\n' > "$PD/calc.py"
printf 'import unittest, calc\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertEqual(calc.add(2,3),5)\n' > "$PD/test_calc.py"
printf 'import pathlib\np=pathlib.Path("calc.py");p.write_text(p.read_text().replace("a-b","a+b"))\n' > "$BD/agent.py"
(cd "$PD" && "$VAC" do --cmd "python3 $BD/agent.py" --prompt 'fix' --attempts 1)
echo "===== A legit-fix EXIT=$? (want 0, calc fixed)"; grep return "$PD/calc.py"

# B: --check './verify.sh' exec-bit preserved
B=$(mk b); IFS='|' read -r BD PD <<< "$B"
export VACANT_HOME="$BD/vh"; export VACANT_WORK="$BD/vw"
printf '#!/bin/sh\nexit 1\n' > "$PD/verify.sh"; chmod 755 "$PD/verify.sh"
printf 'x\n' > "$PD/keep.txt"
printf 'import pathlib\npathlib.Path("out.txt").write_text("done")\n' > "$BD/agent.py"
(cd "$PD" && "$VAC" do --cmd "python3 $BD/agent.py" --prompt 'x' --check './verify.sh' --attempts 1)
echo "===== B exec-check EXIT=$? (want 40 reject, not 43 baseline_error)"

# C: no tests
B=$(mk c); IFS='|' read -r BD PD <<< "$B"
export VACANT_HOME="$BD/vh"; export VACANT_WORK="$BD/vw"
printf 'x\n' > "$PD/keep.txt"
printf 'import pathlib\npathlib.Path("out.txt").write_text("done")\n' > "$BD/agent.py"
(cd "$PD" && "$VAC" do --cmd "python3 $BD/agent.py" --prompt 'x')
echo "===== C no-tests EXIT=$? (want 0 + honest msg)"

# D: agent flips the test assert -> restored -> reject
B=$(mk d); IFS='|' read -r BD PD <<< "$B"
export VACANT_HOME="$BD/vh"; export VACANT_WORK="$BD/vw"
printf 'def add(a,b):\n    return a-b\n' > "$PD/calc.py"
printf 'import unittest, calc\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertEqual(calc.add(2,3),5)\n' > "$PD/test_calc.py"
printf 'import pathlib\np=pathlib.Path("test_calc.py");p.write_text(p.read_text().replace("5","-1"))\n' > "$BD/agent.py"
(cd "$PD" && "$VAC" do --cmd "python3 $BD/agent.py" --prompt 'fix' --attempts 1)
echo "===== D tamper EXIT=$? (want 40, test file unchanged)"; grep assertEqual "$PD/test_calc.py"
