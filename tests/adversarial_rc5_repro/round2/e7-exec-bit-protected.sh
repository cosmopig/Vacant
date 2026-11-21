#!/bin/bash
# e7: NEW BUG — protected files are restored before the check with mode 0600,
# losing the exec bit. A natural `--check './verify.sh'` therefore fails the
# baseline with exit 126 and vacant refuses to run (exit 43, fake "environment"
# error) even though everything is fine.
set -u
BASE=/tmp/claude-1000/devin-rc5
P=$BASE/projects/e7
rm -rf "$P"
mkdir -p "$P/proj" "$P/vh" "$P/vw"
cd "$P/proj"

cat > verify.sh <<'EOF'
#!/bin/bash
# the project's own acceptance script: must FAIL (dep is buggy)
grep -q 'ok = () => true' dep.js
EOF
chmod +x verify.sh
cat > dep.js <<'EOF'
exports.ok = () => false;
EOF

cat > "$P/agent.sh" <<'EOF'
#!/bin/bash
cat > dep.js <<'PY'
exports.ok = () => true;
PY
EOF
chmod +x "$P/agent.sh"

echo "############ --check './verify.sh' (directly executed script) ############"
export VACANT_HOME="$P/vh" VACANT_WORK="$P/vw"
"$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt x --check './verify.sh'
echo "EXIT=$?   (43 = 'environment' stop; verify.sh is executable in the project)"
ls -l "$P/proj/verify.sh"
echo
echo "############ control: --check 'bash verify.sh' ############"
P2=$BASE/projects/e7b
rm -rf "$P2"; mkdir -p "$P2/proj" "$P2/vh" "$P2/vw"
cd "$P2/proj"
cp "$P/proj/verify.sh" "$P/proj/dep.js" .
cp "$P/agent.sh" "$P2/agent.sh"
VACANT_HOME="$P2/vh" VACANT_WORK="$P2/vw" \
  "$BASE/venv/bin/vacant" do --cmd "bash $P2/agent.sh" --prompt x --check 'bash verify.sh'
echo "EXIT=$?"
