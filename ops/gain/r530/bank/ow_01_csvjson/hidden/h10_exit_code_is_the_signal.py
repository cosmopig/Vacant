# anchor_kind: goal
# anchor: success and failure have to be distinguishable without reading the output
# derivation: a shell script only sees the exit status, so it has to differ between
# a good file and a bad one.

import os
import subprocess
import sys
import tempfile


def _run(solution, body):
    home = os.path.dirname(os.path.abspath(solution.__file__))
    handle, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(handle, "w", encoding="utf-8", newline="") as fh:
        fh.write(body)
    return subprocess.run([sys.executable, "-m", "solution", path],
                          cwd=home, capture_output=True, text=True)


def run(solution):
    ok = "h,i\n1,2\n"
    proc = _run(solution, ok)
    assert proc.returncode == 0, "args=%r got=%r want=%r" % (ok, proc.returncode, 0)
    broken = 'h,i\n1,2,3\n'
    proc = _run(solution, broken)
    assert proc.returncode == 2, "args=%r got=%r want=%r" % (broken, proc.returncode, 2)
