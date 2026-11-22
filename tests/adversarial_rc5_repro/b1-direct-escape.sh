#!/bin/bash
# FINDING b1-direct-escape (class B: escape from the copy)
# The stand-in agent writes to the ORIGINAL project directory during an attempt
# that is later rejected. Three vectors PERSIST undetected:
#   * files inside .git/ (COPY_SKIP path -> never scanned or planned):
#     an executable .git/hooks/post-commit survives and will run on the next
#     `git commit` in the user's repo;
#   * a planted symlink (scandir skips symlinks -> invisible to the write-back
#     plan);
#   * files anywhere outside the project (never inspected; documented boundary).
# Regular-file escape writes ARE reverted/deleted at delivery (the write-back
# plan diffs the live project against the delivered snapshot), which also means
# any file a user creates in the project during the run is silently deleted.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VACANT="$HERE/venv/bin/vacant"
ROOT="$(mktemp -d "$HERE/projects/b1.XXXXXX")"
export VACANT_HOME="$ROOT/vhome" VACANT_WORK="$ROOT/vwork"
cd "$ROOT"

mkdir proj outside
cd proj && git init -q . && git config user.email t@t && git config user.name t
cat > test_x.py <<'EOF'
import unittest
class T(unittest.TestCase):
    def test_never_passes(self):
        self.assertEqual(1, 2)
EOF
git add -A && git commit -qm init
cd "$ROOT"

cat > agent.sh <<EOF
#!/bin/bash
ORIG="$ROOT/proj"
echo '#!/bin/bash' > "\$ORIG/.git/hooks/post-commit"
echo 'echo HOOK_FIRED' >> "\$ORIG/.git/hooks/post-commit"
chmod +x "\$ORIG/.git/hooks/post-commit"
ln -s /etc/hostname "\$ORIG/planted_link"
echo PWNED > "\$ORIG/pwned_regular.txt"        # regular file: reverted at delivery
echo OUTSIDE > "$ROOT/outside/marker.txt"       # outside project: persists
EOF
chmod +x agent.sh

cd proj
timeout 120 "$VACANT" do --cmd "$ROOT/agent.sh {prompt}" --prompt "fix test" --attempts 1
echo "EXIT=$?"
echo "=== original project after delivery:"; ls -la
echo "=== planted .git/hooks/post-commit:"; cat .git/hooks/post-commit 2>/dev/null || echo "(absent)"
echo "=== planted_link:"; ls -l planted_link 2>/dev/null || echo "(absent)"
echo "=== regular-file escape pwned_regular.txt:"; cat pwned_regular.txt 2>/dev/null || echo "(reverted/deleted at delivery)"
echo "=== outside marker:"; cat "$ROOT/outside/marker.txt" 2>/dev/null || echo "(absent)"
