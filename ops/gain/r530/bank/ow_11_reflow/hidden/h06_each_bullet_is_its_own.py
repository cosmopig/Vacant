# anchor_kind: goal
# anchor: Each bullet in a list is its own thought and must not be glued onto the
# one above it.
# derivation: three short bullets on three lines come back as three bullets, not as
# one filled paragraph.


def run(solution):
    text = "- one\n- two\n- three\n"
    got = solution.reflow(text, 60)
    lines = got.rstrip("\n").split("\n")
    assert lines == ["- one", "- two", "- three"], (
        "args=%r got=%r want=%r" % (text, lines, ["- one", "- two", "- three"]))
