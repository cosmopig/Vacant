"""Known-bad A: merges in the wrong order and never converts anything.

The file is applied last, so it beats the environment, and every value stays the
string it arrived as.
"""


class Config(object):
    def __init__(self, values, sources):
        self._values = values
        self._sources = sources

    def get(self, key):
        return self._values[key]

    def source(self, key):
        return self._sources[key]

    def as_dict(self):
        return dict(self._values)


def load(defaults, file_text, env):
    values = dict(defaults)
    sources = dict((key, "default") for key in defaults)

    for name, raw in env.items():
        if not name.startswith("APP_"):
            continue
        key = name[4:].replace("__", ".").lower()
        if key in defaults:
            values[key] = raw
            sources[key] = "env"

    section = ""
    for line in (file_text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if "=" not in stripped:
            continue
        name, _, raw = stripped.partition("=")
        key = (section + "." + name.strip()) if section else name.strip()
        if key in defaults:
            values[key] = raw.strip()
            sources[key] = "file"
    return Config(values, sources)
