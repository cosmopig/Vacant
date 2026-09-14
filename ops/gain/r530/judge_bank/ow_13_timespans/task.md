# Goal

A client runs a booking calendar for a shared resource. Busy periods arrive from
several systems and they need them folded into one tidy list of when the resource
is actually busy, plus a way to work out what is left once certain periods are
taken out of it.

The periods arrive in no particular order and they overlap. Some of them touch end
to end, and two bookings where one ends exactly when the next begins are one busy
stretch, not two. A period with no length is not a period at all.

Some systems send a date only and some send a time of day as well, and both have
to be understood. A period that ends before it starts is a bug in whoever sent it
and has to be reported rather than quietly reversed.

They also want the total, in whole seconds, of the tidy list, counting time that
two systems both reported only once.

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
