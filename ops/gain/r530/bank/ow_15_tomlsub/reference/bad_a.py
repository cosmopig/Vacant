"""Known-bad A: everything is a string and there are no groups.

Split on the first equals sign, throw away anything after a hash, store the rest as
text. Headings look like junk lines and are skipped.
"""


def parse(text):
    out = {}
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if not line or line.startswith("["):
            continue
        if "=" not in line:
            continue
        name, _, value = line.partition("=")
        out[name.strip()] = value.strip().strip('"')
    return out


def dumps(data):
    return "".join('%s = "%s"\n' % (name, data[name]) for name in data)
