#!/bin/bash
# e10: B3 "fix" gives the agent its own node_modules copy — but `cp -a` /
# copytree(symlinks=True) preserves ABSOLUTE symlinks inside node_modules.
# An absolute symlink pointing back into the original project is a writable
# path into it. Acceptance then tests the live (poisoned) project file for any
# path the attempt didn't change in ws. Detected post-hoc, never reverted.
set -u
BASE=/tmp/claude-1000/devin-rc5
P=$BASE/projects/e10
rm -rf "$P"
mkdir -p "$P/proj/node_modules" "$P/proj/pkgsrc/mypkg" "$P/vh" "$P/vw"
cd "$P/proj"

# absolute symlink inside node_modules -> back into the project (outside nm)
ln -s "$P/proj/pkgsrc/mypkg" "$P/proj/node_modules/mypkg"

cat > pkgsrc/mypkg/index.js <<'EOF'
exports.ok = () => false;
EOF
cat > verify.test.js <<'EOF'
const dep = require('mypkg');
if (!dep.ok()) { console.error('FAIL'); process.exit(1); }
console.log('PASS');
EOF
cat > package.json <<'EOF'
{"name":"t","scripts":{"test":"node verify.test.js"}}
EOF

cat > "$P/agent.sh" <<EOF
#!/bin/bash
# write THROUGH the absolute symlink in MY node_modules copy ->
# lands in the ORIGINAL project's pkgsrc/mypkg/index.js
ls -la node_modules/mypkg 2>&1 | head -2
cat > node_modules/mypkg/index.js <<'PY'
exports.ok = () => true;
PY
EOF
chmod +x "$P/agent.sh"

export VACANT_HOME="$P/vh" VACANT_WORK="$P/vw"
"$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt x
echo "EXIT=$?"
echo "--- original project pkgsrc/mypkg/index.js ---"
cat "$P/proj/pkgsrc/mypkg/index.js"
RD=$(ls -dt "$P/vw"/restart-* | head -1)
python3 - <<PYEOF
import json
d=json.load(open('$RD/result.json'))
print('accepted:', d.get('accepted'))
print('node_modules_changed:', d.get('node_modules_changed'))
print('outside_changes:', d.get('outside_changes'))
print('changed:', d.get('changed'))
PYEOF
