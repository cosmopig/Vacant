# anchor_kind: contract
# anchor: must not be empty
# derivation: the rest-of-path capture needs at least one character, so the bare
# prefix does not match and neither does the prefix with a trailing slash.


def run(solution):
    router = solution.Router()
    router.add("/dl/{path:*}", "download")
    for path in ("/dl", "/dl/"):
        got = router.match(path)
        assert got is None, "args=%r got=%r want=%r" % (path, got, None)
