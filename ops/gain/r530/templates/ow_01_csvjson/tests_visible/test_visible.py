"""Checks that ship with this task. You can run them yourself: `bash run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns normally.
These are the same checks the client runs before accepting the work.
"""
import json
import os
import subprocess
import sys
import tempfile

import solution


def check_basic_rows():
    text = "name,age\nada,36\ngrace,45\n"
    got = solution.csv_to_jsonl(text)
    want = ('{"name": "ada", "age": "36"}\n'
            '{"name": "grace", "age": "45"}\n')
    assert [json.loads(x) for x in got.splitlines()] == \
           [json.loads(x) for x in want.splitlines()], \
        f"csv_to_jsonl({text!r}) returned {got!r}, expected {want!r}"
    assert got.endswith("\n"), f"the last line must end with a newline: {got!r}"


def check_quoted_comma():
    text = 'city,note\n"Taipei, Taiwan",ok\n'
    got = solution.csv_to_jsonl(text)
    rows = [json.loads(x) for x in got.splitlines()]
    assert rows == [{"city": "Taipei, Taiwan", "note": "ok"}], \
        f"csv_to_jsonl({text!r}) returned {got!r}"


def check_cli_success():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "in.csv")
        with open(p, "w", encoding="utf-8") as f:
            f.write("a,b\n1,2\n")
        r = subprocess.run([sys.executable, "-m", "solution", p],
                           capture_output=True, text=True, timeout=20)
        assert r.returncode == 0, \
            f"`python3 -m solution FILE` exited {r.returncode}, stderr={r.stderr!r}"
        assert [json.loads(x) for x in r.stdout.splitlines()] == [{"a": "1", "b": "2"}], \
            f"stdout was {r.stdout!r}"
        assert r.stderr == "", f"stderr must be empty on success, was {r.stderr!r}"
