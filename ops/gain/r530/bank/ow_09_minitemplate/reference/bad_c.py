"""Known-bad C: the skeleton. Every name exists, almost nothing happens."""
def render(template, data):
    out = template
    for key, value in data.items():
        out = out.replace("{{" + key + "}}", str(value))
    return out
