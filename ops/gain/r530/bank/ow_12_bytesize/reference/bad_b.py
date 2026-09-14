"""Known-bad B: the bases are right, the edges are not.

Both unit families step correctly and the fraction is dropped, but the unit table
is case-sensitive, the printed number loses a trailing zero, a size below one step
is still printed with a decimal, and a negative size is accepted.
"""

import re

SIZE = re.compile(r"^(-?\d+(?:\.\d+)?)\s*([A-Za-z]*)$")

BINARY_UNITS = ("B", "KiB", "MiB", "GiB", "TiB")
DECIMAL_UNITS = ("B", "KB", "MB", "GB", "TB")

STEPS = {"B": 1, "KiB": 1024, "MiB": 1024 ** 2, "GiB": 1024 ** 3, "TiB": 1024 ** 4,
         "KB": 1000, "MB": 1000 ** 2, "GB": 1000 ** 3, "TB": 1000 ** 4}


def to_bytes(s):
    found = SIZE.match(s.strip())
    if not found:
        raise ValueError("bad size")
    amount, unit = found.groups()
    if unit and unit not in STEPS:
        raise ValueError("bad unit")
    return int(float(amount) * STEPS.get(unit or "B", 1))


def humanize(n, *, binary=True):
    units = BINARY_UNITS if binary else DECIMAL_UNITS
    step = 1024 if binary else 1000
    value = float(n)
    index = 0
    while value >= step and index < len(units) - 1:
        value /= step
        index += 1
    return "%g %s" % (value, units[index])
