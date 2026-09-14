"""Known-bad C: the skeleton. Every name exists, almost nothing happens."""
def parse(text):
    out = {}
    for line in text.splitlines():
        if "=" in line:
            name, _, value = line.partition("=")
            out[name.strip()] = value.strip()
    return out


def dumps(data):
    return "".join("%s = %s\n" % (name, data[name]) for name in data)
