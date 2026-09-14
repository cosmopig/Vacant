# Contract

    solution.merge(spans: list[tuple[str, str]]) -> list[tuple[str, str]]
    solution.subtract(spans: list[tuple[str, str]],
                      holes: list[tuple[str, str]]) -> list[tuple[str, str]]
    solution.total_seconds(spans: list[tuple[str, str]]) -> int

- An instant is written `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS`. A date on its own
  means midnight at the start of that day.
- A span is the pair `(start, end)` and covers the instants from `start` up to but
  not including `end`.
- `merge` returns the union of the spans as the shortest list that covers it,
  ordered by start. Spans that overlap or that touch end to end become one. A span
  whose start equals its end covers nothing and is dropped.
- `subtract` returns the union of `spans` with every instant covered by `holes`
  removed, in that same shortest form.
- `total_seconds` returns the number of whole seconds covered by the union, as an
  `int`.
- Every instant in a returned span is written `YYYY-MM-DDTHH:MM:SS`.
- A span whose end is earlier than its start raises `ValueError`, and so does an
  instant that is not one of the two written forms.
