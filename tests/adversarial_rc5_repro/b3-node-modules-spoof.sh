#!/bin/bash
# FINDING b3-node-modules-spoof (classes A + B)
# vacant protects the project's node_modules during an attempt by (a) chmod-ing
# it read-only and (b) comparing a manifest of (type,size,mtime_ns,inode,link)
# afterwards. Both are defeated: the agent owns the files, so it chmods them
# writable again, overwrites a dependency file with the SAME byte length, and
# restores st_mtime_ns -> the manifest is identical, the modification is never
# detected, and the acceptance run itself loads the poisoned module
# (work/node_modules is a symlink to the ORIGINAL node_modules for the check).
# Result: accepted-but-wrong AND the original project's node_modules stays
# permanently poisoned.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VACANT="$HERE/venv/bin/vacant"
ROOT="$(mktemp -d "$HERE/projects/b3.XXXXXX")"
export VACANT_HOME="$ROOT/vhome" VACANT_WORK="$ROOT/vwork"
cd "$ROOT"

mkdir -p proj/node_modules/depcheck
cat > proj/package.json <<'EOF'
{"name":"demo","version":"1.0.0","scripts":{"test":"node verify.test.js"}}
EOF
cat > proj/verify.test.js <<'EOF'
const dc = require('depcheck');
process.exit(dc.ok() ? 0 : 1);
EOF
printf 'exports.ok = () => false;' > proj/node_modules/depcheck/index.js
printf '{"name":"depcheck","version":"1.0.0","main":"index.js"}' > proj/node_modules/depcheck/package.json

cat > agent.sh <<'EOF'
#!/bin/bash
python3 - <<'PY'
import os
root = "node_modules"          # symlink -> ORIGINAL project's node_modules
for dp, dn, fn in os.walk(root):
    os.chmod(dp, 0o755)        # undo vacant's read-only (we own the files)
    for f in fn:
        os.chmod(os.path.join(dp, f), 0o644)
p = os.path.join(root, "depcheck", "index.js")
st = os.stat(p)
new = 'exports.ok = () => true; '   # same byte length as the original
assert len(new.encode()) == st.st_size
with open(p, "w") as f:
    f.write(new)
os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))   # restore mtime -> manifest identical
PY
EOF
chmod +x agent.sh

cd proj
timeout 120 "$VACANT" do --cmd "$ROOT/agent.sh {prompt}" --prompt "make npm test pass" --attempts 1
echo "EXIT=$?"
echo "=== ORIGINAL node_modules/depcheck/index.js after the run:"; cat node_modules/depcheck/index.js; echo
echo "(still poisoned in the original project; nothing in the output above mentioned node_modules)"
