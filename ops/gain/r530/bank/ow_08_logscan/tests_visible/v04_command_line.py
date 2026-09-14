"""Visible check 4: the command line -- one JSON object on stdout, exit 0."""

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
    body = ("2026-09-13T09:00:00Z GET /a 200 10\n"
            "2026-09-13T09:00:01Z GET /a 500 30\n")
    proc = _run(solution, body)
    assert proc.returncode == 0, "args=%r got=%r want=%r" % (body, proc.returncode, 0)
    got = json.loads(proc.stdout)
    want = {"endpoints": [{"path": "/a", "n": 2, "error_rate": 0.5,
                           "p50_ms": 10, "p95_ms": 30}],
            "bad_lines": 0, "total": 2}
    assert got == want, "args=%r got=%r want=%r" % (body, got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v04_command_line")
