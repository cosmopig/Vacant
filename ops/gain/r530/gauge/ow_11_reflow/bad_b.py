"""Known-bad B: columns and bullets right, three other things wrong.

It measures display width, hangs bullet continuations correctly and leaves fenced
blocks alone, but a run of Chinese is treated as one unbreakable word, a run of
blank lines collapses to one, and a piece longer than the width is chopped to fit.
"""

import re
import unicodedata

BULLET = re.compile(r"^(\s*)((?:[-*]\s+)|(?:\d+\.\s+))(.*)$")


def _width(text):
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _wrap(words, first_prefix, continuation_prefix, width):
    lines = []
    prefix = first_prefix
    current = ""
    for word in words:
        while _width(word) > width - _width(prefix):
            head = word[:max(1, width - _width(prefix))]
            lines.append(prefix + head)
            prefix = continuation_prefix
            word = word[len(head):]
        candidate = (current + " " + word) if current else word
        if current and _width(prefix) + _width(candidate) > width:
            lines.append(prefix + current)
            prefix = continuation_prefix
            current = word
        else:
            current = candidate
    lines.append(prefix + current)
    return lines


def reflow(text, width):
    if width <= 0:
        raise ValueError("width must be positive")
    trailing = text.endswith("\n")
    lines = text.split("\n")
    if trailing:
        lines = lines[:-1]

    out = []
    pending = None
    in_fence = False
    for line in lines:
        if in_fence:
            out.append(line)
            if line.strip().startswith("```"):
                in_fence = False
            continue
        if line.strip().startswith("```"):
            if pending:
                out.extend(_wrap(" ".join(pending[2]).split(), pending[0], pending[1], width))
                pending = None
            out.append(line)
            in_fence = True
            continue
        if not line.strip():
            if pending:
                out.extend(_wrap(" ".join(pending[2]).split(), pending[0], pending[1], width))
                pending = None
            if out and out[-1] != "":
                out.append("")
            continue
        bullet = BULLET.match(line)
        if bullet:
            if pending:
                out.extend(_wrap(" ".join(pending[2]).split(), pending[0], pending[1], width))
            indent, marker, rest = bullet.groups()
            pending = (indent + marker, " " * (len(indent) + len(marker)), [rest])
            continue
        if pending is None:
            indent = line[:len(line) - len(line.lstrip())]
            pending = (indent, indent, [line.strip()])
        else:
            pending[2].append(line.strip())
    if pending:
        out.extend(_wrap(" ".join(pending[2]).split(), pending[0], pending[1], width))
    joined = "\n".join(out)
    return joined + "\n" if trailing else joined
