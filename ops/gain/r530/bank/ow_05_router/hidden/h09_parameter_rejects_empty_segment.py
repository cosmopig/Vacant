# anchor_kind: contract
# anchor: `{name}` matches exactly one segment, never spans a `/`, and never matches
# an empty segment.
# derivation: a trailing slash leaves an empty segment, which a named segment must
# refuse rather than capture as "".


def run(solution):
    router = solution.Router()
    router.add("/tags/{tag}", "tag")
    got = router.match("/tags/")
    assert got is None, "args=%r got=%r want=%r" % ("/tags/", got, None)
