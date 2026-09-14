# anchor_kind: goal
# anchor: they want a mistake in a pattern to be reported when the route is
# registered rather than on the first request that hits it
# derivation: every malformed shape raises from add, before any path is matched.


def run(solution):
    router = solution.Router()
    for pattern in ("users/{id}", "/users/{}", "/users/{id", "/users/id}", "/a/{b:*}/c"):
        try:
            router.add(pattern, "x")
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (pattern, "no error", "ValueError"))
