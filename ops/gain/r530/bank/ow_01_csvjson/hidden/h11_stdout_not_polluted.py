# anchor_kind: goal
# anchor: the converted data must not be polluted by chatter
# derivation: stdout carries the data and nothing else, and on failure it carries
# nothing at all while the complaint goes to stderr as a single line.

import json
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
    body = "p,q\n8,9\n"
    proc = _run(solution, body)
    parsed = [json.loads(line) for line in proc.stdout.splitlines()]
    assert parsed == [{"p": "8", "q": "9"}], (
        "args=%r got=%r want=%r" % (body, proc.stdout, '{"p": "8", "q": "9"}'))
    assert proc.stderr == "", "args=%r got=%r want=%r" % (body, proc.stderr, "")

    body = "p,q\n8\n"
    proc = _run(solution, body)
    assert proc.stdout == "", "args=%r got=%r want=%r" % (body, proc.stdout, "")
    assert len(proc.stderr.splitlines()) == 1, (
        "args=%r got=%r want=%r" % (body, proc.stderr, "exactly one line"))
