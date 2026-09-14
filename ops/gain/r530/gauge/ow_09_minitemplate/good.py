"""Reference solution for ow_09_minitemplate (gauge only; never enters a workspace)."""

OUTSIDE = object()          # marker for "not inside an each block"


def tokenize(template):
    """Turn a template into [(kind, value)] where kind is text/var/comment/open/close."""
    tokens = []
    text = []
    index, size = 0, len(template)
    while index < size:
        # The escape has to be recognised before the opening brace, or "\{{" would
        # start a placeholder whose first character is a backslash.
        if template.startswith("\\{{", index):
            text.append("{{")
            index += 3
            continue
        if template.startswith("{{", index):
            closing = template.find("}}", index + 2)
            if closing == -1:
                raise ValueError("unclosed {{ at offset %d" % index)
            body = template[index + 2:closing].strip()
            if text:
                tokens.append(("text", "".join(text)))
                text = []
            if body.startswith("!"):
                tokens.append(("comment", body[1:].strip()))
            elif body.startswith("#each"):
                name = body[len("#each"):].strip()
                if not name:
                    raise ValueError("{{#each}} needs a name")
                tokens.append(("open", name))
            elif body == "/each":
                tokens.append(("close", ""))
            elif not body:
                raise ValueError("empty placeholder at offset %d" % index)
            else:
                tokens.append(("var", body))
            index = closing + 2
            continue
        text.append(template[index])
        index += 1
    if text:
        tokens.append(("text", "".join(text)))
    return tokens


def walk(root, parts, written):
    node = root
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            raise KeyError(written)
        node = node[part]
    return node


def lookup(name, data, current):
    if name.startswith("."):
        if current is OUTSIDE:
            raise ValueError("%r is only meaningful inside an {{#each}} block" % ("{{%s}}" % name))
        if name == ".":
            return current
        return walk(current, name[1:].split("."), name)
    return walk(data, name.split("."), name)


def render_tokens(tokens, data, current, out):
    index = 0
    while index < len(tokens):
        kind, value = tokens[index]
        if kind == "text":
            out.append(value)
        elif kind == "comment":
            pass
        elif kind == "var":
            out.append(str(lookup(value, data, current)))
        elif kind == "close":
            raise ValueError("{{/each}} with no {{#each}} open")
        else:
            end = index + 1
            while end < len(tokens) and tokens[end][0] != "close":
                if tokens[end][0] == "open":
                    raise ValueError("an {{#each}} block may not contain another one")
                end += 1
            if end >= len(tokens):
                raise ValueError("{{#each %s}} is never closed" % value)
            items = lookup(value, data, current)
            if not isinstance(items, list):
                raise ValueError("{{#each %s}} needs a list, found %s" % (value, type(items).__name__))
            body = tokens[index + 1:end]
            for item in items:
                render_tokens(body, data, item, out)
            index = end
        index += 1


def render(template, data):
    out = []
    render_tokens(tokenize(template), data, OUTSIDE, out)
    return "".join(out)
