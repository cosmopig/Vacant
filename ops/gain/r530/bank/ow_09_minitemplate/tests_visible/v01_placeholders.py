"""Visible check 1: plain and nested placeholders, values turned into text."""


def run(solution):
    template = "Hi {{user.name}}, you have {{count}} messages."
    data = {"user": {"name": "Ann"}, "count": 3}
    got = solution.render(template, data)
    want = "Hi Ann, you have 3 messages."
    assert got == want, "args=%r got=%r want=%r" % ((template, data), got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_placeholders")
