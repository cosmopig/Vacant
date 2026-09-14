# anchor_kind: goal
# anchor: they can ask what was found in a line so a dashboard can count it, and a
# line with nothing in it answers with nothing
# derivation: a line holding three secrets reports three, a line holding one reports
# one, and a clean line reports none.


def run(solution):
    clean = "2026-09-13 INFO nothing to see"
    assert solution.findings(clean) == [], (
        "args=%r got=%r want=%r" % (clean, solution.findings(clean), []))

    one = "key AKIAP0O9I8U7Y6T5R4E3 only"
    assert len(solution.findings(one)) == 1, (
        "args=%r got=%r want=%r" % (one, solution.findings(one), "one finding"))

    three = ("AKIAP0O9I8U7Y6T5R4E3 then Authorization: Bearer aa.bb.cc "
             "then redis://user:pw@cache:6379/0")
    assert len(solution.findings(three)) == 3, (
        "args=%r got=%r want=%r" % (three, solution.findings(three), "three findings"))
