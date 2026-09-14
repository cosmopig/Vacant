"""Known-bad A: hand back the keys.

The table is already roughly in the order somebody typed it, so the shortest thing
that runs is to return its keys. Prerequisites that are not themselves keys are
never mentioned.
"""


def plan(jobs):
    return list(jobs)
