"""Known-bad B: depth-first with a visited set and no circle check.

The visited set stops it looping, which is exactly why the circle goes unnoticed:
the traversal finishes and returns an order that cannot actually be run.
"""


def plan(jobs):
    ordered = []
    seen = set()

    def visit(name):
        if name in seen:
            return
        seen.add(name)
        for need in jobs.get(name, []):
            visit(need)
        ordered.append(name)

    for name in jobs:
        visit(name)
    return ordered
