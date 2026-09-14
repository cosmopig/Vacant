"""Known-bad B: placeholders and repeats work, the rest of the syntax does not.

Nested lookup, repeats and the loud KeyError are all there, but comments are
rendered literally, the brace escape is not recognised, a repeat inside a repeat
is silently mangled, and an unclosed placeholder is left in the output.
"""

import re

BLOCK = re.compile(r"\{\{#each\s+([^}]+)\}\}(.*?)\{\{/each\}\}", re.S)
VAR = re.compile(r"\{\{([^}]+)\}\}")


def _walk(root, name):
    node = root
    for part in name.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(name)
        node = node[part]
    return node


def _fill(text, data, current):
    def swap(found):
        name = found.group(1).strip()
        if name == ".":
            return str(current)
        if name.startswith("."):
            return str(_walk(current, name[1:]))
        return str(_walk(data, name))
    return VAR.sub(swap, text)


def render(template, data):
    def expand(found):
        items = _walk(data, found.group(1).strip())
        return "".join(_fill(found.group(2), data, item) for item in items)
    expanded = BLOCK.sub(expand, template)
    return _fill(expanded, data, None)
