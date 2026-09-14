# Contract

## Library

    solution.csv_to_jsonl(text: str) -> str

- Returns JSON Lines: one JSON object per data row, each object on its own line,
  every line terminated by a newline, so the returned string ends with a newline.
- The first record of the input is the header. Every value in every object is a
  string. A field that is empty becomes `""`.
- When a header name repeats, the last occurrence wins.
- Quoting is the usual CSV convention: a field may be wrapped in double quotes;
  inside such a field a doubled `""` stands for one literal double quote, and
  commas and line breaks are ordinary characters.
- `"\n"` and `"\r\n"` are both accepted as line endings and neither survives into
  a parsed value.
- The input may or may not end with a final newline; that makes no difference to
  the output. A completely empty line is ignored.
- When there are no data rows the result is the empty string.
- Invalid input raises `ValueError` whose message starts with `line <N>: `, where
  `N` is the 1-based line number on which the offending record starts and the
  header is line 1. Invalid means: a record whose field count differs from the
  header, or an unclosed quote.

## Command line

    python -m solution FILE

- The file is read as UTF-8.
- On success the JSON Lines go to stdout and the exit code is 0. Nothing else is
  written to stdout.
- On invalid input exactly one line `line <N>: <reason>` is written to stderr and
  the exit code is 2. Nothing is written to stdout.
