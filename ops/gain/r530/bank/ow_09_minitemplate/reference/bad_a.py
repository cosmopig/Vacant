"""Known-bad A: str.replace for every key in the data.

The shortest thing that looks like it works: no nested paths, no repeats, and any
placeholder the data does not mention is simply left alone.
"""


def render(template, data):
    out = template
    for key, value in data.items():
        out = out.replace("{{" + key + "}}", str(value))
    return out
