"""Known-bad A: one meaning of KB, and rounding.

Every unit steps by 1024, the fraction is rounded rather than dropped, and the
printed form has no decimal at all.
"""

UNITS = ["B", "KB", "MB", "GB", "TB"]


def to_bytes(s):
    text = s.strip()
    digits = ""
    unit = ""
    for ch in text:
        if ch.isdigit() or ch == ".":
            digits += ch
        elif not ch.isspace():
            unit += ch
    factor = 1
    if unit:
        letter = unit[0].upper()
        factor = 1024 ** ("BKMGT".index(letter) if letter in "BKMGT" else 0)
    return round(float(digits) * factor)


def humanize(n, *, binary=True):
    value = float(n)
    index = 0
    while value >= 1024 and index < len(UNITS) - 1:
        value /= 1024
        index += 1
    return "%d %s" % (round(value), UNITS[index])
