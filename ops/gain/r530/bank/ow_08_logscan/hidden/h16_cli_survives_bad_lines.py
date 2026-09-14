# anchor_kind: contract
# anchor: Bad lines in the file are not a reason for the command to fail: it counts
# them the way the library does and still exits 0
# derivation: a file whose lines are mostly garbled, with blank lines mixed in,
# still exits 0, and the object on stdout carries the same bad_lines and total the
# library call would have produced for the same lines.

import json
import os
import subprocess
import sys
import tempfile


def run(solution):
    lines = ["2026-03-03T07:00:00Z GET /ok 200 12",
             "truncated",
             "",
             "2026-03-03T07:00:01Z GET /ok abc 12",
             "   ",
             "not-a-time GET /ok 200 12",
             "2026-03-03T07:00:02Z GET /ok 200 34"]
    body = "\n".join(lines) + "\n"
    home = os.path.dirname(os.path.abspath(solution.__file__))
    handle, path = tempfile.mkstemp(suffix=".log")
    with os.fdopen(handle, "w", encoding="utf-8") as fh:
        fh.write(body)
    proc = subprocess.run([sys.executable, "-m", "solution", path],
                          cwd=home, capture_output=True, text=True)
    assert proc.returncode == 0, "args=%r got=%r want=%r" % (body, proc.returncode, 0)
    got = json.loads(proc.stdout)
    want = solution.summarize(lines)
    assert got == want, "args=%r got=%r want=%r" % (body, got, want)
    assert got["bad_lines"] == 3, "args=%r got=%r want=%r" % (body, got["bad_lines"], 3)
    assert got["total"] == 5, "args=%r got=%r want=%r" % (body, got["total"], 5)
