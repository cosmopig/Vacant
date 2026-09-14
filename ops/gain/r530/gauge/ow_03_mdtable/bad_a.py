"""Known-bad A: measures width with len() and splits on every pipe.

The two mistakes that show up first: character count instead of display width, so
every CJK table is short by the number of wide characters, and a plain
str.split("|"), so escapes and inline code lose their pipes.
"""

import re

SEPARATOR_CELL = re.compile(r"^:?-+:?$")


def _cells(line):
    parts = line.split("|")
    if parts and parts[0].strip() == "":
        parts = parts[1:]
    if parts and parts[-1].strip() == "":
        parts = parts[:-1]
    return [p.strip() for p in parts]


def realign(text):
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        cells = _cells(lines[i])
        if (len(cells) > 1 and i + 1 < len(lines)
                and all(SEPARATOR_CELL.match(c) for c in _cells(lines[i + 1]))
                and _cells(lines[i + 1])):
            end = i + 2
            while end < len(lines) and lines[end].strip() and "|" in lines[end]:
                end += 1
            rows = [_cells(l) for l in lines[i:end]]
            columns = max(len(r) for r in rows)
            rows = [r + [""] * (columns - len(r)) for r in rows]
            widths = [max(3, max(len(r[c]) for k, r in enumerate(rows) if k != 1))
                      for c in range(columns)]
            for index, row in enumerate(rows):
                if index == 1:
                    drawn = ["-" * widths[c] for c in range(columns)]
                else:
                    drawn = [row[c].ljust(widths[c]) for c in range(columns)]
                out.append("| " + " | ".join(drawn) + " |")
            i = end
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)
