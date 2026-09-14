"""ow_13_timespans — hidden checks, 13. **Never enters a workspace.**

Generated from bank/ow_13_timespans/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_touching_spans_join():
    # anchor_kind: goal
    # anchor: two bookings where one ends exactly when the next begins are one busy
    # stretch, not two
    # derivation: the end instant is not covered, so there is no gap between the two and
    # they come back as a single span.


    def _bank_entry(solution):
        spans = [("2026-01-01T09:00:00", "2026-01-01T10:00:00"),
                 ("2026-01-01T10:00:00", "2026-01-01T11:00:00")]
        got = solution.merge(spans)
        want = [("2026-01-01T09:00:00", "2026-01-01T11:00:00")]
        assert got == want, "args=%r got=%r want=%r" % (spans, got, want)
    _bank_entry(solution)


def check_h02_unordered_input():
    # anchor_kind: goal
    # anchor: The periods arrive in no particular order
    # derivation: the same set of periods handed over in a different order gives the
    # same tidy list, sorted by when each stretch starts.


    def _bank_entry(solution):
        spans = [("2026-01-05", "2026-01-06"), ("2026-01-01", "2026-01-02"),
                 ("2026-01-03", "2026-01-04")]
        got = solution.merge(spans)
        want = [("2026-01-01T00:00:00", "2026-01-02T00:00:00"),
                ("2026-01-03T00:00:00", "2026-01-04T00:00:00"),
                ("2026-01-05T00:00:00", "2026-01-06T00:00:00")]
        assert got == want, "args=%r got=%r want=%r" % (spans, got, want)
        assert solution.merge(list(reversed(spans))) == want, (
            "args=%r got=%r want=%r" % (list(reversed(spans)), solution.merge(list(reversed(spans))), want))
    _bank_entry(solution)


def check_h03_zero_length_dropped():
    # anchor_kind: goal
    # anchor: A period with no length is not a period at all.
    # derivation: a span whose start and end are the same covers nothing, so it neither
    # appears in the tidy list nor joins its neighbours together.


    def _bank_entry(solution):
        spans = [("2026-02-01T00:00:00", "2026-02-01T00:00:00"),
                 ("2026-02-01T05:00:00", "2026-02-01T06:00:00")]
        got = solution.merge(spans)
        want = [("2026-02-01T05:00:00", "2026-02-01T06:00:00")]
        assert got == want, "args=%r got=%r want=%r" % (spans, got, want)

        got = solution.merge([("2026-02-01", "2026-02-01")])
        assert got == [], "args=%r got=%r want=%r" % ([("2026-02-01", "2026-02-01")], got, [])
    _bank_entry(solution)


def check_h04_dates_are_midnight():
    # anchor_kind: goal
    # anchor: Some systems send a date only and some send a time of day as well
    # derivation: a date on its own is the midnight that starts that day, so it joins
    # with a timed span that runs up to that same midnight.


    def _bank_entry(solution):
        spans = [("2026-04-01", "2026-04-02"),
                 ("2026-04-02T00:00:00", "2026-04-02T06:00:00")]
        got = solution.merge(spans)
        want = [("2026-04-01T00:00:00", "2026-04-02T06:00:00")]
        assert got == want, "args=%r got=%r want=%r" % (spans, got, want)
        assert solution.total_seconds([("2026-04-01", "2026-04-02")]) == 86400, (
            "args=%r got=%r want=%r" % ("one whole day", solution.total_seconds([("2026-04-01", "2026-04-02")]), 86400))
    _bank_entry(solution)


def check_h05_output_is_normalised():
    # anchor_kind: contract
    # anchor: Every instant in a returned span is written `YYYY-MM-DDTHH:MM:SS`.
    # derivation: whatever form went in, what comes out is the long form, for merge and
    # for subtract alike.

    import re

    SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


    def _bank_entry(solution):
        spans = [("2026-05-01", "2026-05-03")]
        holes = [("2026-05-02", "2026-05-02T12:00:00")]
        for produced in (solution.merge(spans), solution.subtract(spans, holes)):
            for start, end in produced:
                assert SHAPE.match(start) and SHAPE.match(end), (
                    "args=%r got=%r want=%r" % (spans, (start, end), "YYYY-MM-DDTHH:MM:SS"))
    _bank_entry(solution)


def check_h06_hole_in_the_middle():
    # anchor_kind: goal
    # anchor: a way to work out what is left once certain periods are taken out of it
    # derivation: a hole strictly inside a busy stretch leaves two stretches, one on
    # each side of it.


    def _bank_entry(solution):
        spans = [("2026-06-01T08:00:00", "2026-06-01T18:00:00")]
        holes = [("2026-06-01T12:00:00", "2026-06-01T13:00:00")]
        got = solution.subtract(spans, holes)
        want = [("2026-06-01T08:00:00", "2026-06-01T12:00:00"),
                ("2026-06-01T13:00:00", "2026-06-01T18:00:00")]
        assert got == want, "args=%r got=%r want=%r" % ((spans, holes), got, want)
    _bank_entry(solution)


def check_h07_hole_swallows_everything():
    # anchor_kind: contract
    # anchor: `subtract` returns the union of `spans` with every instant covered by
    # `holes` removed
    # derivation: a hole that covers the whole stretch leaves nothing behind, and
    # several holes together can do the same.


    def _bank_entry(solution):
        spans = [("2026-06-01T08:00:00", "2026-06-01T10:00:00")]
        got = solution.subtract(spans, [("2026-06-01T07:00:00", "2026-06-01T11:00:00")])
        assert got == [], "args=%r got=%r want=%r" % (spans, got, [])

        holes = [("2026-06-01T08:00:00", "2026-06-01T09:00:00"),
                 ("2026-06-01T09:00:00", "2026-06-01T10:00:00")]
        got = solution.subtract(spans, holes)
        assert got == [], "args=%r got=%r want=%r" % ((spans, holes), got, [])
    _bank_entry(solution)


def check_h08_holes_that_miss():
    # anchor_kind: contract
    # anchor: `subtract` returns the union of `spans`
    # derivation: holes that fall entirely outside a stretch, or that only touch its
    # edge, take nothing away from it.


    def _bank_entry(solution):
        spans = [("2026-07-01T10:00:00", "2026-07-01T12:00:00")]
        holes = [("2026-07-01T08:00:00", "2026-07-01T10:00:00"),
                 ("2026-07-01T12:00:00", "2026-07-01T14:00:00"),
                 ("2026-07-02", "2026-07-03")]
        got = solution.subtract(spans, holes)
        want = [("2026-07-01T10:00:00", "2026-07-01T12:00:00")]
        assert got == want, "args=%r got=%r want=%r" % ((spans, holes), got, want)
    _bank_entry(solution)


def check_h09_total_counts_overlap_once():
    # anchor_kind: goal
    # anchor: counting time that two systems both reported only once
    # derivation: three heavily overlapping reports of the same hour total one hour,
    # not three.


    def _bank_entry(solution):
        spans = [("2026-08-01T09:00:00", "2026-08-01T10:00:00"),
                 ("2026-08-01T09:15:00", "2026-08-01T09:45:00"),
                 ("2026-08-01T09:00:00", "2026-08-01T10:00:00")]
        got = solution.total_seconds(spans)
        assert got == 3600, "args=%r got=%r want=%r" % (spans, got, 3600)
    _bank_entry(solution)


def check_h10_reversed_span_is_reported():
    # anchor_kind: goal
    # anchor: A period that ends before it starts is a bug in whoever sent it and has to
    # be reported rather than quietly reversed.
    # derivation: the reversed span raises from every entry point rather than being
    # swapped into a plausible booking.


    def _bank_entry(solution):
        bad = [("2026-09-02T10:00:00", "2026-09-02T09:00:00")]
        for call in (lambda: solution.merge(bad),
                     lambda: solution.total_seconds(bad),
                     lambda: solution.subtract(bad, []),
                     lambda: solution.subtract([("2026-09-02", "2026-09-03")], bad)):
            try:
                call()
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (bad, "accepted", "ValueError"))
    _bank_entry(solution)


def check_h11_unreadable_instant():
    # anchor_kind: contract
    # anchor: and so does an instant that is not one of the two written forms
    # derivation: anything that is not one of the two shapes raises, including a shape
    # that is close but not right.


    def _bank_entry(solution):
        for text in ("2026-9-2", "02/09/2026", "2026-09-02 10:00:00", "2026-09-02T10:00",
                     "not a date", ""):
            try:
                solution.merge([(text, "2026-09-03")])
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (text, "accepted", "ValueError"))
    _bank_entry(solution)


def check_h12_nothing_to_do():
    # anchor_kind: contract
    # anchor: `merge` returns the union of the spans as the shortest list that covers it
    # derivation: no spans means no stretches and a total of zero, and subtracting from
    # nothing is still nothing.


    def _bank_entry(solution):
        assert solution.merge([]) == [], "args=%r got=%r want=%r" % ([], solution.merge([]), [])
        assert solution.total_seconds([]) == 0, (
            "args=%r got=%r want=%r" % ([], solution.total_seconds([]), 0))
        assert solution.subtract([], [("2026-01-01", "2026-01-02")]) == [], (
            "args=%r got=%r want=%r" % ("empty spans", solution.subtract([], [("2026-01-01", "2026-01-02")]), []))
    _bank_entry(solution)


def check_h13_seconds_resolution():
    # anchor_kind: contract
    # anchor: `total_seconds` returns the number of whole seconds covered by the union,
    # as an `int`.
    # derivation: a one-second stretch is one second, and a stretch across a day
    # boundary is counted through it.


    def _bank_entry(solution):
        got = solution.total_seconds([("2026-01-01T00:00:00", "2026-01-01T00:00:01")])
        assert got == 1, "args=%r got=%r want=%r" % ("one second", got, 1)
        got = solution.total_seconds([("2026-01-01T23:59:00", "2026-01-02T00:01:00")])
        assert got == 120, "args=%r got=%r want=%r" % ("across midnight", got, 120)
    _bank_entry(solution)
