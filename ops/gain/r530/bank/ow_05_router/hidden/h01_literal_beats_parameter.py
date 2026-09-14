# anchor_kind: goal
# anchor: they want the same answer every time -- the more specific one
# derivation: a literal segment is more specific than a named one at the same
# position, so the literal route answers.


def run(solution):
    router = solution.Router()
    router.add("/orders/{ref}", "one_order")
    router.add("/orders/export", "export_orders")
    got = router.match("/orders/export")
    assert got == ("export_orders", {}), (
        "args=%r got=%r want=%r" % ("/orders/export", got, ("export_orders", {})))
