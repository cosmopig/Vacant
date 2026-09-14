"""Reference solution for ow_15_tomlsub (gauge only; never enters a workspace)."""

import re

NAME = re.compile(r"^[A-Za-z0-9_-]+$")
WHOLE = re.compile(r"^-?\d+$")
DECIMAL = re.compile(r"^-?\d+\.\d+$")

ESCAPES = {'"': '"', "\\": "\\", "n": "\n", "t": "\t"}
UNESCAPES = {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\t": "\\t"}


def strip_comment(line):
    """Drop a trailing comment. Has to know about quotes: a `#` inside text is
    part of the text, not the start of a comment."""
    out = []
    inside = False
    index = 0
    while index < len(line):
        ch = line[index]
        if inside:
            if ch == "\\" and index + 1 < len(line):
                out.append(line[index:index + 2])
                index += 2
                continue
            if ch == '"':
                inside = False
            out.append(ch)
            index += 1
            continue
        if ch == '"':
            inside = True
            out.append(ch)
            index += 1
            continue
        if ch == "#":
            break
        out.append(ch)
        index += 1
    return "".join(out)


def parse_string(text, number):
    if len(text) < 2 or not text.endswith('"'):
        raise ValueError("line %d: unterminated text %r" % (number, text))
    body = text[1:-1]
    out = []
    index = 0
    while index < len(body):
        ch = body[index]
        if ch == "\\":
            if index + 1 >= len(body):
                raise ValueError("line %d: a backslash at the end of text" % number)
            code = body[index + 1]
            if code not in ESCAPES:
                raise ValueError("line %d: unknown escape \\%s" % (number, code))
            out.append(ESCAPES[code])
            index += 2
            continue
        if ch == '"':
            raise ValueError("line %d: an unescaped quote inside text" % number)
        out.append(ch)
        index += 1
    return "".join(out)


def split_items(inner, number):
    items, buffer = [], []
    inside = False
    index = 0
    while index < len(inner):
        ch = inner[index]
        if inside:
            if ch == "\\" and index + 1 < len(inner):
                buffer.append(inner[index:index + 2])
                index += 2
                continue
            if ch == '"':
                inside = False
            buffer.append(ch)
            index += 1
            continue
        if ch == '"':
            inside = True
            buffer.append(ch)
            index += 1
            continue
        if ch == ",":
            items.append("".join(buffer))
            buffer = []
            index += 1
            continue
        buffer.append(ch)
        index += 1
    if inside:
        raise ValueError("line %d: unterminated text in a list" % number)
    items.append("".join(buffer))
    if any(item.strip() == "" for item in items):
        raise ValueError("line %d: an empty item in a list" % number)
    return items


def parse_value(text, number):
    if not text:
        raise ValueError("line %d: a name with no value" % number)
    if text.startswith("["):
        if not text.endswith("]"):
            raise ValueError("line %d: unterminated list %r" % (number, text))
        inner = text[1:-1].strip()
        if not inner:
            return []
        items = [parse_value(piece.strip(), number) for piece in split_items(inner, number)]
        if any(isinstance(item, list) for item in items):
            raise ValueError("line %d: a list inside a list" % number)
        kinds = set(type(item).__name__ for item in items)
        if len(kinds) > 1:
            raise ValueError("line %d: a list mixing %s" % (number, ", ".join(sorted(kinds))))
        return items
    if text.startswith('"'):
        return parse_string(text, number)
    if text == "true":
        return True
    if text == "false":
        return False
    if WHOLE.match(text):
        return int(text)
    if DECIMAL.match(text):
        return float(text)
    raise ValueError("line %d: cannot read %r as a value" % (number, text))


def parse(text):
    root = {}
    path = ()
    names_seen = {(): set()}
    headings_seen = set()
    for number, raw in enumerate(text.splitlines(), start=1):
        line = strip_comment(raw).strip()
        if not line:
            continue
        if line.startswith("["):
            if not line.endswith("]"):
                raise ValueError("line %d: unterminated heading %r" % (number, line))
            parts = [piece.strip() for piece in line[1:-1].split(".")]
            if not parts or any(not NAME.match(piece) for piece in parts):
                raise ValueError("line %d: bad heading %r" % (number, line))
            path = tuple(parts)
            if path in headings_seen:
                raise ValueError("line %d: heading %r opened twice" % (number, line))
            headings_seen.add(path)
            names_seen.setdefault(path, set())
            node = root
            for piece in parts:
                node = node.setdefault(piece, {})
                if not isinstance(node, dict):
                    raise ValueError("line %d: %r is already a value" % (number, piece))
            continue
        if "=" not in line:
            raise ValueError("line %d: not a name and a value: %r" % (number, line))
        name, _, rest = line.partition("=")
        name = name.strip()
        if not NAME.match(name):
            raise ValueError("line %d: bad name %r" % (number, name))
        if name in names_seen[path]:
            raise ValueError("line %d: name %r used twice in the same group" % (number, name))
        names_seen[path].add(name)
        node = root
        for piece in path:
            node = node[piece]
        node[name] = parse_value(rest.strip(), number)
    return root


def escape(text):
    return "".join(UNESCAPES.get(ch, ch) for ch in text)


def dump_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        written = repr(value)
        if not DECIMAL.match(written):
            raise ValueError("cannot write the decimal %r" % (value,))
        return written
    if isinstance(value, str):
        return '"%s"' % escape(value)
    if isinstance(value, list):
        if any(isinstance(item, list) for item in value):
            raise ValueError("cannot write a list inside a list")
        kinds = set(type(item).__name__ for item in value)
        if len(kinds) > 1:
            raise ValueError("cannot write a list mixing %s" % ", ".join(sorted(kinds)))
        return "[%s]" % ", ".join(dump_value(item) for item in value)
    raise ValueError("cannot write a value of type %s" % type(value).__name__)


def check_name(name):
    if not isinstance(name, str) or not NAME.match(name):
        raise ValueError("cannot write the name %r" % (name,))


def emit(node, path, lines):
    for name in sorted(k for k, v in node.items() if not isinstance(v, dict)):
        check_name(name)
        lines.append("%s = %s" % (name, dump_value(node[name])))
    for name in sorted(k for k, v in node.items() if isinstance(v, dict)):
        check_name(name)
        child = path + (name,)
        if lines:
            lines.append("")
        lines.append("[%s]" % ".".join(child))
        emit(node[name], child, lines)


def dumps(data):
    if not isinstance(data, dict):
        raise ValueError("cannot write a value of type %s" % type(data).__name__)
    lines = []
    emit(data, (), lines)
    return "".join(line + "\n" for line in lines)
