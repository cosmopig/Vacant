#!/bin/bash
# e8: NEW BUG — rc5 chmods the ORIGINAL project node_modules read-only during
# each attempt and during each acceptance run. If vacant is killed (SIGTERM /
# SIGKILL / OOM / crash), the restore in `finally` never runs and the project's
# node_modules is left read-only permanently.
set -u
BASE=/tmp/claude-1000/devin-rc5
P=$BASE/projects/e8
rm -rf "$P"
mkdir -p "$P/proj/node_modules/dep" "$P/vh" "$P/vw"
cd "$P/proj"

cat > package.json <<'EOF'
{"name":"t","scripts":{"test":"node verify.test.js"}}
EOF
cat > verify.test.js <<'EOF'
process.exit(0);
EOF
echo 'x' > node_modules/dep/index.js
chmod 644 node_modules/dep/index.js
chmod 755 node_modules node_modules/dep

cat > "$P/agent.sh" <<'EOF'
#!/bin/bash
sleep 60
EOF
chmod +x "$P/agent.sh"

echo "--- modes before ---"
stat -c '%a %n' node_modules node_modules/dep node_modules/dep/index.js

export VACANT_HOME="$P/vh" VACANT_WORK="$P/vw"
"$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt x &
VPID=$!
sleep 6   # let it finish baseline + start attempt 1 (agent sleeps 60s)
kill -TERM $VPID 2>/dev/null
sleep 1
kill -9 $VPID 2>/dev/null
wait $VPID 2>/dev/null
echo "vacant killed, EXIT=$?"

echo "--- modes after killing vacant mid-attempt ---"
stat -c '%a %n' node_modules node_modules/dep node_modules/dep/index.js
if [ ! -w node_modules/dep/index.js ]; then
  echo ">>> EVIDENCE: node_modules left read-only after vacant was killed"
fi
# cleanup so other tests are unaffected
chmod -R u+w "$P/proj/node_modules" 2>/dev/null
