#!/bin/bash
# r4 — class (b): .git/objects/** is skipped by the lstat listing, so agent writes under
# it are invisible: planted objects/info/alternates + grafts + pack files and DELETED
# loose objects all go unreported in message and receipt while the repo is damaged.
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
B="$ROOT/projects/r4-gitobj"
P="$B/proj"
export VACANT_HOME="$B/vh"
export VACANT_WORK="$B/vw"
rm -rf "$B"; mkdir -p "$P"

cd "$P"
git init -q .
git config user.email t@t; git config user.name t
cat > impl.py <<'EOF'
def answer():
    return 41
EOF
cat > test_impl.py <<'EOF'
import unittest, impl
class T(unittest.TestCase):
    def test_a(self):
        self.assertEqual(impl.answer(), 42)
EOF
git add -A; git commit -qm init
LOOSE_BEFORE=$(find .git/objects -type f | wc -l)

cat > "$B/agent.py" <<EOF
import pathlib
p = pathlib.Path('impl.py')
p.write_text(p.read_text().replace('41', '42'))
proj = pathlib.Path('$P')
info = proj / '.git/objects/info'
info.mkdir(parents=True, exist_ok=True)
(info / 'alternates').write_text('/nonexistent/evil-objects\n')
(info / 'grafts').write_text('0'*40 + ' ' + '1'*40 + '\n')
(proj / '.git/objects/pack/pack-evil.pack').write_text('PACK')
loose = [f for f in (proj / '.git/objects').rglob('*')
         if f.is_file() and 'pack' not in f.parts and 'info' not in f.parts]
if loose:
    loose[0].unlink()
    print('deleted loose object:', loose[0])
EOF

"$VAC" do --cmd "python3 $B/agent.py" --prompt 'fix impl'
echo "===== EXIT=$?"
echo "----- planted files still present:"
ls -la .git/objects/info/ .git/objects/pack/pack-evil.pack 2>&1
echo "----- objects before: $LOOSE_BEFORE after: $(find .git/objects -type f | wc -l)"
echo "----- git fsck damage probe:"
git -C "$P" fsck 2>&1 | head -5
echo "----- outside_changes / receipt fields in result.json:"
python3 - <<'PYEOF'
import json, glob, os
rs = sorted(glob.glob(os.environ['VACANT_WORK'] + '/restart-*/result.json'))
res = json.load(open(rs[-1]))
print('outside_changes:', res.get('outside_changes'))
print('receipt recorded:', (res.get('receipt') or {}).get('recorded'))
PYEOF
