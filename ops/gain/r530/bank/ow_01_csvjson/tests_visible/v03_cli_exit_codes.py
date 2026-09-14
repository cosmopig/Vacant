"""Visible check 3: the command line -- exit 0 on success, exit 2 on a bad row."""

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
    good = "city,pop\nTaipei,2600000\nTainan,1860000\n"
    proc = _run(solution, good)
    assert proc.returncode == 0, "args=%r got=%r want=%r" % (good, proc.returncode, 0)
    rows = [json.loads(x) for x in proc.stdout.splitlines()]
    assert rows == [{"city": "Taipei", "pop": "2600000"},
                    {"city": "Tainan", "pop": "1860000"}], (
        "args=%r got=%r want=%r" % (good, rows, "two objects"))

    bad = "city,pop\nTaipei,2600000\nTainan\n"
    proc = _run(solution, bad)
    assert proc.returncode == 2, "args=%r got=%r want=%r" % (bad, proc.returncode, 2)
    assert proc.stdout == "", "args=%r got=%r want=%r" % (bad, proc.stdout, "")
    err = proc.stderr.splitlines()
    assert len(err) == 1, "args=%r got=%r want=%r" % (bad, err, "exactly one line")
    assert err[0].startswith("line 3: "), "args=%r got=%r want=%r" % (bad, err[0], "line 3: ...")

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v03_cli_exit_codes")
