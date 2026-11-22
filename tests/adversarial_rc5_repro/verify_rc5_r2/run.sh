#!/bin/bash
# P1 re-check. usage: run.sh <scenario> <fix|break|noop>
set -u
S=/tmp/claude-1000/-home-user1/d5cfe187-d4b3-509f-92d8-4eaf44bea4f5/scratchpad
V=${V:-$S/r2/venv/bin/vacant}
sc=$1; mode=$2; R=$S/r2/p1/run/$sc-$mode; rm -rf $R; mkdir -p $R/proj; cd $R
export VACANT_HOME=$R/vh VACANT_WORK=$R/vw
PLAIN="python3 -m unittest -q"
case $sc in
d) printf 'class Q:\n    def __init__(self): self.items=[]\n    def push(self,x): self.items.append(x)\n    def pop(self): return self.items.pop()\n' > proj/queue.py
   printf 'import unittest\nfrom queue import Q\nclass T(unittest.TestCase):\n    def test_fifo(self):\n        q=Q(); q.push(1); q.push(2); self.assertEqual(q.pop(),1)\n' > proj/test_queue.py
   FIX='sed -i "s/items.pop()/items.pop(0)/" queue.py'; BREAK='sed -i "s/items.pop()/items.pop(-1)/" queue.py';;
d2) python3 -m venv proj/.venv; proj/.venv/bin/pip -q install pytest >/dev/null 2>&1
   printf 'class Q:\n    def __init__(self): self.items=[]\n    def push(self,x): self.items.append(x)\n    def pop(self): return self.items.pop()\n' > proj/queue.py
   printf 'from queue import Q\ndef test_fifo():\n    q=Q(); q.push(1); q.push(2); assert q.pop()==1\n' > proj/test_queue.py
   PLAIN="proj_venv_pytest"
   FIX='sed -i "s/items.pop()/items.pop(0)/" queue.py'; BREAK='sed -i "s/items.pop()/items.pop(-1)/" queue.py';;
m1|m10) printf 'def median(xs):\n    xs = sorted(xs)\n    return xs[0]\n' > proj/statistics.py
   if [ $sc = m1 ]; then printf 'import unittest\nfrom statistics import median\nclass T(unittest.TestCase):\n    def test_median(self):\n        self.assertEqual(median([3, 1, 2]), 2)\n' > proj/test_stats.py
   else printf 'from statistics import median\ndef test_median():\n    assert median([3,1,2]) == 2\n' > proj/test_stats.py; PLAIN="bare"; fi
   FIX='printf "def median(xs):\\n    xs = sorted(xs)\\n    return xs[len(xs)//2]\\n" > statistics.py'; BREAK='printf "def median(xs):\\n    return None\\n" > statistics.py';;
v1) # subpackage module named like stdlib, imported absolutely from inside the package
   mkdir -p proj/app; : > proj/app/__init__.py
   printf 'def fmt(x):\n    return "%%d" %% x\n' > proj/app/string.py
   printf 'from app import string as s\ndef show(x):\n    return "[" + s.fmt(x) + "]"\n' > proj/app/view.py
   printf 'import unittest\nfrom app.view import show\nclass T(unittest.TestCase):\n    def test_show(self):\n        self.assertEqual(show(7), "[007]")\n' > proj/test_view.py
   FIX='sed -i "s/%d/%03d/" app/string.py'; BREAK='sed -i "s/%d/%d!/" app/string.py';;
v2) # top-level logging.py reached indirectly through helpers.py
   printf 'def level_name(n):\n    return {10: "DEBUG", 20: "INFO"}.get(n, "?")\n' > proj/logging.py
   printf 'import logging\ndef describe(n):\n    return "level=" + logging.level_name(n)\n' > proj/helpers.py
   printf 'import unittest\nimport helpers\nclass T(unittest.TestCase):\n    def test_desc(self):\n        self.assertEqual(helpers.describe(30), "level=WARNING")\n' > proj/test_helpers.py
   FIX='sed -i "s/20: \"INFO\"}/20: \"INFO\", 30: \"WARNING\"}/" logging.py'; BREAK='sed -i "s/\"?\"/\"WARN\"/" logging.py';;
v3) # tests in tests/ subdir, project calendar.py at root
   mkdir -p proj/tests; : > proj/tests/__init__.py
   printf 'def days_in_feb(y):\n    return 28\n' > proj/calendar.py
   printf 'import unittest\nfrom calendar import days_in_feb\nclass T(unittest.TestCase):\n    def test_leap(self):\n        self.assertEqual(days_in_feb(2024), 29)\n' > proj/tests/test_cal.py
   PLAIN="python3 -m unittest discover -q -s tests -t ."
   FIX='printf "def days_in_feb(y):\\n    return 29 if (y%%4==0 and y%%100!=0) or y%%400==0 else 28\\n" > calendar.py'; BREAK='printf "def days_in_feb(y):\\n    return 30\\n" > calendar.py';;
v4) # project module "types.py" (already imported at interpreter startup)
   printf 'def kind(x):\n    return "num"\n' > proj/types.py
   printf 'import unittest\nfrom types import kind\nclass T(unittest.TestCase):\n    def test_kind(self):\n        self.assertEqual(kind("a"), "str")\n' > proj/test_types.py
   FIX='printf "def kind(x):\\n    return \\"str\\" if isinstance(x, str) else \\"num\\"\\n" > types.py'; BREAK='printf "def kind(x):\\n    return None\\n" > types.py';;
esac
case $mode in fix) CMD=$FIX;; break) CMD=$BREAK;; noop) CMD=true;; esac
printf '#!/bin/bash\n%s\n' "$CMD" > agent.sh; chmod +x agent.sh
plain() { ( cd $1
  case "$PLAIN" in
    proj_venv_pytest) .venv/bin/python -m pytest -q -p no:cacheprovider 2>&1 | tail -1;;
    bare) python3 -c "import test_stats; test_stats.test_median(); print('OK')" 2>&1 | tail -1;;
    *) $PLAIN 2>&1 | tail -1;;
  esac ) }
cp -r proj plain_before; echo "plain before: $(plain plain_before)"
cp -r proj plain_after; (cd plain_after && bash ../agent.sh); echo "plain after agent ($mode): $(plain plain_after)"
cd proj; $V do --cmd "$R/agent.sh {prompt}" --prompt fix --attempts 1 2>&1 | grep -v "scanned:\|attempts and logs\|interpreter:\|attempt 1 of"; echo "EXIT=${PIPESTATUS[0]}"
