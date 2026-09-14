"""ow_08_logscan — hidden checks, 16. **Never enters a workspace.**

Generated from bank/ow_08_logscan/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_five_hundreds_only():
    # anchor_kind: goal
    # anchor: Failed means the server's own fault, the five-hundreds; a client sending
    # a bad request is not a failure of theirs.
    # derivation: a run of four-hundreds contributes nothing to the error share, while
    # a single five-hundred does.


    def _bank_entry(solution):
        lines = ["2026-01-01T00:00:00Z GET /q 400 1",
                 "2026-01-01T00:00:01Z GET /q 401 1",
                 "2026-01-01T00:00:02Z GET /q 404 1",
                 "2026-01-01T00:00:03Z GET /q 499 1"]
        got = solution.summarize(lines)["endpoints"][0]["error_rate"]
        assert got == 0.0, "args=%r got=%r want=%r" % ("four four-hundreds", got, 0.0)

        lines.append("2026-01-01T00:00:04Z GET /q 500 1")
        got = solution.summarize(lines)["endpoints"][0]["error_rate"]
        assert got == 0.2, "args=%r got=%r want=%r" % ("one five-hundred in five", got, 0.2)
    _bank_entry(solution)


def check_h02_error_rate_rounded():
    # anchor_kind: contract
    # anchor: rounded to four decimal places
    # derivation: one failure in three is 0.3333 exactly, not the full repeating float.


    def _bank_entry(solution):
        lines = ["2026-01-01T00:00:00Z GET /r 500 1",
                 "2026-01-01T00:00:01Z GET /r 200 1",
                 "2026-01-01T00:00:02Z GET /r 200 1"]
        got = solution.summarize(lines)["endpoints"][0]["error_rate"]
        assert got == 0.3333, "args=%r got=%r want=%r" % ("one in three", got, 0.3333)

        lines = ["2026-01-01T00:00:0%d GET /r %d 1" % (i, 500 if i == 0 else 200) for i in range(7)]
        got = solution.summarize(lines)["endpoints"][0]["error_rate"]
        assert got == 0.1429, "args=%r got=%r want=%r" % ("one in seven", got, 0.1429)
    _bank_entry(solution)


def check_h03_p50_nearest_rank():
    # anchor_kind: contract
    # anchor: the p-th percentile of n sorted values is the one at 1-based position
    # `ceil(p / 100 * n)`
    # derivation: with four values the median rank is ceil(2.0) = 2, which is the
    # second smallest -- a floor-indexed implementation returns the third.


    def _bank_entry(solution):
        lines = ["2026-01-01T00:00:0%d GET /m 200 %d" % (i, v)
                 for i, v in enumerate([40, 10, 30, 20])]
        got = solution.summarize(lines)["endpoints"][0]["p50_ms"]
        assert got == 20, "args=%r got=%r want=%r" % ("latencies 10,20,30,40", got, 20)
    _bank_entry(solution)


def check_h04_p95_nearest_rank():
    # anchor_kind: goal
    # anchor: the unlucky tail
    # derivation: with four values the 95th percentile rank is ceil(3.8) = 4, the
    # largest; with ten values it is ceil(9.5) = 10, also the largest.


    def _bank_entry(solution):
        lines = ["2026-01-01T00:00:0%d GET /t 200 %d" % (i, v)
                 for i, v in enumerate([40, 10, 30, 20])]
        got = solution.summarize(lines)["endpoints"][0]["p95_ms"]
        assert got == 40, "args=%r got=%r want=%r" % ("latencies 10,20,30,40", got, 40)

        values = [5, 15, 25, 35, 45, 55, 65, 75, 85, 95]
        lines = ["2026-01-01T00:0%d:00Z GET /t 200 %d" % (i, v) for i, v in enumerate(values)]
        got = solution.summarize(lines)["endpoints"][0]["p95_ms"]
        assert got == 95, "args=%r got=%r want=%r" % ("ten latencies", got, 95)
    _bank_entry(solution)


def check_h05_single_sample():
    # anchor_kind: contract
    # anchor: Percentiles are nearest-rank
    # derivation: with one value the rank is 1 for every percentile, so both numbers are
    # that value.


    def _bank_entry(solution):
        lines = ["2026-01-01T00:00:00Z POST /only 200 77"]
        got = solution.summarize(lines)["endpoints"][0]
        assert (got["p50_ms"], got["p95_ms"]) == (77, 77), (
            "args=%r got=%r want=%r" % (lines, (got["p50_ms"], got["p95_ms"]), (77, 77)))
    _bank_entry(solution)


def check_h06_busiest_first():
    # anchor_kind: goal
    # anchor: They want the busiest endpoints at the top
    # derivation: the ordering is by request count from large to small, whatever order
    # the paths were first seen in.


    def _bank_entry(solution):
        lines = (["2026-01-01T00:00:00Z GET /rare 200 1"]
                 + ["2026-01-01T00:00:0%d GET /busy 200 1" % (i % 10) for i in range(5)]
                 + ["2026-01-01T00:00:0%d GET /mid 200 1" % (i % 10) for i in range(3)])
        got = [row["path"] for row in solution.summarize(lines)["endpoints"]]
        want = ["/busy", "/mid", "/rare"]
        assert got == want, "args=%r got=%r want=%r" % ("1 rare, 5 busy, 3 mid", got, want)
    _bank_entry(solution)


def check_h07_tie_broken_by_path():
    # anchor_kind: goal
    # anchor: when two are equally busy they want the order to be the same every time
    # they run it
    # derivation: equal counts are separated by the path in ordinary string order, so
    # the answer does not depend on which path appeared first in the file.


    def _bank_entry(solution):
        first = ["2026-01-01T00:00:00Z GET /zebra 200 1", "2026-01-01T00:00:01Z GET /apple 200 1"]
        second = list(reversed(first))
        got_first = [row["path"] for row in solution.summarize(first)["endpoints"]]
        got_second = [row["path"] for row in solution.summarize(second)["endpoints"]]
        want = ["/apple", "/zebra"]
        assert got_first == want, "args=%r got=%r want=%r" % (first, got_first, want)
        assert got_second == want, "args=%r got=%r want=%r" % (second, got_second, want)
    _bank_entry(solution)


def check_h08_wrong_field_count():
    # anchor_kind: contract
    # anchor: A line is bad when it does not have exactly five fields
    # derivation: too few fields and too many fields are both bad, and neither adds a
    # request to any endpoint.


    def _bank_entry(solution):
        lines = ["2026-01-01T00:00:00Z GET /ok 200 1",
                 "2026-01-01T00:00:01Z GET /short 200",
                 "2026-01-01T00:00:02Z GET /long 200 1 extra"]
        got = solution.summarize(lines)
        assert got["bad_lines"] == 2, "args=%r got=%r want=%r" % (lines, got["bad_lines"], 2)
        assert len(got["endpoints"]) == 1, (
            "args=%r got=%r want=%r" % (lines, len(got["endpoints"]), 1))
    _bank_entry(solution)


def check_h09_non_integer_fields():
    # anchor_kind: contract
    # anchor: when `STATUS` or `MS` is not a run of digits with an optional leading `-`
    # derivation: a status or a duration that is not an integer makes the line
    # unusable, and a negative one does not.


    def _bank_entry(solution):
        lines = ["2026-01-01T00:00:00Z GET /n 20x 5",
                 "2026-01-01T00:00:01Z GET /n 200 5.5",
                 "2026-01-01T00:00:02Z GET /n 200 -3"]
        got = solution.summarize(lines)
        assert got["bad_lines"] == 2, "args=%r got=%r want=%r" % (lines, got["bad_lines"], 2)
        assert got["endpoints"][0]["n"] == 1, (
            "args=%r got=%r want=%r" % (lines, got["endpoints"][0]["n"], 1))
    _bank_entry(solution)


def check_h10_bad_timestamp():
    # anchor_kind: contract
    # anchor: or when the timestamp is not ISO8601
    # derivation: a timestamp that is not a real date-time makes the line unusable even
    # though the other four fields are fine.


    def _bank_entry(solution):
        lines = ["yesterday GET /s 200 1",
                 "2026-13-45T99:99:99Z GET /s 200 1",
                 "2026-01-01T00:00:00Z GET /s 200 1"]
        got = solution.summarize(lines)
        assert got["bad_lines"] == 2, "args=%r got=%r want=%r" % (lines, got["bad_lines"], 2)
        assert got["total"] == 3, "args=%r got=%r want=%r" % (lines, got["total"], 3)
    _bank_entry(solution)


def check_h11_bad_lines_are_reported():
    # anchor_kind: goal
    # anchor: They also want to know how many lines were unusable
    # derivation: the count of unusable lines is part of the answer and keeps rising
    # through a file that is mostly rubbish, without the run stopping.


    def _bank_entry(solution):
        lines = ["rubbish %d" % index for index in range(20)]
        lines.insert(10, "2026-01-01T00:00:00Z GET /one 200 9")
        got = solution.summarize(lines)
        assert got["bad_lines"] == 20, "args=%r got=%r want=%r" % ("20 junk + 1 good", got["bad_lines"], 20)
        assert got["total"] == 21, "args=%r got=%r want=%r" % ("20 junk + 1 good", got["total"], 21)
        assert got["endpoints"][0]["path"] == "/one", (
            "args=%r got=%r want=%r" % ("20 junk + 1 good", got["endpoints"], "/one survives"))
    _bank_entry(solution)


def check_h12_blank_lines_are_nothing():
    # anchor_kind: goal
    # anchor: Blank lines are just noise from the rotation script and should not count
    # as anything at all.
    # derivation: an empty or whitespace-only line is neither a request nor a bad line,
    # so neither total nor bad_lines moves.


    def _bank_entry(solution):
        lines = ["", "   ", "\t", "2026-01-01T00:00:00Z GET /z 200 1", "", "\n"]
        got = solution.summarize(lines)
        assert got["total"] == 1, "args=%r got=%r want=%r" % (lines, got["total"], 1)
        assert got["bad_lines"] == 0, "args=%r got=%r want=%r" % (lines, got["bad_lines"], 0)
    _bank_entry(solution)


def check_h13_trailing_newlines():
    # anchor_kind: contract
    # anchor: Any trailing newline is not part of the line.
    # derivation: lines read straight from a file keep their newline, which must not
    # turn the last field into something non-numeric.


    def _bank_entry(solution):
        lines = ["2026-01-01T00:00:00Z GET /f 200 12\n",
                 "2026-01-01T00:00:01Z GET /f 500 34\r\n"]
        got = solution.summarize(lines)
        assert got["bad_lines"] == 0, "args=%r got=%r want=%r" % (lines, got["bad_lines"], 0)
        endpoint = got["endpoints"][0]
        assert (endpoint["n"], endpoint["error_rate"]) == (2, 0.5), (
            "args=%r got=%r want=%r" % (lines, (endpoint["n"], endpoint["error_rate"]), (2, 0.5)))
    _bank_entry(solution)


def check_h14_result_shape():
    # anchor_kind: contract
    # anchor: The result has exactly this shape
    # derivation: the three top-level keys and the five per-endpoint keys are fixed,
    # the counts are ints and the percentiles are ints, and an empty log still has the
    # shape.


    def _bank_entry(solution):
        empty = solution.summarize([])
        assert empty == {"endpoints": [], "bad_lines": 0, "total": 0}, (
            "args=%r got=%r want=%r" % ([], empty, {"endpoints": [], "bad_lines": 0, "total": 0}))

        lines = ["2026-01-01T00:00:00Z GET /k 500 8"]
        got = solution.summarize(lines)
        assert sorted(got) == ["bad_lines", "endpoints", "total"], (
            "args=%r got=%r want=%r" % (lines, sorted(got), ["bad_lines", "endpoints", "total"]))
        row = got["endpoints"][0]
        assert sorted(row) == ["error_rate", "n", "p50_ms", "p95_ms", "path"], (
            "args=%r got=%r want=%r" % (lines, sorted(row),
                                        ["error_rate", "n", "p50_ms", "p95_ms", "path"]))
        kinds = (type(row["n"]).__name__, type(row["p50_ms"]).__name__,
                 type(row["error_rate"]).__name__, type(row["path"]).__name__)
        assert kinds == ("int", "int", "float", "str"), (
            "args=%r got=%r want=%r" % (lines, kinds, ("int", "int", "float", "str")))
    _bank_entry(solution)


def check_h15_cli_gives_back_the_result():
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


    def _bank_entry(solution):
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
    _bank_entry(solution)


def check_h16_cli_survives_bad_lines():
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


    def _bank_entry(solution):
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
    _bank_entry(solution)
