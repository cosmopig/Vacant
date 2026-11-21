#!/bin/bash
# c1/confirm: verify claimed-fixed behaviors quickly.
# (a) non-UTF-8 filename -> receipt IS written now
# (b) .git/hooks plant -> reported in outside_changes + warning
# (c) concurrent user file during run -> kept + 'appeared during run'
# (d) read-only project root -> exit 43 with clear message
# (e) subdir run -> parent_tests_dir hint
set -u
BASE=/tmp/claude-1000/devin-rc5

echo "############ (a) non-UTF-8 filename -> receipt ############"
P=$BASE/projects/c1a
rm -rf "$P"; mkdir -p "$P/proj" "$P/vh" "$P/vw"; cd "$P/proj"
cat > calc.py <<'EOF'
def add(a, b): return a - b
EOF
cat > test_calc.py <<'EOF'
import unittest, calc
class T(unittest.TestCase):
    def test_add(self): self.assertEqual(calc.add(2, 3), 5)
EOF
cat > "$P/agent.sh" <<'EOF'
#!/bin/bash
cat > calc.py <<'PY'
def add(a, b): return a + b
PY
python3 -c "open('bad-\udcff-name.txt','w').write('x')"
EOF
chmod +x "$P/agent.sh"
VACANT_HOME="$P/vh" VACANT_WORK="$P/vw" "$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt x
echo "EXIT=$?"
RD=$(ls -dt "$P/vw"/restart-* | head -1)
python3 -c "import json;d=json.load(open('$RD/result.json'));print('receipt:',d.get('receipt'));print('non_utf8:',d.get('non_utf8_paths'))"
VACANT_HOME="$P/vh" "$BASE/venv/bin/vacant" audit list --strict 2>&1 | tail -3

echo; echo "############ (b) .git/hooks plant -> outside_changes ############"
P=$BASE/projects/c1b
rm -rf "$P"; mkdir -p "$P/proj" "$P/vh" "$P/vw"; cd "$P/proj"
git init -q .; git config user.email t@t; git config user.name t
cat > calc.py <<'EOF'
def add(a, b): return a - b
EOF
cat > test_calc.py <<'EOF'
import unittest, calc
class T(unittest.TestCase):
    def test_add(self): self.assertEqual(calc.add(2, 3), 5)
EOF
git add -A; git commit -qm init
cat > "$P/agent.sh" <<EOF
#!/bin/bash
cat > calc.py <<'PY'
def add(a, b): return a + b
PY
mkdir -p "$P/proj/.git/hooks"
printf '#!/bin/sh\necho PWNED >&2\n' > "$P/proj/.git/hooks/post-commit"
chmod +x "$P/proj/.git/hooks/post-commit"
EOF
chmod +x "$P/agent.sh"
VACANT_HOME="$P/vh" VACANT_WORK="$P/vw" "$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt x
echo "EXIT=$?"

echo; echo "############ (c) concurrent user file -> kept ############"
P=$BASE/projects/c1c
rm -rf "$P"; mkdir -p "$P/proj" "$P/vh" "$P/vw"; cd "$P/proj"
cat > calc.py <<'EOF'
def add(a, b): return a - b
EOF
cat > test_calc.py <<'EOF'
import unittest, calc
class T(unittest.TestCase):
    def test_add(self): self.assertEqual(calc.add(2, 3), 5)
EOF
cat > "$P/agent.sh" <<EOF
#!/bin/bash
( sleep 0.5; echo userwork > "$P/proj/userfile.txt" ) &
sleep 0.2
cat > calc.py <<'PY'
def add(a, b): return a + b
PY
sleep 1
EOF
chmod +x "$P/agent.sh"
VACANT_HOME="$P/vh" VACANT_WORK="$P/vw" "$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt x
echo "EXIT=$?"; ls "$P/proj/userfile.txt" && cat "$P/proj/userfile.txt"

echo; echo "############ (d) read-only project root -> 43 ############"
P=$BASE/projects/c1d
rm -rf "$P"; mkdir -p "$P/proj" "$P/vh" "$P/vw"; cd "$P/proj"
cat > calc.py <<'EOF'
def add(a, b): return a - b
EOF
cat > test_calc.py <<'EOF'
import unittest, calc
class T(unittest.TestCase):
    def test_add(self): self.assertEqual(calc.add(2, 3), 5)
EOF
cat > "$P/agent.sh" <<'EOF'
#!/bin/bash
echo x > out.txt
EOF
chmod +x "$P/agent.sh"
chmod 0555 "$P/proj"
VACANT_HOME="$P/vh" VACANT_WORK="$P/vw" "$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt x
echo "EXIT=$?"
chmod 0755 "$P/proj"

echo; echo "############ (e) run from subdir -> hint ############"
P=$BASE/projects/c1e
rm -rf "$P"; mkdir -p "$P/proj/pkg" "$P/vh" "$P/vw"; cd "$P/proj"
cat > test_root.py <<'EOF'
import unittest
class T(unittest.TestCase):
    def test_x(self): self.assertEqual(1, 2)
EOF
cat > "$P/agent.sh" <<'EOF'
#!/bin/bash
echo x > out.txt
EOF
chmod +x "$P/agent.sh"
cd "$P/proj/pkg"
VACANT_HOME="$P/vh" VACANT_WORK="$P/vw" "$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt x
echo "EXIT=$?"
