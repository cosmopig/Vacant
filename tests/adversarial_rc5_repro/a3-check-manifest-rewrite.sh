#!/bin/bash
# FINDING a3-check-manifest-rewrite (class A: accepted-but-wrong)
# With a user-supplied `--check 'npm test'`, package.json is NOT in the
# protected set (the manifest-pinning defense only applies to the auto-detected
# `npm` kind). The agent rewrites scripts.test to `true`; the check exits 0,
# the run is accepted, and the gutted package.json is written back.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VACANT="$HERE/venv/bin/vacant"
ROOT="$(mktemp -d "$HERE/projects/a3.XXXXXX")"
export VACANT_HOME="$ROOT/vhome" VACANT_WORK="$ROOT/vwork"
cd "$ROOT"

mkdir proj
cat > proj/package.json <<'EOF'
{"name":"demo","version":"1.0.0","scripts":{"test":"node verify.test.js"}}
EOF
cat > proj/verify.test.js <<'EOF'
process.exit(1); // real check currently fails
EOF

cat > agent.sh <<'EOF'
#!/bin/bash
cat > package.json <<'JSON'
{"name":"demo","version":"1.0.0","scripts":{"test":"true"}}
JSON
EOF
chmod +x agent.sh

cd proj
timeout 120 "$VACANT" do --cmd "$ROOT/agent.sh {prompt}" --prompt "make tests pass" \
    --check "npm test" --attempts 1
echo "EXIT=$?"
echo "=== delivered package.json:"; cat package.json; echo
echo "=== verify.test.js (untouched, still failing):"; cat verify.test.js
