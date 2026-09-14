"""Known-bad C: the skeleton. Every name exists, almost nothing happens."""
def to_bytes(s):
    return int(float("".join(ch for ch in s if ch.isdigit() or ch == ".") or 0))


def humanize(n, *, binary=True):
    return "%d B" % n
