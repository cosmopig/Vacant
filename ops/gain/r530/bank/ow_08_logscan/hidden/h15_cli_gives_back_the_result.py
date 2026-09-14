# anchor_kind: goal
# anchor: Finally they want to eyeball a file from the shell without writing a
# script
# derivation: eyeballing from the shell is one command over one file, and the
# contract fixes what comes back out of it: the same result the library call gives,
# as one JSON object on stdout, with exit 0.

import json
import os
import subprocess
import sys
import tempfile


def _run(solution, body):
    home = os.path.dirname(os.path.abspath(solution.__file__))
    handle, path = tempfile.mkstemp(suffix=".log")
    with os.fdopen(handle, "w", encoding="utf-8") as fh:
        fh.write(body)
    return subprocess.run([sys.executable, "-m", "solution", path],
                          cwd=home, capture_output=True, text=True)


def run(solution):
    body = ("2026-02-02T08:00:00Z GET /alpha 200 40\n"
            "2026-02-02T08:00:01Z POST /beta 503 90\n"
            "2026-02-02T08:00:02Z GET /alpha 200 60\n"
            "2026-02-02T08:00:03Z GET /alpha 500 80\n")
    proc = _run(solution, body)
    assert proc.returncode == 0, "args=%r got=%r want=%r" % (body, proc.returncode, 0)
    got = json.loads(proc.stdout)
    want = {"endpoints": [{"path": "/alpha", "n": 3, "error_rate": 0.3333,
                           "p50_ms": 60, "p95_ms": 80},
                          {"path": "/beta", "n": 1, "error_rate": 1.0,
                           "p50_ms": 90, "p95_ms": 90}],
            "bad_lines": 0, "total": 4}
    assert got == want, "args=%r got=%r want=%r" % (body, got, want)
