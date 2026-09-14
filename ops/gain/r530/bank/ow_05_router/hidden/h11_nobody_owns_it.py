# anchor_kind: goal
# anchor: A path that belongs to nobody
# derivation: with routes registered but none fitting, the answer is None rather
# than an exception or an empty tuple.


def run(solution):
    router = solution.Router()
    router.add("/a/{x}", "a")
    router.add("/b/c", "bc")
    for path in ("/", "/a", "/b", "/a/x/y", "/zzz"):
        got = router.match(path)
        assert got is None, "args=%r got=%r want=%r" % (path, got, None)
