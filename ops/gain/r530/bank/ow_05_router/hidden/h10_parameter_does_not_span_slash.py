# anchor_kind: contract
# anchor: never spans a `/`
# derivation: a two-segment tail cannot be swallowed by one named segment, so the
# deeper path does not match the shallower pattern.


def run(solution):
    router = solution.Router()
    router.add("/blog/{slug}", "post")
    got = router.match("/blog/2026/hello")
    assert got is None, "args=%r got=%r want=%r" % ("/blog/2026/hello", got, None)
