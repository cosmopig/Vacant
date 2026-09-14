"""Visible check 2: a title that is already a clean slug is left alone."""


def run(solution):
    titles = ["already-a-slug", "another-one", "third-thing"]
    got = solution.slugify(titles)
    assert got == titles, "args=%r got=%r want=%r" % (titles, got, titles)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_already_a_slug")
