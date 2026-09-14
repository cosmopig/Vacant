# anchor_kind: goal
# anchor: pulling out the named pieces of the path along the way
# derivation: every parameter in the pattern appears in the returned mapping, under
# its own name, holding exactly the text of its segment.


def run(solution):
    router = solution.Router()
    router.add("/{tenant}/repos/{owner}/{repo}/issues/{number}", "issue")
    got = router.match("/acme/repos/bob/tools/issues/318")
    want = ("issue", {"tenant": "acme", "owner": "bob", "repo": "tools", "number": "318"})
    assert got == want, "args=%r got=%r want=%r" % ("/acme/repos/bob/tools/issues/318", got, want)
