"""Reference solution for ow_04_layerconf (gauge only; never enters a workspace)."""

PREFIX = "APP_"
TRUE_WORDS = ("true", "1", "yes")
FALSE_WORDS = ("false", "0", "no")


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


def coerce(raw, sample, key):
    """Turn a raw string into the type the key already has in `defaults`."""
    # bool first: bool is a subclass of int, so the int branch would swallow it.
    if isinstance(sample, bool):
        word = raw.strip().lower()
        if word in TRUE_WORDS:
            return True
        if word in FALSE_WORDS:
            return False
        raise ValueError("%s: cannot read %r as a boolean" % (key, raw))
    if isinstance(sample, int):
        try:
            return int(raw.strip())
        except ValueError:
            raise ValueError("%s: cannot read %r as an integer" % (key, raw)) from None
    if isinstance(sample, float):
        try:
            return float(raw.strip())
        except ValueError:
            raise ValueError("%s: cannot read %r as a number" % (key, raw)) from None
    return raw


def parse_file(text):
    """Yield (key, raw_value) pairs in the order the file gives them."""
    section = ""
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            continue
        if "=" not in stripped:
            continue
        name, _, raw = stripped.partition("=")
        name = name.strip()
        yield ("%s.%s" % (section, name) if section else name), raw.strip()


def env_key(name):
    """The dotted key an environment variable sets, or None if it sets nothing."""
    if not name.upper().startswith(PREFIX):
        return None
    return name[len(PREFIX):].replace("__", ".").lower()


def apply_layer(values, sources, pairs, label, defaults):
    for key, raw in pairs:
        if key is None or key not in defaults:
            continue
        values[key] = coerce(raw, defaults[key], key)
        sources[key] = label


def load(defaults, file_text, env):
    values = dict(defaults)
    sources = dict((key, "default") for key in defaults)
    apply_layer(values, sources, parse_file(file_text), "file", defaults)
    apply_layer(values, sources,
                ((env_key(name), raw) for name, raw in env.items()), "env", defaults)
    return Config(values, sources)
