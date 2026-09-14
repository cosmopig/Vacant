"""Reference solution for ow_12_bytesize (gauge only; never enters a workspace)."""

import re

SIZE = re.compile(r"^(\d+(?:\.\d+)?)\s*([A-Za-z]*)$")

BINARY_UNITS = ("B", "KiB", "MiB", "GiB", "TiB")
DECIMAL_UNITS = ("B", "KB", "MB", "GB", "TB")

STEPS = {}
for _index, _name in enumerate(BINARY_UNITS):
    STEPS[_name.lower()] = 1024 ** _index
for _index, _name in enumerate(DECIMAL_UNITS):
    STEPS[_name.lower()] = 1000 ** _index


def to_bytes(s):
    if not isinstance(s, str):
        raise ValueError("cannot read %r as a size" % (s,))
    text = s.strip()
    if not text:
        raise ValueError("cannot read an empty string as a size")
    found = SIZE.match(text)
    if not found:
        raise ValueError("cannot read %r as a size" % (s,))
    amount, unit = found.groups()
    key = unit.lower() if unit else "b"
    if key not in STEPS:
        raise ValueError("unknown unit %r in %r" % (unit, s))
    return int(float(amount) * STEPS[key])


def humanize(n, *, binary=True):
    if isinstance(n, bool) or not isinstance(n, int):
        raise ValueError("size must be a whole number of bytes, got %r" % (n,))
    if n < 0:
        raise ValueError("size must not be negative, got %r" % (n,))
    units = BINARY_UNITS if binary else DECIMAL_UNITS
    step = 1024 if binary else 1000
    # Below one step the size is a count of whole things, so no decimal is shown.
    if n < step:
        return "%d B" % n
    value = float(n)
    index = 0
    while value >= step and index < len(units) - 1:
        value /= step
        index += 1
    return "%.1f %s" % (value, units[index])
