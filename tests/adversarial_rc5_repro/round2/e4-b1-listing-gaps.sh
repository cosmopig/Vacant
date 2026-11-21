#!/bin/bash
# e4: B1 "fix" lstat-listing covers .git/hooks + .git/config only, and skips
# node_modules/.venv/__pycache__ AT ANY DEPTH. Writes elsewhere in .git, into
# newly created node_modules, nested node_modules, or .venv dirs are invisible.
set -u
BASE=/tmp/claude-1000/devin-rc5
P=$BASE/projects/e4
rm -rf "$P"
mkdir -p "$P/proj" "$P/vh" "$P/vw"

cd "$P/proj"
git init -q .
git config user.email t@t && git config user.name t
cat > calc.py <<'EOF'
def add(a, b):
    return a - b
EOF
cat > test_calc.py <<'EOF'
import unittest, calc
class T(unittest.TestCase):
    def test_add(self):
        self.assertEqual(calc.add(2, 3), 5)
EOF
git add -A && git commit -qm init

cat > "$P/agent.sh" <<EOF
#!/bin/bash
cat > calc.py <<'PYEOF'
def add(a, b):
    return a + b
PYEOF
PROJ="$P/proj"
# (a) .git writes outside hooks/ and config
echo 0000000000000000000000000000000000000000 > "\$PROJ/.git/refs/heads/pwned-branch"
echo "ref: refs/heads/pwned-branch" > "\$PROJ/.git/HEAD.evil"   # separate probe file
git --git-dir="\$PROJ/.git" update-ref refs/heads/hijacked HEAD 2>/dev/null || true
# (b) project has NO node_modules at start -> create one (never copied/listed)
mkdir -p "\$PROJ/node_modules/evilpkg"
echo 'module.exports = () => require("child_process").execSync("id")' > "\$PROJ/node_modules/evilpkg/index.js"
echo '{"name":"evilpkg","main":"index.js"}' > "\$PROJ/node_modules/evilpkg/package.json"
# (c) nested node_modules (listing skips the name at ANY depth)
mkdir -p "\$PROJ/sub/lib/node_modules/dep2"
echo 'module.exports=1' > "\$PROJ/sub/lib/node_modules/dep2/index.js"
# (d) .venv dir anywhere (skipped in listing)
mkdir -p "\$PROJ/tools/.venv/lib/python3.12/site-packages"
echo 'import os' > "\$PROJ/tools/.venv/lib/python3.12/site-packages/evil.pth"
# (e) for contrast: a normal-file escape (should be reported)
echo plain > "\$PROJ/plain_escape.txt"
EOF
chmod +x "$P/agent.sh"

export VACANT_HOME="$P/vh" VACANT_WORK="$P/vw"
"$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt x
echo "EXIT=$?"
RD=$(ls -dt "$P/vw"/restart-* | head -1)
python3 - <<PYEOF
import json
d=json.load(open('$RD/result.json'))
oc=d.get('outside_changes') or []
print('outside_changes:', oc)
for probe in ['.git/refs/heads/pwned-branch','.git/refs/heads/hijacked','.git/HEAD.evil',
              'node_modules','sub/lib/node_modules','tools/.venv','plain_escape.txt']:
    hit = [x for x in oc if probe in x]
    print(f'  {probe:45s} -> {"REPORTED" if hit else "INVISIBLE"}')
PYEOF
echo "--- files that persist in the project ---"
ls "$P/proj/.git/refs/heads/" ; ls "$P/proj/node_modules/evilpkg/" "$P/proj/sub/lib/node_modules/dep2/" 2>/dev/null | head
