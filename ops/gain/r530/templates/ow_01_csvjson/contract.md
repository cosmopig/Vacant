# Contract

Put your work in `solution.py` (or a package directory `solution/`) in this
directory. Nothing else is imported.

## Library interface

`solution.csv_to_jsonl(text: str) -> str`

- Returns JSON Lines: one JSON object per data row, each line ending with `\n`
  (including the last one).
- The first record of the input is the header.
- Every value is a string. A field left blank is `""`.
- If the header repeats a name, the **last** column with that name wins.
- Quoting follows the usual CSV rules: a field may be wrapped in `"`, a wrapped
  field may contain `,`, `\n` and `\r\n`, and `""` inside a wrapped field means
  one literal `"`.
- Line endings `\n`, `\r\n` and `\r` all end a record.
- Input with no records at all, and input with only a header, both return `""`.

## Errors

Input is invalid when a record has a different number of fields from the header,
or when a quoted field is never closed.

On invalid input `csv_to_jsonl` raises `ValueError`, and `str(exc)` is **exactly**

```
line <N>: <reason>
```

`<N>` is the 1-based line number in the input where the offending record starts.
`<reason>` is your own short text and is not checked, but it must not be empty
and must not contain a newline.

## Command line

`python3 -m solution FILE`

- On success: the JSON Lines go to stdout, nothing goes to stderr, exit code 0.
- On invalid input: **exactly one line** `line <N>: <reason>` goes to stderr,
  stdout is empty, exit code 2.
- The file is read as UTF-8.
