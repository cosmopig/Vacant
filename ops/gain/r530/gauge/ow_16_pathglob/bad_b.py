"""Known-bad B: the closest near miss.

Stars stay inside a segment, classes and ranges work, the whole path has to match,
and bad patterns are reported. What is wrong: the double star insists on at least
one segment, the exclamation mark is not understood, and the result comes back in
the order the patterns picked things up rather than the order the files were
listed.
"""

import re


def _segment(segment, pattern):
    out = []
    index = 0
    while index < len(segment):
        ch = segment[index]
        if ch == "*":
            out.append("[^/]*")
            index += 1
        elif ch == "?":
            out.append("[^/]")
            index += 1
        elif ch == "[":
            close = segment.find("]", index + 1)
            if close == -1:
                raise ValueError("unclosed [ in %r" % (pattern,))
            body = segment[index + 1:close]
            if not body:
                raise ValueError("empty class in %r" % (pattern,))
            if body.startswith("!"):
                out.append("[^%s]" % body[1:])
            else:
                out.append("[%s]" % body)
            index = close + 1
        else:
            out.append(re.escape(ch))
            index += 1
    return "".join(out)


def _regex(pattern):
    pieces = []
    for segment in pattern.split("/"):
        if segment == "**":
            pieces.append("[^/]+(?:/[^/]+)*")
        else:
            pieces.append(_segment(segment, pattern))
    return re.compile("/".join(pieces) + r"\Z")


def matches(pattern, path):
    return bool(_regex(pattern).match(path))


def select(patterns, paths):
    out = []
    for pattern in patterns:
        rx = _regex(pattern)
        for path in paths:
            if rx.match(path) and path not in out:
                out.append(path)
    return out
