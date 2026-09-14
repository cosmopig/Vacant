# anchor_kind: goal
# anchor: everything in the line that is not a secret comes back exactly as it was
# derivation: lines with no secret in them, including ones that merely look
# secret-ish, come back byte for byte.


def run(solution):
    for line in ("2026-09-13 ERROR timeout after 30s talking to db.internal",
                 "user bob@example.com signed in from 10.0.0.4",
                 "fetched https://example.com/a/b?c=d in 12ms",
                 "AKIA is a prefix, AKIASHORT is not a key",
                 ""):
        got = solution.redact(line)
        assert got == line, "args=%r got=%r want=%r" % (line, got, line)
