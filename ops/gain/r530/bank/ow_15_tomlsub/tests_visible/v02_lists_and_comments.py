"""Visible check 2: lists of one kind, and comments that are not settings."""


def run(solution):
    text = ("# the ports we listen on\nports = [80, 443, 8080]   # and nothing else\n"
            "\nnames = [\"a\", \"b\"]\nempty = []\n")
    got = solution.parse(text)
    want = {"ports": [80, 443, 8080], "names": ["a", "b"], "empty": []}
    assert got == want, "args=%r got=%r want=%r" % (text, got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_lists_and_comments")
