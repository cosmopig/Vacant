# anchor_kind: goal
# anchor: the answer must not depend on that order
# derivation: every permutation of the same three routes must answer the same way
# for the same path.

import itertools


def run(solution):
    routes = [("/p/{id}", "one"), ("/p/latest", "latest"), ("/p/{rest:*}", "tree")]
    answers = []
    for order in itertools.permutations(routes):
        router = solution.Router()
        for pattern, name in order:
            router.add(pattern, name)
        answers.append((router.match("/p/latest"), router.match("/p/9"), router.match("/p/a/b")))
    distinct = sorted(set(repr(answer) for answer in answers))
    assert len(distinct) == 1, "args=%r got=%r want=%r" % (
        "six registration orders", distinct, "one answer for all six")
    got = answers[0]
    want = (("latest", {}), ("one", {"id": "9"}), ("tree", {"rest": "a/b"}))
    assert got == want, "args=%r got=%r want=%r" % ("six registration orders", got, want)
