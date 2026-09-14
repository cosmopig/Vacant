"""Visible check 3: the rest-of-path pattern, and a path that belongs to nobody."""


def run(solution):
    router = solution.Router()
    router.add("/static/{rest:*}", "assets")
    got = router.match("/static/css/site/main.css")
    want = ("assets", {"rest": "css/site/main.css"})
    assert got == want, "args=%r got=%r want=%r" % ("/static/css/site/main.css", got, want)
    got = router.match("/nothing/here")
    assert got is None, "args=%r got=%r want=%r" % ("/nothing/here", got, None)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v03_catch_all_and_miss")
