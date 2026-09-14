"""Reference solution for ow_11_reflow (gauge only; never enters a workspace)."""

import re
import unicodedata

BULLET = re.compile(r"^(\s*)((?:[-*]\s+)|(?:\d+\.\s+))(.*)$")
FENCE = "```"


def display_width(text):
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def is_wide(ch):
    return unicodedata.east_asian_width(ch) in ("W", "F")


def split_word(word):
    """A word becomes pieces: each wide character is its own piece.

    That is what lets a line break fall between two Chinese characters while an
    English word stays whole.
    """
    pieces, buffer = [], []
    for ch in word:
        if is_wide(ch):
            if buffer:
                pieces.append("".join(buffer))
                buffer = []
            pieces.append(ch)
        else:
            buffer.append(ch)
    if buffer:
        pieces.append("".join(buffer))
    return pieces


def split_into_pieces(text):
    """[(piece, space_before)] for one paragraph's worth of text."""
    out = []
    for index, word in enumerate(text.split()):
        for position, piece in enumerate(split_word(word)):
            out.append((piece, index > 0 and position == 0))
    return out


def wrap(pieces, first_prefix, continuation_prefix, width):
    lines = []
    prefix = first_prefix
    current = ""
    for piece, space_before in pieces:
        separator = " " if (space_before and current) else ""
        candidate = current + separator + piece
        if current and display_width(prefix) + display_width(candidate) > width:
            lines.append((prefix + current).rstrip())
            prefix = continuation_prefix
            current = piece
        else:
            current = candidate
    lines.append((prefix + current).rstrip())
    return lines


def reflow(text, width):
    if width <= 0:
        raise ValueError("width must be positive, got %r" % (width,))
    ends_with_newline = text.endswith("\n")
    lines = text.split("\n")
    if ends_with_newline:
        lines = lines[:-1]

    out = []
    paragraph = None          # (first_prefix, continuation_prefix, [words...])
    in_fence = False

    def flush():
        if paragraph is not None:
            out.extend(wrap(split_into_pieces(" ".join(paragraph[2])),
                            paragraph[0], paragraph[1], width))

    for line in lines:
        if in_fence:
            out.append(line)
            if line.strip().startswith(FENCE):
                in_fence = False
            continue
        if line.strip().startswith(FENCE):
            flush()
            paragraph = None
            out.append(line)
            in_fence = True
            continue
        if not line.strip():
            flush()
            paragraph = None
            out.append("")
            continue
        bullet = BULLET.match(line)
        if bullet:
            flush()
            indent, marker, rest = bullet.groups()
            paragraph = (indent + marker, " " * (len(indent) + len(marker)), [rest])
            continue
        if paragraph is None:
            indent = line[:len(line) - len(line.lstrip())]
            paragraph = (indent, indent, [line.strip()])
        else:
            paragraph[2].append(line.strip())
    flush()

    joined = "\n".join(out)
    return joined + "\n" if ends_with_newline else joined
