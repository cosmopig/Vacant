"""Known-bad A: textwrap over the whole thing.

One call to textwrap.fill per paragraph, counting characters rather than columns,
with no idea that bullets or fenced blocks exist.
"""

import textwrap


def reflow(text, width):
    out = []
    for block in text.split("\n\n"):
        if not block.strip():
            out.append("")
            continue
        out.append(textwrap.fill(" ".join(block.split()), width=width))
    return "\n\n".join(out)
