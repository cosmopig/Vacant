"""Known-bad B: specificity by counting literals.

It does sort the candidates, which fixes the obvious order dependence, but it
ranks a pattern by how many literal segments it has rather than by where the
first difference falls, it never notices that two patterns are the same pattern,
and it lets a rest-of-path segment sit anywhere.
"""

import re


def _parse(pattern):
    out = []
    for segment in pattern.split("/")[1:]:
        if re.match(r"^\{\w+:\*\}$", segment):
            out.append(("wild", segment[1:-3]))
        elif re.match(r"^\{\w+\}$", segment):
            out.append(("param", segment[1:-1]))
        else:
            out.append(("lit", segment))
    return out


def _capture(parsed, segments):
    params = {}
    for index, (kind, value) in enumerate(parsed):
        if kind == "wild":
            params[value] = "/".join(segments[index:])
            return params
        if index >= len(segments):
            return None
        if kind == "lit":
            if segments[index] != value:
                return None
        else:
            if segments[index] == "":
                return None
            params[value] = segments[index]
    if len(segments) != len(parsed):
        return None
    return params


class Router(object):
    def __init__(self):
        self._routes = []

    def add(self, pattern, name):
        self._routes.append((_parse(pattern), name))

    def match(self, path):
        segments = path.split("/")[1:]
        hits = []
        for parsed, name in self._routes:
            params = _capture(parsed, segments)
            if params is not None:
                literals = sum(1 for kind, _ in parsed if kind == "lit")
                hits.append((-literals, -len(parsed), name, params))
        if not hits:
            return None
        hits.sort(key=lambda row: (row[0], row[1]))
        return hits[0][2], hits[0][3]
