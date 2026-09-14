"""ow_01_csvjson — hidden checks, 14. **Never enters a workspace.**

Generated from bank/ow_01_csvjson/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_comma_in_quotes():
    # anchor_kind: goal
    # anchor: fields containing commas
    # derivation: a hand-edited field that holds commas must arrive as one value, not several.

    import json


    def _bank_entry(solution):
        text = 'id,addr\n7,"12 Main St, Apt 4, Rear"\n'
        got = json.loads(solution.csv_to_jsonl(text).splitlines()[0])
        want = {"id": "7", "addr": "12 Main St, Apt 4, Rear"}
        assert got == want, "args=%r got=%r want=%r" % (text, got, want)
    _bank_entry(solution)


def check_h02_newline_in_quotes():
    # anchor_kind: goal
    # anchor: fields containing line breaks
    # derivation: a line break inside a quoted field belongs to the value, so the record
    # spans two physical lines and still produces one object.

    import json


    def _bank_entry(solution):
        text = 'id,memo\n9,"first\nsecond"\n10,plain\n'
        out = solution.csv_to_jsonl(text)
        lines = out.splitlines()
        assert len(lines) == 2, "args=%r got=%r want=%r" % (text, len(lines), 2)
        got = json.loads(lines[0])
        want = {"id": "9", "memo": "first\nsecond"}
        assert got == want, "args=%r got=%r want=%r" % (text, got, want)
    _bank_entry(solution)


def check_h03_doubled_quote():
    # anchor_kind: contract
    # anchor: inside such a field a doubled `""` stands for one literal double quote
    # derivation: the escape has to collapse to exactly one quote character.

    import json


    def _bank_entry(solution):
        text = 'who,said\nann,"she said ""no"" twice"\n'
        got = json.loads(solution.csv_to_jsonl(text).splitlines()[0])
        want = {"who": "ann", "said": 'she said "no" twice'}
        assert got == want, "args=%r got=%r want=%r" % (text, got, want)
    _bank_entry(solution)


def check_h04_blank_column():
    # anchor_kind: goal
    # anchor: whole columns left blank
    # derivation: a column nobody filled in yields the empty string on every row, and a
    # record whose fields are all empty is still a record.

    import json


    def _bank_entry(solution):
        text = "a,b,c\n1,,x\n,,\n"
        lines = solution.csv_to_jsonl(text).splitlines()
        assert len(lines) == 2, "args=%r got=%r want=%r" % (text, len(lines), 2)
        first, second = json.loads(lines[0]), json.loads(lines[1])
        assert first == {"a": "1", "b": "", "c": "x"}, (
            "args=%r got=%r want=%r" % (text, first, {"a": "1", "b": "", "c": "x"}))
        assert second == {"a": "", "b": "", "c": ""}, (
            "args=%r got=%r want=%r" % (text, second, {"a": "", "b": "", "c": ""}))
    _bank_entry(solution)


def check_h05_repeated_header():
    # anchor_kind: contract
    # anchor: When a header name repeats, the last occurrence wins.
    # derivation: two columns called the same thing collapse to one key holding the
    # rightmost column's value.

    import json


    def _bank_entry(solution):
        text = "k,v,k\nalpha,1,omega\n"
        got = json.loads(solution.csv_to_jsonl(text).splitlines()[0])
        want = {"k": "omega", "v": "1"}
        assert got == want, "args=%r got=%r want=%r" % (text, got, want)
    _bank_entry(solution)


def check_h06_crlf():
    # anchor_kind: contract
    # anchor: `"\n"` and `"\r\n"` are both accepted as line endings and neither survives
    # derivation: a file last saved on Windows must not leave a stray carriage return
    # glued to the final value of every row.

    import json


    def _bank_entry(solution):
        text = "x,y\r\n1,2\r\n3,4\r\n"
        lines = solution.csv_to_jsonl(text).splitlines()
        assert len(lines) == 2, "args=%r got=%r want=%r" % (text, len(lines), 2)
        got = [json.loads(line) for line in lines]
        want = [{"x": "1", "y": "2"}, {"x": "3", "y": "4"}]
        assert got == want, "args=%r got=%r want=%r" % (text, got, want)
    _bank_entry(solution)


def check_h07_non_ascii():
    # anchor_kind: goal
    # anchor: Some of the data is not ASCII and has to survive the trip unchanged.
    # derivation: non-ASCII values must come back out identical, whatever escaping the
    # JSON writer chooses.

    import json


    def _bank_entry(solution):
        text = "name,city\n張三,台南\n"
        got = json.loads(solution.csv_to_jsonl(text).splitlines()[0])
        want = {"name": "張三", "city": "台南"}
        assert got == want, "args=%r got=%r want=%r" % (text, got, want)
    _bank_entry(solution)


def check_h08_line_number_of_bad_row():
    # anchor_kind: contract
    # anchor: `N` is the 1-based line number on which the offending record starts and the
    # header is line 1
    # derivation: the reported number must point at the record that is actually wrong,
    # even when an earlier record spanned two physical lines.

    def _bank_entry(solution):
        text = 'a,b\n1,"two\nlines"\n3\n'
        try:
            solution.csv_to_jsonl(text)
        except ValueError as exc:
            got = str(exc)
            assert got.startswith("line 4: "), "args=%r got=%r want=%r" % (text, got, "line 4: ...")
            return
        raise AssertionError("args=%r got=%r want=%r" % (text, "no error", "ValueError"))
    _bank_entry(solution)


def check_h09_unclosed_quote():
    # anchor_kind: contract
    # anchor: Invalid means: a record whose field count differs from the header, or an
    # unclosed quote.
    # derivation: a quote that is never closed is an error, not a value that runs to the
    # end of the file.

    def _bank_entry(solution):
        text = 'a,b\n1,"never closed\n'
        try:
            solution.csv_to_jsonl(text)
        except ValueError as exc:
            got = str(exc)
            assert got.startswith("line 2: "), "args=%r got=%r want=%r" % (text, got, "line 2: ...")
            return
        raise AssertionError("args=%r got=%r want=%r" % (text, "no error", "ValueError"))
    _bank_entry(solution)


def check_h10_exit_code_is_the_signal():
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


    def _bank_entry(solution):
        ok = "h,i\n1,2\n"
        proc = _run(solution, ok)
        assert proc.returncode == 0, "args=%r got=%r want=%r" % (ok, proc.returncode, 0)
        broken = 'h,i\n1,2,3\n'
        proc = _run(solution, broken)
        assert proc.returncode == 2, "args=%r got=%r want=%r" % (broken, proc.returncode, 2)
    _bank_entry(solution)


def check_h11_stdout_not_polluted():
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


    def _bank_entry(solution):
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
    _bank_entry(solution)


def check_h12_no_data_rows():
    # anchor_kind: contract
    # anchor: When there are no data rows the result is the empty string.
    # derivation: an empty file and a header-only file both have zero data rows.

    def _bank_entry(solution):
        for text in ("", "only,a,header\n", "only,a,header"):
            got = solution.csv_to_jsonl(text)
            assert got == "", "args=%r got=%r want=%r" % (text, got, "")
    _bank_entry(solution)


def check_h13_missing_final_newline():
    # anchor_kind: contract
    # anchor: The input may or may not end with a final newline; that makes no
    # difference to the output.
    # derivation: the same data with and without a trailing newline must convert
    # identically, including the newline the output itself must end with.

    def _bank_entry(solution):
        with_nl = "u,v\n5,6\n7,8\n"
        without = "u,v\n5,6\n7,8"
        a = solution.csv_to_jsonl(with_nl)
        b = solution.csv_to_jsonl(without)
        assert a == b, "args=%r got=%r want=%r" % (without, b, a)
        assert b.endswith("\n"), "args=%r got=%r want=%r" % (without, b, "ends with a newline")
    _bank_entry(solution)


def check_h14_one_object_per_line():
    # anchor_kind: contract
    # anchor: one JSON object per data row, each object on its own line
    # derivation: three data rows give three lines, each of which parses on its own as
    # one object whose values are all strings.

    import json


    def _bank_entry(solution):
        text = "n\n1\n2\n3\n"
        got = solution.csv_to_jsonl(text)
        lines = got.splitlines()
        assert len(lines) == 3, "args=%r got=%r want=%r" % (text, len(lines), 3)
        for line in lines:
            obj = json.loads(line)
            assert isinstance(obj, dict), "args=%r got=%r want=%r" % (text, type(obj).__name__, "dict")
            for value in obj.values():
                assert isinstance(value, str), (
                    "args=%r got=%r want=%r" % (text, type(value).__name__, "str"))
    _bank_entry(solution)
