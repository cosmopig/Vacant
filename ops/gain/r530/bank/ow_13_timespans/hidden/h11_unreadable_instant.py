# anchor_kind: contract
# anchor: and so does an instant that is not one of the two written forms
# derivation: anything that is not one of the two shapes raises, including a shape
# that is close but not right.


def run(solution):
    for text in ("2026-9-2", "02/09/2026", "2026-09-02 10:00:00", "2026-09-02T10:00",
                 "not a date", ""):
        try:
            solution.merge([(text, "2026-09-03")])
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (text, "accepted", "ValueError"))
