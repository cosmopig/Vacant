"""Known-bad B: the closest near miss.

The five kinds, the groups and the lists are all right. What is wrong: comments are
stripped without looking at quotes, nothing notices a name or a heading used twice,
and text is written back out without escaping.
"""

import re

WHOLE = re.compile(r"^-?\d+$")
DECIMAL = re.compile(r"^-?\d+\.\d+$")


def _value(text, number):
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        items = [_value(piece.strip(), number) for piece in inner.split(",")]
        kinds = set(type(item).__name__ for item in items)
        if len(kinds) > 1:
            raise ValueError("line %d: mixed list" % number)
        return items
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        return text[1:-1].replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
    if text == "true":
        return True
    if text == "false":
        return False
    if WHOLE.match(text):
        return int(text)
    if DECIMAL.match(text):
        return float(text)
    raise ValueError("line %d: cannot read %r" % (number, text))


def parse(text):
    root = {}
    node = root
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#")[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            node = root
            for piece in line[1:-1].split("."):
                node = node.setdefault(piece.strip(), {})
            continue
        if "=" not in line:
            raise ValueError("line %d: not a name and a value" % number)
        name, _, rest = line.partition("=")
        node[name.strip()] = _value(rest.strip(), number)
    return root


def _write(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return '"%s"' % value
    if isinstance(value, list):
        return "[%s]" % ", ".join(_write(item) for item in value)
    raise ValueError("cannot write %r" % (value,))


def _emit(node, path, lines):
    for name in sorted(k for k, v in node.items() if not isinstance(v, dict)):
        lines.append("%s = %s" % (name, _write(node[name])))
    for name in sorted(k for k, v in node.items() if isinstance(v, dict)):
        child = path + (name,)
        if lines:
            lines.append("")
        lines.append("[%s]" % ".".join(child))
        _emit(node[name], child, lines)


def dumps(data):
    lines = []
    _emit(data, (), lines)
    return "".join(line + "\n" for line in lines)
