"""Reference solution for ow_05_router (gauge only; never enters a workspace)."""

import re

LITERAL, PARAMETER, WILDCARD = 0, 1, 2

PARAM_RE = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*)\}$")
WILDCARD_RE = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*):\*\}$")


def parse_pattern(pattern):
    """Turn a pattern into [(kind, value), ...]; raise for anything malformed."""
    if not pattern.startswith("/"):
        raise ValueError("a pattern must begin with '/': %r" % pattern)
    raw = pattern.split("/")[1:]
    parsed = []
    for index, segment in enumerate(raw):
        param = PARAM_RE.match(segment)
        if param:
            parsed.append((PARAMETER, param.group(1)))
            continue
        wild = WILDCARD_RE.match(segment)
        if wild:
            if index != len(raw) - 1:
                raise ValueError("a {name:*} segment may only appear last: %r" % pattern)
            parsed.append((WILDCARD, wild.group(1)))
            continue
        if "{" in segment or "}" in segment:
            raise ValueError("malformed segment %r in %r" % (segment, pattern))
        parsed.append((LITERAL, segment))
    return parsed


def shape(parsed):
    """What makes two patterns the same pattern: kinds plus literals, not names."""
    return tuple((kind, value if kind == LITERAL else "") for kind, value in parsed)


def more_specific(left, right):
    """True when `left` wins. The first position where the ranks differ decides."""
    for (left_kind, _), (right_kind, _) in zip(left, right):
        if left_kind != right_kind:
            return left_kind < right_kind
    return len(left) > len(right)


def capture(parsed, segments):
    """The parameters this pattern pulls out of these segments, or None."""
    params = {}
    for index, (kind, value) in enumerate(parsed):
        if kind == WILDCARD:
            rest = "/".join(segments[index:])
            if rest == "":
                return None
            params[value] = rest
            return params
        if index >= len(segments):
            return None
        segment = segments[index]
        if kind == LITERAL:
            if segment != value:
                return None
        else:
            if segment == "":
                return None
            params[value] = segment
    if len(segments) != len(parsed):
        return None
    return params


class Router(object):
    def __init__(self):
        self._routes = []

    def add(self, pattern, name):
        parsed = parse_pattern(pattern)
        fingerprint = shape(parsed)
        for known, _name, known_shape in self._routes:
            if known_shape == fingerprint:
                raise ValueError("pattern %r is already registered" % pattern)
        self._routes.append((parsed, name, fingerprint))

    def match(self, path):
        segments = path.split("/")[1:]
        best = None
        for parsed, name, _shape in self._routes:
            params = capture(parsed, segments)
            if params is None:
                continue
            if best is None or more_specific(parsed, best[0]):
                best = (parsed, name, params)
        if best is None:
            return None
        return best[1], best[2]
