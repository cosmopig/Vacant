"""Visible check 3: pieces made for another version are refused."""


def run(solution):
    old = ["a", "b", "c"]
    new = ["a", "B", "c"]
    pieces = solution.diff(old, new)
    someone_else_edited = ["a", "x", "c"]
    try:
        solution.apply(someone_else_edited, pieces)
    except ValueError:
        return
    raise AssertionError("args=%r got=%r want=%r"
                         % (someone_else_edited, "patched anyway", "ValueError"))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v03_refuses_a_piece_that_does_not_fit")
