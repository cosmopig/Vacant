"""Known-bad A: first registered wins.

Patterns are turned into regexes and tried in registration order, which is the
shortest route to a working prototype and the reason the answer depends on which
module imported first.
"""

import re


def _to_regex(pattern):
    parts = []
    names = []
    for segment in pattern.split("/")[1:]:
        if segment.endswith(":*}") and segment.startswith("{"):
            names.append(segment[1:-3])
            parts.append("(.+)")
        elif segment.startswith("{") and segment.endswith("}"):
            names.append(segment[1:-1])
            parts.append("([^/]+)")
        else:
            parts.append(re.escape(segment))
    return re.compile("^/" + "/".join(parts) + "$"), names


class Router(object):
    def __init__(self):
        self._routes = []

    def add(self, pattern, name):
        rx, names = _to_regex(pattern)
        self._routes.append((rx, names, name))

    def match(self, path):
        for rx, names, name in self._routes:
            found = rx.match(path)
            if found:
                return name, dict(zip(names, found.groups()))
        return None
