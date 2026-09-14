"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_counts_and_error_share():
    """Visible check 1: per-endpoint counts, busiest first, five-hundreds only."""


    def _bank_entry(solution):
        lines = [
            "2026-09-13T10:00:00Z GET /a 200 10",
            "2026-09-13T10:00:01Z GET /a 500 20",
            "2026-09-13T10:00:02Z GET /a 404 30",
            "2026-09-13T10:00:03Z GET /a 503 40",
            "2026-09-13T10:00:04Z GET /b 200 50",
        ]
        got = solution.summarize(lines)
        paths = [row["path"] for row in got["endpoints"]]
        assert paths == ["/a", "/b"], "args=%r got=%r want=%r" % (lines, paths, ["/a", "/b"])
        first = got["endpoints"][0]
        assert first["n"] == 4, "args=%r got=%r want=%r" % (lines, first["n"], 4)
        assert first["error_rate"] == 0.5, "args=%r got=%r want=%r" % (lines, first["error_rate"], 0.5)
        assert got["total"] == 5, "args=%r got=%r want=%r" % (lines, got["total"], 5)
    _bank_entry(solution)


def check_v02_bad_lines_do_not_stop_it():
    """Visible check 2: garbled lines are counted and the run keeps going."""


    def _bank_entry(solution):
        lines = [
            "2026-09-13T11:00:00Z GET /x 200 5",
            "this line is truncat",
            "2026-09-13T11:00:01Z GET /x 200 7",
        ]
        got = solution.summarize(lines)
        assert got["bad_lines"] == 1, "args=%r got=%r want=%r" % (lines, got["bad_lines"], 1)
        assert got["total"] == 3, "args=%r got=%r want=%r" % (lines, got["total"], 3)
        assert got["endpoints"][0]["n"] == 2, (
            "args=%r got=%r want=%r" % (lines, got["endpoints"][0]["n"], 2))
    _bank_entry(solution)


def check_v03_percentiles():
    """Visible check 3: the ordinary middle and the unlucky tail."""


    def _bank_entry(solution):
        lines = ["2026-09-13T12:00:0%d GET /p 200 %d" % (index, value)
                 for index, value in enumerate([50, 10, 40, 20, 30])]
        got = solution.summarize(lines)["endpoints"][0]
        assert got["p50_ms"] == 30, "args=%r got=%r want=%r" % (lines, got["p50_ms"], 30)
        assert got["p95_ms"] == 50, "args=%r got=%r want=%r" % (lines, got["p95_ms"], 50)
    _bank_entry(solution)


def check_v04_command_line():
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


    def _bank_entry(solution):
        body = ("2026-09-13T09:00:00Z GET /a 200 10\n"
                "2026-09-13T09:00:01Z GET /a 500 30\n")
        proc = _run(solution, body)
        assert proc.returncode == 0, "args=%r got=%r want=%r" % (body, proc.returncode, 0)
        got = json.loads(proc.stdout)
        want = {"endpoints": [{"path": "/a", "n": 2, "error_rate": 0.5,
                               "p50_ms": 10, "p95_ms": 30}],
                "bad_lines": 0, "total": 2}
        assert got == want, "args=%r got=%r want=%r" % (body, got, want)
    _bank_entry(solution)
