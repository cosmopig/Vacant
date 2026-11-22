#!/bin/bash
# e12: cost of the B3 fix — full sha256 manifest of node_modules at start, after
# each attempt, before/after each acceptance, and at end; plus a full copy for
# each attempt. Time it with a realistic-size node_modules.
set -u
BASE=/tmp/claude-1000/devin-rc5
P=$BASE/projects/e12
rm -rf "$P"
mkdir -p "$P/proj" "$P/vh" "$P/vw"
cd "$P/proj"

cat > package.json <<'EOF'
{"name":"t","scripts":{"test":"node verify.test.js"}}
EOF
cat > verify.test.js <<'EOF'
process.exit(0);
EOF
# ~3000 files, ~30MB node_modules (small by real-world standards)
python3 - <<'PY'
import os, random
os.makedirs('node_modules/pkg', exist_ok=True)
for i in range(150):
    d = f'node_modules/pkg/d{i}'
    os.makedirs(d, exist_ok=True)
    for j in range(20):
        with open(f'{d}/f{j}.js', 'w') as f:
            f.write('x' * 10000)
PY
du -sh node_modules; find node_modules -type f | wc -l

cat > "$P/agent.sh" <<'EOF'
#!/bin/bash
echo hi > out.txt
EOF
chmod +x "$P/agent.sh"

export VACANT_HOME="$P/vh" VACANT_WORK="$P/vw"
time "$BASE/venv/bin/vacant" do --cmd "bash $P/agent.sh" --prompt x
echo "EXIT=$?"
RD=$(ls -dt "$P/vw"/restart-* | head -1)
python3 - <<PYEOF
import json
d=json.load(open('$RD/result.json'))
print('node_modules_copy_s:', d.get('node_modules_copy_s'))
print('node_modules_hash_s:', d.get('node_modules_hash_s'))
print('total_wall_s:', d.get('total_wall_s'))
PYEOF
