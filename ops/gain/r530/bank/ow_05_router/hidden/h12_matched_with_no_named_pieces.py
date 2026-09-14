# anchor_kind: goal
# anchor: has to be distinguishable from a path that matched with no named pieces
# derivation: an all-literal pattern returns an empty mapping, which must not be
# confused with no match at all.


def run(solution):
    router = solution.Router()
    router.add("/health/live", "liveness")
    got = router.match("/health/live")
    assert got is not None, "args=%r got=%r want=%r" % ("/health/live", got, "a match")
    assert got == ("liveness", {}), (
        "args=%r got=%r want=%r" % ("/health/live", got, ("liveness", {})))
