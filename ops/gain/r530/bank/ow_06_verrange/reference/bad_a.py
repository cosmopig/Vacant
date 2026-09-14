"""Known-bad A: compares the strings.

The version is split on dots and the pieces are compared as text, which is exactly
how 1.10 ends up older than 1.9, and the pre-release suffix rides along inside the
last piece.
"""

OPERATORS = (">=", "<=", "==", "!=", ">", "<")


def compare(a, b):
    left = a.split(".")
    right = b.split(".")
    if left == right:
        return 0
    return -1 if left < right else 1


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
