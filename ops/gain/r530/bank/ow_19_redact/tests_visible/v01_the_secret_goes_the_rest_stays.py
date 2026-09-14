"""Visible check 1: the key is gone and the line is still readable."""


def run(solution):
    line = "2026-09-13 WARN starting upload with AKIAIOSFODNN7EXAMPLE to bucket logs"
    got = solution.redact(line)
    assert "AKIAIOSFODNN7EXAMPLE" not in got, (
        "args=%r got=%r want=%r" % (line, got, "the key removed"))
    for word in ("2026-09-13", "WARN", "starting", "upload", "bucket", "logs"):
        assert word in got, "args=%r got=%r want=%r" % (line, got, "the word %r kept" % word)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_the_secret_goes_the_rest_stays")
