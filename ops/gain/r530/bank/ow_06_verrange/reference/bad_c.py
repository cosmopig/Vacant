"""Known-bad C: the skeleton. Every name exists, almost nothing happens."""
def compare(a, b):
    if a == b:
        return 0
    return -1 if a < b else 1


def satisfies(version, spec):
    return True
