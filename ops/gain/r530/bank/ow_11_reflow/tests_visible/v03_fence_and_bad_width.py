"""Visible check 3: fenced code is left alone; a nonsense width is refused."""


def run(solution):
    text = "note\n\n```\nthis fenced line is far longer than the width given here\n```\n"
    got = solution.reflow(text, 12)
    assert "this fenced line is far longer than the width given here" in got, (
        "args=%r got=%r want=%r" % (text, got, "the fenced line unchanged"))

    for width in (0, -5):
        try:
            solution.reflow("hello", width)
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (width, "wrapped", "ValueError"))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v03_fence_and_bad_width")
