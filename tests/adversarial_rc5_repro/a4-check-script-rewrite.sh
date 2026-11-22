#!/bin/bash
# FINDING a4-check-script-rewrite (class A: accepted-but-wrong)
# For `--check '<cmd>'`, files that do not match the built-in test-name patterns
# (verify.sh, Makefile, run_checks.py, ...) are not protected even when they ARE
# the check's harness. The agent rewrites the harness to `exit 0` / `@true`;
# the run is accepted and the gutted file is written back. vacant does warn
# "the agent could have edited what this check runs" but still accepts.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VACANT="$HERE/venv/bin/vacant"

for KIND in sh make; do
  ROOT="$(mktemp -d "$HERE/projects/a4$KIND.XXXXXX")"
  export VACANT_HOME="$ROOT/vhome" VACANT_WORK="$ROOT/vwork"
  cd "$ROOT"
  mkdir proj
  cat > proj/impl.py <<'EOF'
def answer():
    return 41  # should be 42
EOF
  if [ "$KIND" = sh ]; then
    printf '#!/bin/bash\npython3 -c "import impl; assert impl.answer()==42"\n' > proj/verify.sh
    cat > agent.sh <<'EOF'
#!/bin/bash
printf '#!/bin/bash\nexit 0\n' > verify.sh
EOF
    CHECK="bash verify.sh"
  else
    printf 'test:\n\t@python3 -c "import impl; assert impl.answer()==42"\n' > proj/Makefile
    cat > agent.sh <<'EOF'
#!/bin/bash
printf 'test:\n\t@true\n' > Makefile
EOF
    CHECK="make test"
  fi
  chmod +x agent.sh
  cd proj
  echo "######## check=$CHECK ########"
  timeout 120 "$VACANT" do --cmd "$ROOT/agent.sh {prompt}" --prompt "make check pass" \
      --check "$CHECK" --attempts 1
  echo "EXIT=$?"
  if [ "$KIND" = sh ]; then echo "=== delivered verify.sh:"; cat verify.sh;
  else echo "=== delivered Makefile:"; cat Makefile; fi
  cd "$ROOT"
done
