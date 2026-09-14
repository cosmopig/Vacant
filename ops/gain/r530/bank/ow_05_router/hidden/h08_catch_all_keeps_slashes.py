# anchor_kind: goal
# anchor: a pattern that swallows the rest of the path for serving files
# derivation: the captured remainder keeps its slashes, so a nested file path comes
# back whole.


def run(solution):
    router = solution.Router()
    router.add("/files/{path:*}", "serve")
    got = router.match("/files/a/b/c/d.txt")
    want = ("serve", {"path": "a/b/c/d.txt"})
    assert got == want, "args=%r got=%r want=%r" % ("/files/a/b/c/d.txt", got, want)
