"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_plain_rows():
    """Visible check 1: the plain path -- rows in, JSON Lines out."""

    import json


    def _bank_entry(solution):
        text = "name,qty,note\npen,3,\nmug,12,chipped\n"
        got = solution.csv_to_jsonl(text)
        assert got.endswith("\n"), "args=%r got=%r want=%r" % (text, got, "a string ending in a newline")
        lines = got.splitlines()
        assert len(lines) == 2, "args=%r got=%r want=%r" % (text, len(lines), 2)
        first = json.loads(lines[0])
        want_first = {"name": "pen", "qty": "3", "note": ""}
        assert first == want_first, "args=%r got=%r want=%r" % (text, first, want_first)
        second = json.loads(lines[1])
        want_second = {"name": "mug", "qty": "12", "note": "chipped"}
        assert second == want_second, "args=%r got=%r want=%r" % (text, second, want_second)
        for value in first.values():
            assert isinstance(value, str), "args=%r got=%r want=%r" % (text, type(value).__name__, "str")
    _bank_entry(solution)


def check_v02_quoted_comma():
    """Visible check 2: a comma inside a quoted field is data, not a separator."""

    import json


    def _bank_entry(solution):
        text = 'sku,colours\nA1,"red, blue"\nB2,green\n'
        got = solution.csv_to_jsonl(text)
        lines = got.splitlines()
        assert len(lines) == 2, "args=%r got=%r want=%r" % (text, len(lines), 2)
        row = json.loads(lines[0])
        want = {"sku": "A1", "colours": "red, blue"}
        assert row == want, "args=%r got=%r want=%r" % (text, row, want)
        assert json.loads(lines[1]) == {"sku": "B2", "colours": "green"}, (
            "args=%r got=%r want=%r" % (text, lines[1], {"sku": "B2", "colours": "green"}))
    _bank_entry(solution)


def check_v03_cli_exit_codes():
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


    def _bank_entry(solution):
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
    _bank_entry(solution)
