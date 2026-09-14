"""ow_01_csvjson — 隱藏驗收，14 條。**永遠不進工作區。**

每一條都要指得回 `goal.md` 或 `contract.md` 的某一句（§五-2 的公平性複核），
對照表在 `ops/gain/r530/hidden/ow_01_csvjson/ANCHORS.md`。

⚠ 這個檔案在驗收的那一瞬間被複製到 run 目錄底下的暫存目錄、以唯讀綁進沙箱、
  跑完立刻刪掉。工作區在整個過程中不會被寫入任何一個位元組
  （`openwork_arms.run_cell` 有一條硬斷言在驗收前後比樹雜湊）。
"""
import json
import os
import subprocess
import sys
import tempfile

import solution


def _rows(text):
    out = solution.csv_to_jsonl(text)
    assert isinstance(out, str), f"csv_to_jsonl must return str, got {type(out).__name__}"
    if out == "":
        return []
    assert out.endswith("\n"), f"every line must end with a newline: {out!r}"
    return [json.loads(line) for line in out.splitlines()]


def check_quoted_comma():
    text = 'a,b\n"x,y",z\n'
    assert _rows(text) == [{"a": "x,y", "b": "z"}], \
        f"a quoted field may contain a comma: got {solution.csv_to_jsonl(text)!r}"


def check_quoted_newline():
    text = 'a,b\n"line1\nline2",z\n'
    assert _rows(text) == [{"a": "line1\nline2", "b": "z"}], \
        f"a quoted field may contain a line break: got {solution.csv_to_jsonl(text)!r}"


def check_escaped_quote():
    text = 'a\n"he said ""hi"""\n'
    assert _rows(text) == [{"a": 'he said "hi"'}], \
        f'"" inside a quoted field is one literal quote: got {solution.csv_to_jsonl(text)!r}'


def check_crlf():
    text = "a,b\r\n1,2\r\n"
    assert _rows(text) == [{"a": "1", "b": "2"}], \
        f"CRLF ends a record: got {solution.csv_to_jsonl(text)!r}"


def check_empty_input():
    assert solution.csv_to_jsonl("") == "", \
        "input with no records returns the empty string"


def check_header_only():
    assert solution.csv_to_jsonl("a,b\n") == "", \
        "input with only a header returns the empty string"


def check_duplicate_header_last_wins():
    text = "a,a\n1,2\n"
    rows = _rows(text)
    assert len(rows) == 1 and rows[0].get("a") == "2", \
        f"when the header repeats a name the last column wins: got {rows!r}"


def check_field_count_mismatch_line_number():
    text = "a,b\n1,2\n3\n"
    try:
        solution.csv_to_jsonl(text)
    except ValueError as e:
        msg = str(e)
    else:
        raise AssertionError("a record with the wrong number of fields must raise ValueError")
    assert msg.startswith("line 3:"), \
        f'str(exc) must start with "line 3:" for {text!r}, got {msg!r}'
    assert "\n" not in msg and len(msg) > len("line 3:"), \
        f"the message must be one non-empty line, got {msg!r}"


def check_unclosed_quote_raises():
    text = 'a,b\n"never closed,2\n'
    try:
        solution.csv_to_jsonl(text)
    except ValueError as e:
        msg = str(e)
    else:
        raise AssertionError("an unclosed quoted field must raise ValueError")
    assert msg.startswith("line 2:"), \
        f'str(exc) must start with "line 2:", got {msg!r}'


def check_cli_invalid_exit_2_one_line():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "bad.csv")
        with open(p, "w", encoding="utf-8") as f:
            f.write("a,b\n1\n")
        r = subprocess.run([sys.executable, "-m", "solution", p],
                           capture_output=True, text=True, timeout=20)
    assert r.returncode == 2, f"invalid input must exit 2, got {r.returncode}"
    lines = [x for x in r.stderr.splitlines() if x.strip()]
    assert len(lines) == 1, f"stderr must be exactly one line, got {r.stderr!r}"
    assert lines[0].startswith("line 2:"), \
        f'stderr must start with "line 2:", got {lines[0]!r}'


def check_cli_stdout_only_jsonl():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "ok.csv")
        with open(p, "w", encoding="utf-8") as f:
            f.write("a,b\n1,2\n3,4\n")
        r = subprocess.run([sys.executable, "-m", "solution", p],
                           capture_output=True, text=True, timeout=20)
    assert r.returncode == 0, f"exit code was {r.returncode}, stderr={r.stderr!r}"
    lines = r.stdout.splitlines()
    assert len(lines) == 2, \
        f"stdout must hold exactly one JSON object per data row, got {r.stdout!r}"
    for line in lines:
        json.loads(line)


def check_utf8_non_ascii():
    text = "名前,備考\n愛だ,ok\n"
    assert _rows(text) == [{"名前": "愛だ", "備考": "ok"}], \
        f"non-ASCII text must survive: got {solution.csv_to_jsonl(text)!r}"


def check_no_trailing_newline_input():
    text = "a,b\n1,2"
    assert _rows(text) == [{"a": "1", "b": "2"}], \
        f"a last record without a trailing newline still counts: " \
        f"got {solution.csv_to_jsonl(text)!r}"


def check_all_empty_fields_row():
    text = "a,b,c\n,,\n"
    assert _rows(text) == [{"a": "", "b": "", "c": ""}], \
        f"a row of blank fields is three empty strings: " \
        f"got {solution.csv_to_jsonl(text)!r}"
