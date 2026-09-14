"""Known-bad B: widths and markers right, structure wrong.

Display width and the alignment markers are handled properly, but fenced code
blocks are not tracked at all, an escaped pipe is treated as a separator, and the
document is rebuilt with "\n" so a CRLF file comes back rewritten.
"""

import re
import unicodedata

SEPARATOR_CELL = re.compile(r"^:?-+:?$")


def _width(text):
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _cells(line):
    parts = line.split("|")
    if len(parts) > 1 and parts[0].strip() == "":
        parts = parts[1:]
    if len(parts) > 1 and parts[-1].strip() == "":
        parts = parts[:-1]
    return [p.strip() for p in parts]


def _separator(marker, width):
    left = marker.startswith(":")
    right = marker.endswith(":") and len(marker) >= 2
    dashes = max(1, width - (1 if left else 0) - (1 if right else 0))
    return (":" if left else "") + "-" * dashes + (":" if right else "")


def realign(text):
    lines = text.replace("\r\n", "\n").split("\n")
    out = []
    i = 0
    while i < len(lines):
        head = _cells(lines[i])
        nxt = _cells(lines[i + 1]) if i + 1 < len(lines) else []
        if (len(head) > 1 and nxt and all(SEPARATOR_CELL.match(c) for c in nxt)
                and not all(SEPARATOR_CELL.match(c) for c in head)):
            end = i + 2
            while end < len(lines) and lines[end].strip() and "|" in lines[end]:
                end += 1
            rows = [_cells(l) for l in lines[i:end]]
            columns = max(len(r) for r in rows)
            rows = [r + [""] * (columns - len(r)) for r in rows]
            widths = [max(3, max(_width(r[c]) for k, r in enumerate(rows) if k != 1))
                      for c in range(columns)]
            for index, row in enumerate(rows):
                if index == 1:
                    drawn = [_separator(row[c], widths[c]) for c in range(columns)]
                else:
                    drawn = [row[c] + " " * (widths[c] - _width(row[c])) for c in range(columns)]
                out.append("| " + " | ".join(drawn) + " |")
            i = end
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)
