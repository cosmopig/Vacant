"""Known-bad B: numbers right, pre-releases and specs sloppy.

The three numbers are compared numerically and a pre-release does count as older,
but the pre-release itself is compared as one string, spaces around a condition
are left attached to the version, and nothing is ever rejected.
"""

OPERATORS = (">=", "<=", "==", "!=", ">", "<")


def _split(text):
    body, _, pre = text.partition("-")
    numbers = tuple(int(piece) for piece in body.split("."))
    return numbers, pre


def compare(a, b):
    numbers_a, pre_a = _split(a)
    numbers_b, pre_b = _split(b)
    if numbers_a != numbers_b:
        return -1 if numbers_a < numbers_b else 1
    if pre_a == pre_b:
        return 0
    if not pre_a:
        return 1
    if not pre_b:
        return -1
    return -1 if pre_a < pre_b else 1


def satisfies(version, spec):
    for condition in spec.split(","):
        for operator in OPERATORS:
            if condition.startswith(operator):
                target = condition[len(operator):]
                break
        else:
            return False
        result = compare(version, target)
        if operator == ">" and result != 1:
            return False
        if operator == ">=" and result == -1:
            return False
        if operator == "<" and result != -1:
            return False
        if operator == "<=" and result == 1:
            return False
        if operator == "==" and result != 0:
            return False
        if operator == "!=" and result == 0:
            return False
    return True
