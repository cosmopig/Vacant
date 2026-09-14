"""Reference solution for ow_16_pathglob (gauge only; never enters a workspace)."""

import re

DOUBLE_STAR = "**"


def class_body(body, pattern):
    if not body:
        raise ValueError("empty character class in %r" % (pattern,))
    out = []
    for ch in body:
        out.append("\\" + ch if ch in "\\]^" else ch)
    return "".join(out)


def segment_matcher(segment, pattern):
    """A compiled matcher for one segment, where `/` can never be matched."""
    out = []
    index, size = 0, len(segment)
    while index < size:
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
            negated = body.startswith("!")
            out.append("[%s%s]" % ("^" if negated else "",
                                   class_body(body[1:] if negated else body, pattern)))
            index = close + 1
        else:
            out.append(re.escape(ch))
            index += 1
    return re.compile("".join(out) + r"\Z")


def compile_pattern(pattern):
    """[matcher or DOUBLE_STAR, ...]. Raises here, when the pattern is read."""
    compiled = []
    for segment in pattern.split("/"):
        if segment == DOUBLE_STAR:
            compiled.append(DOUBLE_STAR)
        else:
            compiled.append(segment_matcher(segment, pattern))
    return compiled


def walk(compiled, segments):
    if not compiled:
        return not segments
    head = compiled[0]
    if head is DOUBLE_STAR:
        # It may swallow nothing at all, so every length has to be tried.
        return any(walk(compiled[1:], segments[taken:]) for taken in range(len(segments) + 1))
    if not segments:
        return False
    if head.match(segments[0]):
        return walk(compiled[1:], segments[1:])
    return False


def matches(pattern, path):
    return walk(compile_pattern(pattern), path.split("/"))


def select(patterns, paths):
    position = dict((path, index) for index, path in enumerate(paths))
    chosen = set()
    for pattern in patterns:
        removing = pattern.startswith("!")
        body = pattern[1:] if removing else pattern
        compiled = compile_pattern(body)          # validated even if nothing matches
        hits = set(path for path in paths if walk(compiled, path.split("/")))
        chosen = (chosen - hits) if removing else (chosen | hits)
    return sorted(chosen, key=lambda path: position[path])
