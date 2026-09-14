# Contract

## Library

    solution.summarize(lines: Iterable[str]) -> dict

A log line is `<ISO8601> <METHOD> <PATH> <STATUS> <MS>`, the five fields separated
by one space each. Any trailing newline is not part of the line.

The result has exactly this shape:

    {"endpoints": [{"path": str, "n": int, "error_rate": float,
                    "p50_ms": int, "p95_ms": int}, ...],
     "bad_lines": int, "total": int}

- `error_rate` is the share of that endpoint's requests whose status is 500 or
  more, rounded to four decimal places.
- Percentiles are nearest-rank: the p-th percentile of n sorted values is the one
  at 1-based position `ceil(p / 100 * n)`.
- `endpoints` is ordered by `n` from large to small, and endpoints with the same
  `n` are ordered by `path` in ordinary string order.
- A line is bad when it does not have exactly five fields, when `STATUS` or `MS` is
  not a run of digits with an optional leading `-`, or when the timestamp is not
  ISO8601. A timestamp counts as ISO8601 when
  `datetime.datetime.fromisoformat` accepts it, after a trailing `Z` has been
  replaced by `+00:00`.
- `total` counts every line that was looked at, good and bad together. A line that
  is empty or only whitespace is not looked at: it is neither good nor bad and is
  not in `total`.
- `bad_lines` counts the bad ones. A bad line never stops the run.

## Command line

    python -m solution FILE

Reads that file and writes to stdout the same result `summarize` returns, as one
JSON object, then exits 0. How that JSON is laid out -- indenting, key order,
spacing, trailing newline -- is not checked, only that stdout holds that one object
and that it carries the same numbers the library call would have given.

Bad lines in the file are not a reason for the command to fail: it counts them the
way the library does and still exits 0.
