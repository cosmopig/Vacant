"""Reference solution for ow_03_mdtable (gauge only; never enters a workspace)."""

import re
import unicodedata

SEPARATOR_CELL = re.compile(r"^:?-+:?$")
LINE = re.compile(r"[^\n]*\n|[^\n]+\Z")


def display_width(text):
    """Columns the text occupies in a fixed-width terminal."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def split_cells(line):
    """Split a row on column separators only.

    The backslash and backtick states have to be tracked in the same scan: a
    backtick inside an escaped sequence is not a code delimiter, and a pipe inside
    a code span is not a separator.
    """
    cells, buf = [], []
    in_code = False
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if ch == "\\" and i + 1 < n:
            buf.append(line[i:i + 2])
            i += 2
            continue
        if ch == "`":
            in_code = not in_code
            buf.append(ch)
            i += 1
            continue
        if ch == "|" and not in_code:
            cells.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    cells.append("".join(buf))
    if len(cells) > 1 and cells[0].strip() == "" and line.lstrip().startswith("|"):
        cells = cells[1:]
    if len(cells) > 1 and cells[-1].strip() == "" and line.rstrip().endswith("|"):
        cells = cells[:-1]
    return [cell.strip() for cell in cells]


def has_separator(line):
    return len(split_cells(line)) > 1 or ("|" in line and split_cells(line) != [line.strip()])


def is_separator_row(line):
    cells = split_cells(line)
    return bool(cells) and all(SEPARATOR_CELL.match(cell) for cell in cells)


def render_separator(marker, width):
    left = marker.startswith(":")
    right = marker.endswith(":") and len(marker) >= 2
    dashes = max(1, width - (1 if left else 0) - (1 if right else 0))
    return (":" if left else "") + "-" * dashes + (":" if right else "")


def render_table(rows):
    parsed = [split_cells(row) for row in rows]
    columns = max(len(cells) for cells in parsed)
    parsed = [cells + [""] * (columns - len(cells)) for cells in parsed]
    widths = []
    for column in range(columns):
        width = 3
        for index, cells in enumerate(parsed):
            if index == 1:
                continue
            width = max(width, display_width(cells[column]))
        widths.append(width)

    out = []
    for index, cells in enumerate(parsed):
        if index == 1:
            drawn = [render_separator(cells[c], widths[c]) for c in range(columns)]
        else:
            drawn = [cells[c] + " " * (widths[c] - display_width(cells[c])) for c in range(columns)]
        out.append("| " + " | ".join(drawn) + " |")
    return out


def split_lines(text):
    lines, endings = [], []
    for part in LINE.findall(text):
        if part.endswith("\r\n"):
            lines.append(part[:-2])
            endings.append("\r\n")
        elif part.endswith("\n"):
            lines.append(part[:-1])
            endings.append("\n")
        else:
            lines.append(part)
            endings.append("")
    return lines, endings


def realign(text):
    lines, endings = split_lines(text)
    out = []
    fence = None
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if fence is not None:
            out.append(line)
            if stripped.startswith(fence):
                fence = None
            i += 1
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence = stripped[:3]
            out.append(line)
            i += 1
            continue
        if (has_separator(line) and i + 1 < len(lines)
                and is_separator_row(lines[i + 1]) and not is_separator_row(line)):
            end = i + 2
            while end < len(lines) and lines[end].strip() and has_separator(lines[end]):
                end += 1
            out.extend(render_table(lines[i:end]))
            i = end
            continue
        out.append(line)
        i += 1
    return "".join(line + ending for line, ending in zip(out, endings))
