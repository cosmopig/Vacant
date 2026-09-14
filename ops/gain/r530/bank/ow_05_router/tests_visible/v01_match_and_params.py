"""Visible check 1: a path finds its pattern and hands back the named pieces."""


def run(solution):
    router = solution.Router()
    router.add("/users/{id}/posts/{slug}", "user_post")
    got = router.match("/users/42/posts/hello")
    want = ("user_post", {"id": "42", "slug": "hello"})
    assert got == want, "args=%r got=%r want=%r" % ("/users/42/posts/hello", got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_match_and_params")
