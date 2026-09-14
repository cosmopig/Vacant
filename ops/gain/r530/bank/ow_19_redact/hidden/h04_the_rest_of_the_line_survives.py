# anchor_kind: goal
# anchor: because a person is going to read the line and needs the rest of it
# derivation: after a secret is taken out, every other word of the line is still
# there, and the line has not been replaced wholesale.


def run(solution):
    line = "2026-09-13 ERROR worker-7 could not reach postgres://svc:hunter9@db:5432/app retrying"
    got = solution.redact(line)
    for word in ("2026-09-13", "ERROR", "worker-7", "could", "not", "reach",
                 "retrying", "db", "5432", "app"):
        assert word in got, "args=%r got=%r want=%r" % (line, got, "the word %r kept" % word)
    assert "hunter9" not in got, "args=%r got=%r want=%r" % (line, got, "the password removed")
