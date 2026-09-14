# anchor_kind: contract
# anchor: compare the two patterns segment by segment from the left: the first
# position at which they differ picks the winner
# derivation: both patterns have one literal and one parameter, so a rule that
# counts literals cannot separate them; only the leftmost difference can.


def run(solution):
    router = solution.Router()
    router.add("/{owner}/settings", "user_settings")
    router.add("/admin/{page}", "admin_page")
    got = router.match("/admin/settings")
    assert got == ("admin_page", {"page": "settings"}), (
        "args=%r got=%r want=%r" % ("/admin/settings", got, ("admin_page", {"page": "settings"})))
