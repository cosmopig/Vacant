"""Visible check 3: what cannot be read is refused."""


def run(solution):
    for text in ("", "   ", "banana", "4 KBs", "1.2.3 MB"):
        try:
            solution.to_bytes(text)
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (text, "a number", "ValueError"))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v03_refuses_nonsense")
