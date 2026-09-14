"""Known-bad B: right order, right provenance, three ordinary slips.

It unpacks the split on "=" into exactly two parts, it keeps keys that are not in
the defaults, and its boolean words are only "true" and "false".
"""


class Config(object):
    def __init__(self, values, sources):
        self._values = values
        self._sources = sources

    def get(self, key):
        if key not in self._values:
            raise KeyError(key)
        return self._values[key]

    def source(self, key):
        if key not in self._sources:
            raise KeyError(key)
        return self._sources[key]

    def as_dict(self):
        return dict(self._values)


def _convert(raw, sample):
    if isinstance(sample, bool):
        word = raw.strip().lower()
        if word == "true":
            return True
        if word == "false":
            return False
        raise ValueError("not a boolean: %r" % raw)
    if isinstance(sample, int):
        return int(raw.strip())
    if isinstance(sample, float):
        return float(raw.strip())
    return raw


def load(defaults, file_text, env):
    values = dict(defaults)
    sources = dict((key, "default") for key in defaults)

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
        name, raw = stripped.split("=")
        key = (section + "." + name.strip()) if section else name.strip()
        sample = defaults.get(key, "")
        values[key] = _convert(raw, sample)
        sources[key] = "file"

    for name, raw in env.items():
        if not name.upper().startswith("APP_"):
            continue
        key = name[4:].replace("__", ".").lower()
        sample = defaults.get(key, "")
        values[key] = _convert(raw, sample)
        sources[key] = "env"
    return Config(values, sources)
