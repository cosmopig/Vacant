# anchor_kind: goal
# anchor: after the pass, none of the secret text is anywhere in the result
# derivation: each of the three kinds the client showed, in a fresh instance, is
# absent from the redacted line.


def run(solution):
    cases = [("upload key AKIAZ9Y8X7W6V5U4T3S2 ok", "AKIAZ9Y8X7W6V5U4T3S2"),
             ("GET /v1 Authorization: Bearer abc.DEF-123_ghi done",
              "abc.DEF-123_ghi"),
             ("dsn=mysql://root:s3cr3tpw@10.0.0.4:3306/app", "s3cr3tpw")]
    for line, secret in cases:
        got = solution.redact(line)
        assert secret not in got, "args=%r got=%r want=%r" % (line, got, "%r removed" % secret)
