"""ow_19_redact — hidden checks, 6. **Never enters a workspace.**

Generated from bank/ow_19_redact/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_all_three_kinds_go():
    # anchor_kind: goal
    # anchor: after the pass, none of the secret text is anywhere in the result
    # derivation: each of the three kinds the client showed, in a fresh instance, is
    # absent from the redacted line.


    def _bank_entry(solution):
        cases = [("upload key AKIAZ9Y8X7W6V5U4T3S2 ok", "AKIAZ9Y8X7W6V5U4T3S2"),
                 ("GET /v1 Authorization: Bearer abc.DEF-123_ghi done",
                  "abc.DEF-123_ghi"),
                 ("dsn=mysql://root:s3cr3tpw@10.0.0.4:3306/app", "s3cr3tpw")]
        for line, secret in cases:
            got = solution.redact(line)
            assert secret not in got, "args=%r got=%r want=%r" % (line, got, "%r removed" % secret)
    _bank_entry(solution)


def check_h02_ordinary_lines_untouched():
    # anchor_kind: goal
    # anchor: everything in the line that is not a secret comes back exactly as it was
    # derivation: lines with no secret in them, including ones that merely look
    # secret-ish, come back byte for byte.


    def _bank_entry(solution):
        for line in ("2026-09-13 ERROR timeout after 30s talking to db.internal",
                     "user bob@example.com signed in from 10.0.0.4",
                     "fetched https://example.com/a/b?c=d in 12ms",
                     "AKIA is a prefix, AKIASHORT is not a key",
                     ""):
            got = solution.redact(line)
            assert got == line, "args=%r got=%r want=%r" % (line, got, line)
    _bank_entry(solution)


def check_h03_second_pass_changes_nothing():
    # anchor_kind: goal
    # anchor: running the pass on a line that has already been through it changes
    # nothing further
    # derivation: for each kind, redacting twice gives the same result as redacting
    # once, and a third pass still gives the same.


    def _bank_entry(solution):
        for line in ("key AKIAQ1W2E3R4T5Y6U7I8 here",
                     "Authorization: Bearer zzz.yyy.xxx",
                     "amqp://user:letmein@rabbit:5672/",
                     "two AKIAQ1W2E3R4T5Y6U7I8 and amqp://u:pw@h:1/ together"):
            once = solution.redact(line)
            twice = solution.redact(once)
            thrice = solution.redact(twice)
            assert once == twice == thrice, (
                "args=%r got=%r want=%r" % (line, (twice, thrice), once))
    _bank_entry(solution)


def check_h04_the_rest_of_the_line_survives():
    # anchor_kind: goal
    # anchor: because a person is going to read the line and needs the rest of it
    # derivation: after a secret is taken out, every other word of the line is still
    # there, and the line has not been replaced wholesale.


    def _bank_entry(solution):
        line = "2026-09-13 ERROR worker-7 could not reach postgres://svc:hunter9@db:5432/app retrying"
        got = solution.redact(line)
        for word in ("2026-09-13", "ERROR", "worker-7", "could", "not", "reach",
                     "retrying", "db", "5432", "app"):
            assert word in got, "args=%r got=%r want=%r" % (line, got, "the word %r kept" % word)
        assert "hunter9" not in got, "args=%r got=%r want=%r" % (line, got, "the password removed")
    _bank_entry(solution)


def check_h05_repeats_both_go():
    # anchor_kind: goal
    # anchor: a secret that appears twice in one line is gone both times
    # derivation: the same secret written twice in one line leaves no trace of either
    # occurrence.


    def _bank_entry(solution):
        key = "AKIAM1N2B3V4C5X6Z7A8"
        line = "rotating %s to %s now" % (key, key)
        got = solution.redact(line)
        assert key not in got, "args=%r got=%r want=%r" % (line, got, "both copies removed")

        line = "a Authorization: Bearer tok-one b and c mongodb://u:pw-two@h:1/d e"
        got = solution.redact(line)
        assert "tok-one" not in got and "pw-two" not in got, (
            "args=%r got=%r want=%r" % (line, got, "both secrets removed"))
    _bank_entry(solution)


def check_h06_the_count_is_usable():
    # anchor_kind: goal
    # anchor: they can ask what was found in a line so a dashboard can count it, and a
    # line with nothing in it answers with nothing
    # derivation: a line holding three secrets reports three, a line holding one reports
    # one, and a clean line reports none.


    def _bank_entry(solution):
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
    _bank_entry(solution)
