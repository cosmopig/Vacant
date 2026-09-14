# anchor_kind: contract
# anchor: the first position at which they differ picks the winner
# derivation: at the first segment one pattern has a literal and the other a
# rest-of-path capture, so the literal one wins however long the path is.


def run(solution):
    router = solution.Router()
    router.add("/{anything:*}", "fallback")
    router.add("/media/{rest:*}", "media")
    got = router.match("/media/img/logo/small.png")
    want = ("media", {"rest": "img/logo/small.png"})
    assert got == want, "args=%r got=%r want=%r" % ("/media/img/logo/small.png", got, want)
    got = router.match("/other/thing")
    want = ("fallback", {"anything": "other/thing"})
    assert got == want, "args=%r got=%r want=%r" % ("/other/thing", got, want)
