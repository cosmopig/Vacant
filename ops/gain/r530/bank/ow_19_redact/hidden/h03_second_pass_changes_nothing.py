# anchor_kind: goal
# anchor: running the pass on a line that has already been through it changes
# nothing further
# derivation: for each kind, redacting twice gives the same result as redacting
# once, and a third pass still gives the same.


def run(solution):
    for line in ("key AKIAQ1W2E3R4T5Y6U7I8 here",
                 "Authorization: Bearer zzz.yyy.xxx",
                 "amqp://user:letmein@rabbit:5672/",
                 "two AKIAQ1W2E3R4T5Y6U7I8 and amqp://u:pw@h:1/ together"):
        once = solution.redact(line)
        twice = solution.redact(once)
        thrice = solution.redact(twice)
        assert once == twice == thrice, (
            "args=%r got=%r want=%r" % (line, (twice, thrice), once))
