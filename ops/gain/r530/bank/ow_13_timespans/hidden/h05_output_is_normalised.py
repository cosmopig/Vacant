# anchor_kind: contract
# anchor: Every instant in a returned span is written `YYYY-MM-DDTHH:MM:SS`.
# derivation: whatever form went in, what comes out is the long form, for merge and
# for subtract alike.

import re

SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


def run(solution):
    spans = [("2026-05-01", "2026-05-03")]
    holes = [("2026-05-02", "2026-05-02T12:00:00")]
    for produced in (solution.merge(spans), solution.subtract(spans, holes)):
        for start, end in produced:
            assert SHAPE.match(start) and SHAPE.match(end), (
                "args=%r got=%r want=%r" % (spans, (start, end), "YYYY-MM-DDTHH:MM:SS"))
