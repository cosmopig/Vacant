"""Reference solution for ow_06_verrange (gauge only; never enters a workspace)."""

import re

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")

# Longest first: "<=" has to be recognised before "<".
OPERATORS = (">=", "<=", "==", "!=", ">", "<")

ACCEPTS = {
    ">": (1,),
    ">=": (0, 1),
    "<": (-1,),
    "<=": (-1, 0),
    "==": (0,),
    "!=": (-1, 1),
}


def parse_version(text):
    """Return (numbers, prerelease_identifiers_or_None); raise on anything else."""
    if not isinstance(text, str):
        raise ValueError("not a version: %r" % (text,))
    found = VERSION_RE.match(text.strip())
    if not found:
        raise ValueError("not a version: %r" % (text,))
    numbers = tuple(int(group) for group in found.groups()[:3])
    raw = found.group(4)
    if raw is None:
        return numbers, None
    identifiers = raw.split(".")
    if any(identifier == "" for identifier in identifiers):
        raise ValueError("empty pre-release identifier in %r" % (text,))
    return numbers, identifiers


def identifier_key(identifier):
    """Sort key for one pre-release identifier.

    The leading 0/1 is what puts every all-digit identifier below every textual
    one; without it "9" and "rc" would be compared as strings.
    """
    if identifier.isdigit():
        return (0, int(identifier), "")
    return (1, 0, identifier)


def compare(a, b):
    numbers_a, pre_a = parse_version(a)
    numbers_b, pre_b = parse_version(b)
    if numbers_a != numbers_b:
        return -1 if numbers_a < numbers_b else 1
    if pre_a is None and pre_b is None:
        return 0
    if pre_a is None:
        return 1
    if pre_b is None:
        return -1
    for left, right in zip(pre_a, pre_b):
        key_left, key_right = identifier_key(left), identifier_key(right)
        if key_left != key_right:
            return -1 if key_left < key_right else 1
    if len(pre_a) == len(pre_b):
        return 0
    return -1 if len(pre_a) < len(pre_b) else 1


def split_condition(condition):
    for operator in OPERATORS:
        if condition.startswith(operator):
            return operator, condition[len(operator):].strip()
    raise ValueError("unrecognised operator in condition %r" % (condition,))


def satisfies(version, spec):
    parse_version(version)
    conditions = [piece.strip() for piece in spec.split(",")]
    if any(condition == "" for condition in conditions):
        raise ValueError("empty condition in spec %r" % (spec,))
    for condition in conditions:
        operator, target = split_condition(condition)
        if compare(version, target) not in ACCEPTS[operator]:
            return False
    return True
